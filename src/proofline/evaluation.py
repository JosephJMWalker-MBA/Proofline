"""Retrieval evaluation against explicit evidence targets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .search import SearchIndex
from .storage import ProoflineStore

_EVAL_SCHEMA = "proofline-retrieval-eval/v1"


@dataclass(frozen=True, slots=True)
class ExpectedTarget:
    source_uri: str
    locator: str
    artifact_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    query: str
    expected: tuple[ExpectedTarget, ...]


@dataclass(frozen=True, slots=True)
class RetrievalSuite:
    name: str
    cases: tuple[RetrievalCase, ...]
    schema: str = _EVAL_SCHEMA


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    query: str
    expected_evidence_ids: tuple[str, ...]
    returned_evidence_ids: tuple[str, ...]
    unresolved_targets: tuple[dict, ...]
    hit: bool
    target_recall: float
    provenance_validity: float

    def to_dict(self) -> dict:
        data = asdict(self)
        data["expected_evidence_ids"] = list(self.expected_evidence_ids)
        data["returned_evidence_ids"] = list(self.returned_evidence_ids)
        data["unresolved_targets"] = list(self.unresolved_targets)
        return data


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    suite: str
    build_id: str
    k: int
    cases: int
    hit_rate_at_k: float
    target_recall_at_k: float
    provenance_validity: float
    unresolved_target_count: int
    case_results: tuple[CaseEvaluation, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["case_results"] = [item.to_dict() for item in self.case_results]
        return data


def load_retrieval_suite(path: str | Path) -> RetrievalSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _EVAL_SCHEMA:
        raise ValueError(f"evaluation schema must be {_EVAL_SCHEMA!r}")
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("evaluation suite name must be non-empty")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("evaluation cases must be a non-empty list")

    cases: list[RetrievalCase] = []
    seen_ids: set[str] = set()
    for item in raw_cases:
        if not isinstance(item, dict):
            raise ValueError("each evaluation case must be an object")
        case_id = item.get("case_id")
        query = item.get("query")
        raw_expected = item.get("expected")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case_id must be non-empty")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(query, str) or not query:
            raise ValueError(f"query must be non-empty for {case_id}")
        if not isinstance(raw_expected, list) or not raw_expected:
            raise ValueError(f"expected targets must be non-empty for {case_id}")

        targets: list[ExpectedTarget] = []
        for target in raw_expected:
            if not isinstance(target, dict):
                raise ValueError(f"expected target must be an object for {case_id}")
            source_uri = target.get("source_uri")
            locator = target.get("locator")
            if not isinstance(source_uri, str) or not source_uri:
                raise ValueError(f"source_uri missing for {case_id}")
            if not isinstance(locator, str) or not locator:
                raise ValueError(f"locator missing for {case_id}")
            targets.append(
                ExpectedTarget(
                    source_uri=source_uri,
                    locator=locator,
                    artifact_sha256=target.get("artifact_sha256"),
                )
            )
        cases.append(RetrievalCase(case_id=case_id, query=query, expected=tuple(targets)))

    return RetrievalSuite(name=name, cases=tuple(cases))


class RetrievalEvaluator:
    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self.index = SearchIndex(self.state_dir)

    def _resolve_target(self, target: ExpectedTarget) -> tuple[str, ...]:
        clauses = ["s.source_uri = ?", "eu.locator = ?"]
        params: list[object] = [target.source_uri, target.locator]
        if target.artifact_sha256:
            clauses.append("a.sha256 = ?")
            params.append(target.artifact_sha256)
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT eu.evidence_id
                FROM sources s
                JOIN source_snapshots ss ON ss.source_id = s.source_id
                JOIN artifacts a ON a.artifact_id = ss.artifact_id
                JOIN evidence_units eu ON eu.artifact_id = a.artifact_id
                WHERE {' AND '.join(clauses)}
                ORDER BY eu.evidence_id
                """,
                params,
            ).fetchall()
        return tuple(str(row["evidence_id"]) for row in rows)

    def _hit_has_valid_provenance(self, hit) -> bool:
        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM evidence_units eu
                JOIN artifacts a ON a.artifact_id = eu.artifact_id
                WHERE eu.evidence_id = ?
                  AND eu.artifact_id = ?
                  AND eu.locator = ?
                """,
                (hit.evidence_id, hit.artifact_id, hit.locator),
            ).fetchone()
        return row is not None and bool(hit.sources)

    def run(self, suite: RetrievalSuite, *, k: int = 5) -> EvaluationResult:
        if k < 1:
            raise ValueError("k must be positive")
        build = self.index.current_build()
        if build is None:
            raise RuntimeError("search index has not been built; run `proofline index` first")

        case_results: list[CaseEvaluation] = []
        total_expected = 0
        total_found = 0
        total_hits = 0
        valid_hits = 0
        unresolved_count = 0

        for case in suite.cases:
            expected_ids: set[str] = set()
            unresolved: list[dict] = []
            for target in case.expected:
                resolved = self._resolve_target(target)
                if not resolved:
                    unresolved.append(asdict(target))
                    unresolved_count += 1
                expected_ids.update(resolved)

            hits = self.index.search(case.query, limit=k)
            returned_ids = tuple(hit.evidence_id for hit in hits)
            returned_set = set(returned_ids)
            found = expected_ids & returned_set
            total_expected += len(expected_ids)
            total_found += len(found)
            total_hits += len(hits)
            valid_for_case = sum(self._hit_has_valid_provenance(hit) for hit in hits)
            valid_hits += valid_for_case

            case_results.append(
                CaseEvaluation(
                    case_id=case.case_id,
                    query=case.query,
                    expected_evidence_ids=tuple(sorted(expected_ids)),
                    returned_evidence_ids=returned_ids,
                    unresolved_targets=tuple(unresolved),
                    hit=bool(found),
                    target_recall=(len(found) / len(expected_ids) if expected_ids else 0.0),
                    provenance_validity=(valid_for_case / len(hits) if hits else 1.0),
                )
            )

        case_count = len(case_results)
        return EvaluationResult(
            suite=suite.name,
            build_id=str(build["build_id"]),
            k=k,
            cases=case_count,
            hit_rate_at_k=(sum(case.hit for case in case_results) / case_count if case_count else 0.0),
            target_recall_at_k=(total_found / total_expected if total_expected else 0.0),
            provenance_validity=(valid_hits / total_hits if total_hits else 1.0),
            unresolved_target_count=unresolved_count,
            case_results=tuple(case_results),
        )
