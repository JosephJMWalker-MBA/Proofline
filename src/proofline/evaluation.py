"""Retrieval evaluation against explicit evidence targets.

Version 1 remains supported for the original lexical-only benchmark. Version 2 adds
explicit retrieval modes, negative/no-result cases, and failure classification so a
real-corpus benchmark can measure deterministic retrieval honestly before Proofline
considers semantic/vector search.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .search import SearchIndex
from .storage import ProoflineStore
from .structured import StructuredIndex

_EVAL_SCHEMA_V1 = "proofline-retrieval-eval/v1"
_EVAL_SCHEMA_V2 = "proofline-retrieval-eval/v2"
_ALLOWED_MODES = {"lexical", "native_identifier", "identifier", "money", "date"}


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
    mode: str = "lexical"
    expect_empty: bool = False
    minimum: float | None = None
    maximum: float | None = None
    start: str | None = None
    end: str | None = None

    @property
    def query_description(self) -> str:
        if self.mode in {"lexical", "native_identifier", "identifier"}:
            return self.query
        if self.mode == "money":
            return f"money(min={self.minimum!r}, max={self.maximum!r})"
        if self.mode == "date":
            return f"date(start={self.start!r}, end={self.end!r})"
        return self.query


@dataclass(frozen=True, slots=True)
class RetrievalSuite:
    name: str
    cases: tuple[RetrievalCase, ...]
    schema: str = _EVAL_SCHEMA_V1


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
    mode: str = "lexical"
    expect_empty: bool = False
    expectation_met: bool = False
    failure_class: str | None = None

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
    schema: str = _EVAL_SCHEMA_V1
    structured_build_id: str | None = None
    expectation_accuracy: float = 0.0
    negative_case_count: int = 0
    negative_accuracy: float = 1.0
    failure_counts: tuple[dict, ...] = ()
    mode_metrics: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["case_results"] = [item.to_dict() for item in self.case_results]
        data["failure_counts"] = list(self.failure_counts)
        data["mode_metrics"] = list(self.mode_metrics)
        return data


def _targets(case_id: str, raw_expected: object, *, allow_empty: bool) -> tuple[ExpectedTarget, ...]:
    if not isinstance(raw_expected, list):
        raise ValueError(f"expected targets must be a list for {case_id}")
    if not raw_expected and not allow_empty:
        raise ValueError(f"expected targets must be non-empty for {case_id}")

    targets: list[ExpectedTarget] = []
    for target in raw_expected:
        if not isinstance(target, dict):
            raise ValueError(f"expected target must be an object for {case_id}")
        source_uri = target.get("source_uri")
        locator = target.get("locator")
        artifact_sha256 = target.get("artifact_sha256")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError(f"source_uri missing for {case_id}")
        if not isinstance(locator, str) or not locator:
            raise ValueError(f"locator missing for {case_id}")
        if artifact_sha256 is not None and (
            not isinstance(artifact_sha256, str) or not artifact_sha256
        ):
            raise ValueError(f"artifact_sha256 must be a non-empty string for {case_id}")
        targets.append(
            ExpectedTarget(
                source_uri=source_uri,
                locator=locator,
                artifact_sha256=artifact_sha256,
            )
        )
    return tuple(targets)


def _number(value: object, *, field: str, case_id: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric for {case_id}")
    return float(value)


def load_retrieval_suite(path: str | Path) -> RetrievalSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = payload.get("schema")
    if schema not in {_EVAL_SCHEMA_V1, _EVAL_SCHEMA_V2}:
        raise ValueError(
            f"evaluation schema must be {_EVAL_SCHEMA_V1!r} or {_EVAL_SCHEMA_V2!r}"
        )
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
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case_id must be non-empty")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)

        if schema == _EVAL_SCHEMA_V1:
            query = item.get("query")
            if not isinstance(query, str) or not query:
                raise ValueError(f"query must be non-empty for {case_id}")
            cases.append(
                RetrievalCase(
                    case_id=case_id,
                    query=query,
                    expected=_targets(case_id, item.get("expected"), allow_empty=False),
                )
            )
            continue

        mode = item.get("mode", "lexical")
        if mode not in _ALLOWED_MODES:
            raise ValueError(f"unsupported retrieval mode {mode!r} for {case_id}")
        expect_empty = item.get("expect_empty", False)
        if not isinstance(expect_empty, bool):
            raise ValueError(f"expect_empty must be boolean for {case_id}")
        expected = _targets(case_id, item.get("expected", []), allow_empty=expect_empty)
        if expect_empty and expected:
            raise ValueError(f"negative case {case_id} cannot also declare positive targets")

        query = item.get("query", "")
        if mode in {"lexical", "native_identifier", "identifier"}:
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"query must be non-empty for {case_id} in mode {mode}")
            query = query.strip()
        elif query not in (None, ""):
            raise ValueError(f"query is not used by structured mode {mode} for {case_id}")
        else:
            query = ""

        minimum = _number(item.get("minimum"), field="minimum", case_id=case_id)
        maximum = _number(item.get("maximum"), field="maximum", case_id=case_id)
        start = item.get("start")
        end = item.get("end")

        if mode == "money":
            if minimum is None and maximum is None:
                raise ValueError(f"money case {case_id} needs minimum and/or maximum")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"minimum cannot exceed maximum for {case_id}")
        elif minimum is not None or maximum is not None:
            raise ValueError(f"minimum/maximum only apply to money mode for {case_id}")

        if mode == "date":
            if start is None and end is None:
                raise ValueError(f"date case {case_id} needs start and/or end")
            if start is not None and (not isinstance(start, str) or not start):
                raise ValueError(f"start must be a non-empty string for {case_id}")
            if end is not None and (not isinstance(end, str) or not end):
                raise ValueError(f"end must be a non-empty string for {case_id}")
        elif start is not None or end is not None:
            raise ValueError(f"start/end only apply to date mode for {case_id}")

        cases.append(
            RetrievalCase(
                case_id=case_id,
                query=query,
                expected=expected,
                mode=mode,
                expect_empty=expect_empty,
                minimum=minimum,
                maximum=maximum,
                start=start,
                end=end,
            )
        )

    return RetrievalSuite(name=name, cases=tuple(cases), schema=str(schema))


class RetrievalEvaluator:
    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self.index = SearchIndex(self.state_dir)
        self.structured = StructuredIndex(self.state_dir)

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

    @staticmethod
    def _unique_evidence_ids(hits) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for hit in hits:
            evidence_id = str(hit.evidence_id)
            if evidence_id not in seen:
                seen.add(evidence_id)
                ordered.append(evidence_id)
        return tuple(ordered)

    def _execute(self, case: RetrievalCase, *, k: int):
        if case.mode == "lexical":
            return self.index.search(case.query, limit=k)
        if case.mode == "native_identifier":
            return self.index.lookup_native_identifier(case.query)[:k]
        if case.mode == "identifier":
            return self.structured.identifier(case.query, limit=k)
        if case.mode == "money":
            return self.structured.money(minimum=case.minimum, maximum=case.maximum, limit=k)
        if case.mode == "date":
            return self.structured.dates(start=case.start, end=case.end, limit=k)
        raise AssertionError(f"unhandled retrieval mode: {case.mode}")

    @staticmethod
    def _failure_class(
        *,
        expect_empty: bool,
        unresolved: tuple[dict, ...],
        expected_ids: set[str],
        returned_ids: tuple[str, ...],
        found: set[str],
        provenance_validity: float,
    ) -> str | None:
        if unresolved:
            return "unresolved_target"
        if expect_empty:
            return None if not returned_ids else "unexpected_results"
        if not found:
            return "miss_all_targets"
        if len(found) < len(expected_ids):
            return "partial_target_recall"
        if provenance_validity < 1.0:
            return "invalid_provenance"
        return None

    @staticmethod
    def _mode_metrics(case_results: tuple[CaseEvaluation, ...]) -> tuple[dict, ...]:
        metrics: list[dict] = []
        for mode in sorted({case.mode for case in case_results}):
            rows = [case for case in case_results if case.mode == mode]
            positives = [case for case in rows if not case.expect_empty]
            negatives = [case for case in rows if case.expect_empty]
            metrics.append(
                {
                    "mode": mode,
                    "cases": len(rows),
                    "expectation_accuracy": sum(case.expectation_met for case in rows) / len(rows),
                    "positive_cases": len(positives),
                    "positive_hit_rate": (
                        sum(case.hit for case in positives) / len(positives) if positives else 1.0
                    ),
                    "mean_target_recall": (
                        sum(case.target_recall for case in positives) / len(positives)
                        if positives
                        else 1.0
                    ),
                    "negative_cases": len(negatives),
                    "negative_accuracy": (
                        sum(case.expectation_met for case in negatives) / len(negatives)
                        if negatives
                        else 1.0
                    ),
                    "provenance_validity": (
                        sum(case.provenance_validity for case in rows) / len(rows) if rows else 1.0
                    ),
                }
            )
        return tuple(metrics)

    def run(self, suite: RetrievalSuite, *, k: int = 5) -> EvaluationResult:
        if k < 1:
            raise ValueError("k must be positive")

        modes = {case.mode for case in suite.cases}
        lexical_build = self.index.current_build()
        structured_build = self.structured.current_build()
        if modes & {"lexical", "native_identifier"} and lexical_build is None:
            raise RuntimeError("search index has not been built; run `proofline index` first")
        if modes & {"identifier", "money", "date"} and structured_build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")

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

            hits = self._execute(case, k=k)
            returned_ids = self._unique_evidence_ids(hits)
            returned_set = set(returned_ids)
            found = expected_ids & returned_set
            valid_for_case = sum(self._hit_has_valid_provenance(hit) for hit in hits)
            provenance = valid_for_case / len(hits) if hits else 1.0

            if not case.expect_empty:
                total_expected += len(expected_ids)
                total_found += len(found)
            total_hits += len(hits)
            valid_hits += valid_for_case

            if case.expect_empty:
                hit = not returned_ids
                target_recall = 1.0 if not returned_ids else 0.0
                expectation_met = not returned_ids
            else:
                hit = bool(found)
                target_recall = len(found) / len(expected_ids) if expected_ids else 0.0
                expectation_met = bool(expected_ids) and len(found) == len(expected_ids)

            unresolved_tuple = tuple(unresolved)
            failure_class = self._failure_class(
                expect_empty=case.expect_empty,
                unresolved=unresolved_tuple,
                expected_ids=expected_ids,
                returned_ids=returned_ids,
                found=found,
                provenance_validity=provenance,
            )
            case_results.append(
                CaseEvaluation(
                    case_id=case.case_id,
                    query=case.query_description,
                    expected_evidence_ids=tuple(sorted(expected_ids)),
                    returned_evidence_ids=returned_ids,
                    unresolved_targets=unresolved_tuple,
                    hit=hit,
                    target_recall=target_recall,
                    provenance_validity=provenance,
                    mode=case.mode,
                    expect_empty=case.expect_empty,
                    expectation_met=expectation_met,
                    failure_class=failure_class,
                )
            )

        results_tuple = tuple(case_results)
        positives = [case for case in results_tuple if not case.expect_empty]
        negatives = [case for case in results_tuple if case.expect_empty]
        failure_counter: dict[str, int] = {}
        for case in results_tuple:
            if case.failure_class:
                failure_counter[case.failure_class] = failure_counter.get(case.failure_class, 0) + 1

        case_count = len(results_tuple)
        return EvaluationResult(
            suite=suite.name,
            build_id=str(lexical_build["build_id"]) if lexical_build else "",
            k=k,
            cases=case_count,
            hit_rate_at_k=(
                sum(case.hit for case in positives) / len(positives) if positives else 1.0
            ),
            target_recall_at_k=(total_found / total_expected if total_expected else 1.0),
            provenance_validity=(valid_hits / total_hits if total_hits else 1.0),
            unresolved_target_count=unresolved_count,
            case_results=results_tuple,
            schema=suite.schema,
            structured_build_id=(
                str(structured_build["build_id"]) if structured_build is not None else None
            ),
            expectation_accuracy=(
                sum(case.expectation_met for case in results_tuple) / case_count
                if case_count
                else 1.0
            ),
            negative_case_count=len(negatives),
            negative_accuracy=(
                sum(case.expectation_met for case in negatives) / len(negatives)
                if negatives
                else 1.0
            ),
            failure_counts=tuple(
                {"failure_class": key, "count": failure_counter[key]}
                for key in sorted(failure_counter)
            ),
            mode_metrics=self._mode_metrics(results_tuple),
        )
