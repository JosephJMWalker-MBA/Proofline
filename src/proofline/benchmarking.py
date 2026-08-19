"""Deterministic benchmark-case generation from evidence, not retrieval results.

The pool builder is intentionally retrieval-blind. It derives candidate questions and exact
expected targets directly from preserved evidence, source metadata, and structured facts. A
candidate pool should be frozen before it is scored so the benchmark does not become a list of
queries selected because the current retrieval implementation already succeeds on them.

An optional source-role policy can restrict longitudinal benchmark targets to publisher/profile-
defined canonical evidence while leaving discovery/support artifacts preserved in the corpus.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .benchmark_sources import BenchmarkSourcePolicy
from .hashing import sha256_text
from .storage import ProoflineStore
from .structured import StructuredIndex

_POOL_METHOD = "proofline-retrieval-benchmark-pool/v1"
_POOL_METHOD_SOURCE_POLICY = "proofline-retrieval-benchmark-pool/v2"
_EVAL_SCHEMA = "proofline-retrieval-eval/v2"

_PHRASE_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&'’.-]{2,})(?:\s+(?:[A-Z][A-Za-z0-9&'’.-]{2,})){1,3}\b"
)
_SPACE_RE = re.compile(r"\s+")
_STOP_PHRASES = {
    "board of control",
    "city council",
    "city of canton",
    "state of ohio",
    "united states",
}


class RetrievalBenchmarkPoolBuilder:
    """Build a deterministic v2 benchmark candidate pool without executing retrieval."""

    def __init__(
        self,
        state_dir: str | Path = ".proofline",
        *,
        source_policy: BenchmarkSourcePolicy | None = None,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self.structured = StructuredIndex(self.state_dir)
        self.source_policy = source_policy

    def _source_uris(self, artifact_id: str) -> tuple[str, ...]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT s.source_uri
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.artifact_id = ?
                ORDER BY s.source_uri
                """,
                (artifact_id,),
            ).fetchall()
        return tuple(str(row["source_uri"]) for row in rows)

    def _source_uri(self, artifact_id: str) -> str | None:
        source_uris = self._source_uris(artifact_id)
        if self.source_policy is None:
            return source_uris[0] if source_uris else None
        canonical = [
            source_uri
            for source_uri in source_uris
            if self.source_policy.classify(source_uri) == "canonical"
        ]
        return canonical[0] if canonical else None

    def _evidence(self) -> list[dict]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    eu.evidence_id,
                    eu.artifact_id,
                    eu.locator,
                    a.sha256 AS artifact_sha256,
                    best.extracted_text
                FROM evidence_units eu
                JOIN artifacts a ON a.artifact_id = eu.artifact_id
                JOIN evidence_extractions best
                  ON best.extraction_id = (
                    SELECT ee.extraction_id
                    FROM evidence_extractions ee
                    WHERE ee.evidence_id = eu.evidence_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                             ee.occurred_at DESC,
                             ee.rowid DESC
                    LIMIT 1
                  )
                WHERE best.extracted_text IS NOT NULL
                ORDER BY eu.evidence_id
                """
            ).fetchall()
        records: list[dict] = []
        for row in rows:
            text = str(row["extracted_text"])
            if not text.strip():
                continue
            artifact_id = str(row["artifact_id"])
            source_uri = self._source_uri(artifact_id)
            # With a source policy, absence of a canonical source mapping is an intentional
            # exclusion from benchmark target populations, not missing corpus provenance.
            if self.source_policy is not None and source_uri is None:
                continue
            if source_uri is None:
                continue
            records.append(
                {
                    "evidence_id": str(row["evidence_id"]),
                    "artifact_id": artifact_id,
                    "locator": str(row["locator"]),
                    "artifact_sha256": str(row["artifact_sha256"]),
                    "source_uri": source_uri,
                    "text": text,
                }
            )
        return records

    def _target(self, record: dict) -> dict:
        return {
            "source_uri": record["source_uri"],
            "locator": record["locator"],
            "artifact_sha256": record["artifact_sha256"],
        }

    @staticmethod
    def _case_id(kind: str, signature: str) -> str:
        return f"{kind}-{sha256_text(kind + ':' + signature)[:12]}"

    @staticmethod
    def _stable_select(items: list[dict], *, key, limit: int) -> list[dict]:
        return sorted(items, key=lambda item: sha256_text(str(key(item))))[:limit]

    def _lexical_phrase_cases(
        self,
        records: list[dict],
        *,
        max_per_kind: int,
        max_targets: int,
    ) -> list[dict]:
        evidence_by_id = {record["evidence_id"]: record for record in records}
        phrase_display: dict[str, str] = {}
        phrase_evidence: dict[str, set[str]] = defaultdict(set)

        for record in records:
            seen: set[str] = set()
            for match in _PHRASE_RE.finditer(record["text"]):
                display = _SPACE_RE.sub(" ", match.group(0)).strip()
                normalized = display.casefold()
                if normalized in _STOP_PHRASES or len(normalized) < 7:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                phrase_display.setdefault(normalized, display)
                phrase_evidence[normalized].add(record["evidence_id"])

        unique: list[dict] = []
        cross: list[dict] = []
        for normalized, evidence_ids in phrase_evidence.items():
            if not (1 <= len(evidence_ids) <= max_targets):
                continue
            targets = [self._target(evidence_by_id[evidence_id]) for evidence_id in sorted(evidence_ids)]
            display = phrase_display[normalized]
            payload = {
                "case_id": self._case_id("lexical-entity", normalized),
                "mode": "lexical",
                "query": display,
                "expected": targets,
                "selection_kind": (
                    "lexical_entity_unique" if len(evidence_ids) == 1 else "lexical_entity_cross"
                ),
            }
            (unique if len(evidence_ids) == 1 else cross).append(payload)

        selected_unique = self._stable_select(
            unique, key=lambda item: item["query"].casefold(), limit=max_per_kind
        )
        selected_cross = self._stable_select(
            cross, key=lambda item: item["query"].casefold(), limit=max_per_kind
        )
        return selected_unique + selected_cross

    def _native_identifier_cases(
        self,
        records: list[dict],
        *,
        max_per_kind: int,
        max_targets: int,
    ) -> list[dict]:
        records_by_artifact: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            records_by_artifact[record["artifact_id"]].append(record)

        by_native: dict[str, set[str]] = defaultdict(set)
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT ss.native_identifier, ss.artifact_id, s.source_uri
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.native_identifier IS NOT NULL AND TRIM(ss.native_identifier) != ''
                ORDER BY ss.native_identifier, ss.artifact_id, s.source_uri
                """
            ).fetchall()
        for row in rows:
            source_uri = str(row["source_uri"])
            if self.source_policy is not None and self.source_policy.classify(source_uri) != "canonical":
                continue
            native = str(row["native_identifier"])
            artifact_id = str(row["artifact_id"])
            for record in records_by_artifact.get(artifact_id, ()):  # canonical searchable evidence only
                by_native[native].add(record["evidence_id"])

        evidence_by_id = {record["evidence_id"]: record for record in records}
        candidates: list[dict] = []
        for native, evidence_ids in by_native.items():
            if not (1 <= len(evidence_ids) <= max_targets):
                continue
            candidates.append(
                {
                    "case_id": self._case_id("native-id", native),
                    "mode": "native_identifier",
                    "query": native,
                    "expected": [
                        self._target(evidence_by_id[evidence_id])
                        for evidence_id in sorted(evidence_ids)
                    ],
                    "selection_kind": "native_identifier",
                }
            )
        return self._stable_select(candidates, key=lambda item: item["query"], limit=max_per_kind)

    def _structured_cases(
        self,
        records: list[dict],
        *,
        max_per_kind: int,
        max_targets: int,
    ) -> list[dict]:
        build = self.structured.current_build()
        if build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")
        evidence_by_id = {record["evidence_id"]: record for record in records}
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT fact_type, normalized_text, numeric_value, evidence_id
                FROM evidence_facts
                WHERE build_id = ? AND normalized_text IS NOT NULL
                ORDER BY fact_type, normalized_text, evidence_id
                """,
                (build["build_id"],),
            ).fetchall()

        grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
        numeric: dict[tuple[str, str], float] = {}
        for row in rows:
            fact_type = str(row["fact_type"])
            normalized = str(row["normalized_text"])
            evidence_id = str(row["evidence_id"])
            if evidence_id not in evidence_by_id:
                continue
            key = (fact_type, normalized)
            grouped[key].add(evidence_id)
            if row["numeric_value"] is not None:
                numeric[key] = float(row["numeric_value"])

        by_kind: dict[str, list[dict]] = defaultdict(list)
        for (fact_type, normalized), evidence_ids in grouped.items():
            if not (1 <= len(evidence_ids) <= max_targets):
                continue
            targets = [self._target(evidence_by_id[evidence_id]) for evidence_id in sorted(evidence_ids)]

            if fact_type == "money":
                value = numeric.get((fact_type, normalized))
                if value is None:
                    continue
                kind = "money_exact"
                by_kind[kind].append(
                    {
                        "case_id": self._case_id("money", normalized),
                        "mode": "money",
                        "minimum": value,
                        "maximum": value,
                        "expected": targets,
                        "selection_kind": kind,
                    }
                )
            elif fact_type == "date":
                kind = "date_exact"
                by_kind[kind].append(
                    {
                        "case_id": self._case_id("date", normalized),
                        "mode": "date",
                        "start": normalized,
                        "end": normalized,
                        "expected": targets,
                        "selection_kind": kind,
                    }
                )
            elif fact_type == "identifier":
                kind = "content_identifier"
                by_kind[kind].append(
                    {
                        "case_id": self._case_id("identifier", normalized),
                        "mode": "identifier",
                        "query": normalized,
                        "expected": targets,
                        "selection_kind": kind,
                    }
                )

        selected: list[dict] = []
        for kind in ("money_exact", "date_exact", "content_identifier"):
            selected.extend(
                self._stable_select(
                    by_kind.get(kind, []),
                    key=lambda item: item.get("query") or item.get("start") or item.get("minimum"),
                    limit=max_per_kind,
                )
            )
        return selected

    def _negative_controls(self, records: list[dict]) -> list[dict]:
        text = "\n".join(record["text"].casefold() for record in records)
        lexical = "zzprooflinebenchmarkmissingzz"
        while lexical.casefold() in text:
            lexical += "z"

        with self.store.connection() as connection:
            native_rows = connection.execute(
                """
                SELECT DISTINCT ss.native_identifier, s.source_uri
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.native_identifier IS NOT NULL
                """
            ).fetchall()
            facts = connection.execute(
                """
                SELECT fact_type, normalized_text, numeric_value, evidence_id
                FROM evidence_facts
                WHERE build_id = (
                    SELECT build_id FROM structured_index_builds
                    ORDER BY built_at DESC, rowid DESC LIMIT 1
                )
                """
            ).fetchall()

        native_values = {
            str(row["native_identifier"]).casefold()
            for row in native_rows
            if self.source_policy is None
            or self.source_policy.classify(str(row["source_uri"])) == "canonical"
        }
        evidence_ids = {record["evidence_id"] for record in records}
        relevant_facts = [row for row in facts if str(row["evidence_id"]) in evidence_ids]

        missing_native = "__proofline_missing_native_id__"
        while missing_native.casefold() in native_values:
            missing_native += "x"

        identifiers = {
            str(row["normalized_text"]).casefold()
            for row in relevant_facts
            if row["fact_type"] == "identifier" and row["normalized_text"] is not None
        }
        missing_identifier = "__proofline_missing_identifier__"
        while missing_identifier.casefold() in identifiers:
            missing_identifier += "x"

        money_values = [
            float(row["numeric_value"])
            for row in relevant_facts
            if row["fact_type"] == "money" and row["numeric_value"] is not None
        ]
        max_money = max(money_values, default=0.0)
        missing_money = max_money + max(abs(max_money) * 2.0, 1_000_000.0) + 12345.67

        date_values = {
            str(row["normalized_text"])
            for row in relevant_facts
            if row["fact_type"] == "date" and row["normalized_text"] is not None
        }
        year = 2099
        missing_date = f"{year:04d}-12-31"
        while missing_date in date_values and year < 9999:
            year += 1
            missing_date = f"{year:04d}-12-31"

        return [
            {
                "case_id": self._case_id("negative-lexical", lexical),
                "mode": "lexical",
                "query": lexical,
                "expect_empty": True,
                "expected": [],
                "selection_kind": "negative_control",
            },
            {
                "case_id": self._case_id("negative-native", missing_native),
                "mode": "native_identifier",
                "query": missing_native,
                "expect_empty": True,
                "expected": [],
                "selection_kind": "negative_control",
            },
            {
                "case_id": self._case_id("negative-identifier", missing_identifier),
                "mode": "identifier",
                "query": missing_identifier,
                "expect_empty": True,
                "expected": [],
                "selection_kind": "negative_control",
            },
            {
                "case_id": self._case_id("negative-money", str(missing_money)),
                "mode": "money",
                "minimum": missing_money,
                "maximum": missing_money,
                "expect_empty": True,
                "expected": [],
                "selection_kind": "negative_control",
            },
            {
                "case_id": self._case_id("negative-date", missing_date),
                "mode": "date",
                "start": missing_date,
                "end": missing_date,
                "expect_empty": True,
                "expected": [],
                "selection_kind": "negative_control",
            },
        ]

    def build(
        self,
        *,
        name: str = "Proofline R1 deterministic real-corpus benchmark candidate pool",
        max_per_kind: int = 6,
        max_targets: int = 5,
    ) -> dict:
        if max_per_kind < 1:
            raise ValueError("max_per_kind must be positive")
        if max_targets < 1:
            raise ValueError("max_targets must be positive")

        records = self._evidence()
        if not records:
            raise RuntimeError("no substantive evidence is available for benchmark generation")

        cases: list[dict] = []
        cases.extend(
            self._lexical_phrase_cases(records, max_per_kind=max_per_kind, max_targets=max_targets)
        )
        cases.extend(
            self._native_identifier_cases(records, max_per_kind=max_per_kind, max_targets=max_targets)
        )
        cases.extend(
            self._structured_cases(records, max_per_kind=max_per_kind, max_targets=max_targets)
        )
        cases.extend(self._negative_controls(records))

        kind_counts: dict[str, int] = defaultdict(int)
        for case in cases:
            kind_counts[str(case["selection_kind"])] += 1

        selection = {
            "method": _POOL_METHOD_SOURCE_POLICY if self.source_policy else _POOL_METHOD,
            "retrieval_results_consulted": False,
            "evidence_units_considered": len(records),
            "max_per_kind": max_per_kind,
            "max_targets_per_case": max_targets,
            "kind_counts": dict(sorted(kind_counts.items())),
            "note": (
                "Cases are derived from evidence/source/structured indexes only. "
                "Freeze this pool before running retrieval evaluation."
            ),
        }
        if self.source_policy is not None:
            selection["source_policy"] = self.source_policy.to_dict()
            selection["target_source_role"] = "canonical"

        return {
            "schema": _EVAL_SCHEMA,
            "name": name,
            "selection": selection,
            "cases": cases,
        }
