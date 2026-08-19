"""Disposable deterministic segmentation of preferred Silver evidence.

Segments are parsing/index conveniences, not new source evidence. Every segment retains the
original evidence unit and exact character span that produced it.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .hashing import sha256_text, stable_id
from .storage import ProoflineStore

_SEGMENTATION_SCHEMA = "proofline-segmentation-plan/v1"
_SEGMENTER_VERSION = "proofline-segments/v1"

_SEGMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS segment_index_builds (
    build_id TEXT PRIMARY KEY,
    built_at TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    rule_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    segment_count INTEGER NOT NULL,
    segmenter_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_segments (
    segment_id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    segment_type TEXT NOT NULL,
    anchor_text TEXT NOT NULL,
    normalized_anchor TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_segments_build_evidence
ON evidence_segments(build_id, evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_segments_build_anchor
ON evidence_segments(build_id, segment_type, normalized_anchor);
CREATE INDEX IF NOT EXISTS idx_evidence_segments_build_hash
ON evidence_segments(build_id, segment_type, text_sha256);
"""


@dataclass(frozen=True, slots=True)
class SegmentationRule:
    name: str
    source_name_regex: str
    anchor_regex: str
    segment_type: str = "record_item"
    min_chars: int = 40


@dataclass(frozen=True, slots=True)
class SegmentationPlan:
    name: str
    rules: tuple[SegmentationRule, ...]
    schema: str = _SEGMENTATION_SCHEMA


@dataclass(frozen=True, slots=True)
class EvidenceSegment:
    rule_name: str
    segment_type: str
    anchor_text: str
    normalized_anchor: str
    raw_text: str
    normalized_text: str
    text_sha256: str
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class SegmentBuildResult:
    build_id: str
    built_at: str
    plan_name: str
    plan_sha256: str
    rule_count: int
    evidence_count: int
    segment_count: int
    segmenter_version: str = _SEGMENTER_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SegmentHit:
    build_id: str
    segment_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    rule_name: str
    segment_type: str
    anchor_text: str
    normalized_anchor: str
    raw_text: str
    normalized_text: str
    text_sha256: str
    char_start: int
    char_end: int
    sources: tuple[dict, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = list(self.sources)
        return data


@dataclass(frozen=True, slots=True)
class RepeatedSegmentGroup:
    segment_type: str
    text_sha256: str
    normalized_text: str
    occurrence_count: int
    artifact_count: int
    occurrences: tuple[SegmentHit, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurrences"] = [item.to_dict() for item in self.occurrences]
        return data


def _compile_rule(rule: SegmentationRule) -> tuple[re.Pattern[str], re.Pattern[str]]:
    try:
        source_pattern = re.compile(rule.source_name_regex)
    except re.error as exc:
        raise ValueError(f"invalid source_name_regex for rule {rule.name!r}: {exc}") from exc
    try:
        anchor_pattern = re.compile(rule.anchor_regex, re.MULTILINE)
    except re.error as exc:
        raise ValueError(f"invalid anchor_regex for rule {rule.name!r}: {exc}") from exc
    if "anchor" not in anchor_pattern.groupindex:
        raise ValueError(f"anchor_regex for rule {rule.name!r} must define named group 'anchor'")
    if anchor_pattern.search("") is not None:
        raise ValueError(f"anchor_regex for rule {rule.name!r} must not match empty text")
    return source_pattern, anchor_pattern


def _canonical_plan_payload(plan: SegmentationPlan) -> dict:
    return {
        "schema": plan.schema,
        "name": plan.name,
        "rules": [asdict(rule) for rule in plan.rules],
    }


def segmentation_plan_sha256(plan: SegmentationPlan) -> str:
    serialized = json.dumps(_canonical_plan_payload(plan), sort_keys=True, separators=(",", ":"))
    return sha256_text(serialized)


def segmentation_rule_sha256(rule: SegmentationRule) -> str:
    """Hash the semantics that define one segmenting rule independent of plan neighbors."""
    serialized = json.dumps(
        {
            "schema": _SEGMENTATION_SCHEMA,
            "segmenter_version": _SEGMENTER_VERSION,
            "rule": asdict(rule),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(serialized)


def load_segmentation_plan(path: str | Path) -> SegmentationPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _SEGMENTATION_SCHEMA:
        raise ValueError(f"segmentation schema must be {_SEGMENTATION_SCHEMA!r}")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("segmentation plan name must be a non-empty string")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("segmentation plan rules must be a non-empty list")

    rules: list[SegmentationRule] = []
    seen_names: set[str] = set()
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("each segmentation rule must be an object")
        rule_name = raw.get("name")
        source_name_regex = raw.get("source_name_regex")
        anchor_regex = raw.get("anchor_regex")
        segment_type = raw.get("segment_type", "record_item")
        min_chars = raw.get("min_chars", 40)
        if not isinstance(rule_name, str) or not rule_name.strip():
            raise ValueError("segmentation rule name must be a non-empty string")
        if rule_name in seen_names:
            raise ValueError(f"duplicate segmentation rule name: {rule_name}")
        seen_names.add(rule_name)
        if not isinstance(source_name_regex, str) or not source_name_regex:
            raise ValueError(f"rule {rule_name!r} source_name_regex must be a non-empty string")
        if not isinstance(anchor_regex, str) or not anchor_regex:
            raise ValueError(f"rule {rule_name!r} anchor_regex must be a non-empty string")
        if not isinstance(segment_type, str) or not segment_type.strip():
            raise ValueError(f"rule {rule_name!r} segment_type must be a non-empty string")
        if not isinstance(min_chars, int) or min_chars < 1:
            raise ValueError(f"rule {rule_name!r} min_chars must be a positive integer")
        rule = SegmentationRule(
            name=rule_name,
            source_name_regex=source_name_regex,
            anchor_regex=anchor_regex,
            segment_type=segment_type,
            min_chars=min_chars,
        )
        _compile_rule(rule)
        rules.append(rule)
    return SegmentationPlan(name=name, rules=tuple(rules))


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def segment_text(text: str, rule: SegmentationRule) -> tuple[EvidenceSegment, ...]:
    """Split one evidence text at deterministic source-specific anchors.

    Text before the first anchor is intentionally ignored. Each emitted segment starts at an
    anchor and ends immediately before the next anchor in the same evidence unit.
    """
    _, anchor_pattern = _compile_rule(rule)
    matches = list(anchor_pattern.finditer(text))
    segments: list[EvidenceSegment] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        start, end = _trim_span(text, start, end)
        if end <= start:
            continue
        raw_text = text[start:end]
        normalized_text = " ".join(raw_text.split()).casefold()
        if len(normalized_text) < rule.min_chars:
            continue
        anchor_text = match.group("anchor").strip()
        normalized_anchor = " ".join(anchor_text.split()).casefold()
        segments.append(
            EvidenceSegment(
                rule_name=rule.name,
                segment_type=rule.segment_type,
                anchor_text=anchor_text,
                normalized_anchor=normalized_anchor,
                raw_text=raw_text,
                normalized_text=normalized_text,
                text_sha256=sha256_text(normalized_text),
                char_start=start,
                char_end=end,
            )
        )
    return tuple(segments)


class SegmentIndex:
    """Rebuildable source-profile segmentation over preferred Silver evidence."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        with self.store.connection() as connection:
            connection.executescript(_SEGMENT_SCHEMA)

    def _sources_for_artifact(self, artifact_id: str) -> tuple[dict, ...]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT s.source_id, s.source_uri, s.source_name, ss.native_identifier
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.artifact_id = ?
                ORDER BY s.source_uri
                """,
                (artifact_id,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def _source_names_for_artifact(self, artifact_id: str) -> tuple[str, ...]:
        return tuple(
            source["source_name"]
            for source in self._sources_for_artifact(artifact_id)
            if source.get("source_name")
        )

    def rebuild(self, plan: SegmentationPlan, *, batch_size: int = 1000) -> SegmentBuildResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        compiled = [(rule, *_compile_rule(rule)) for rule in plan.rules]
        rule_hashes = {rule.name: segmentation_rule_sha256(rule) for rule in plan.rules}
        build_id = f"segments:{uuid.uuid4()}"
        built_at = datetime.now(UTC).isoformat()
        plan_sha256 = segmentation_plan_sha256(plan)
        evidence_count = 0
        segment_count = 0
        source_cache: dict[str, tuple[str, ...]] = {}

        with self.store.connection() as connection:
            connection.execute("DELETE FROM evidence_segments")
            cursor = connection.execute(
                """
                SELECT eu.evidence_id, eu.artifact_id, eu.locator, best.extracted_text
                FROM evidence_units eu
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
                  AND TRIM(best.extracted_text) != ''
                ORDER BY eu.evidence_id
                """
            )
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    artifact_id = row["artifact_id"]
                    source_names = source_cache.get(artifact_id)
                    if source_names is None:
                        source_names = self._source_names_for_artifact(artifact_id)
                        source_cache[artifact_id] = source_names

                    matching_rules: list[SegmentationRule] = []
                    for rule, source_pattern, _ in compiled:
                        if any(source_pattern.search(name) for name in source_names):
                            matching_rules.append(rule)
                    if not matching_rules:
                        continue
                    evidence_count += 1

                    for rule in matching_rules:
                        for segment in segment_text(row["extracted_text"], rule):
                            segment_id = stable_id(
                                "segment",
                                _SEGMENTER_VERSION,
                                rule_hashes[rule.name],
                                row["evidence_id"],
                                str(segment.char_start),
                                str(segment.char_end),
                                segment.text_sha256,
                            )
                            connection.execute(
                                """
                                INSERT INTO evidence_segments(
                                    segment_id, build_id, evidence_id, artifact_id, locator,
                                    rule_name, segment_type, anchor_text, normalized_anchor,
                                    raw_text, normalized_text, text_sha256, char_start, char_end
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    segment_id,
                                    build_id,
                                    row["evidence_id"],
                                    artifact_id,
                                    row["locator"],
                                    segment.rule_name,
                                    segment.segment_type,
                                    segment.anchor_text,
                                    segment.normalized_anchor,
                                    segment.raw_text,
                                    segment.normalized_text,
                                    segment.text_sha256,
                                    segment.char_start,
                                    segment.char_end,
                                ),
                            )
                            segment_count += 1

            connection.execute(
                """
                INSERT INTO segment_index_builds(
                    build_id, built_at, plan_name, plan_sha256, rule_count,
                    evidence_count, segment_count, segmenter_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    build_id,
                    built_at,
                    plan.name,
                    plan_sha256,
                    len(plan.rules),
                    evidence_count,
                    segment_count,
                    _SEGMENTER_VERSION,
                ),
            )

        return SegmentBuildResult(
            build_id=build_id,
            built_at=built_at,
            plan_name=plan.name,
            plan_sha256=plan_sha256,
            rule_count=len(plan.rules),
            evidence_count=evidence_count,
            segment_count=segment_count,
        )

    def current_build(self) -> dict | None:
        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM segment_index_builds
                ORDER BY built_at DESC, rowid DESC
                LIMIT 1
                """,
            ).fetchone()
        return dict(row) if row else None

    def _hit(self, row) -> SegmentHit:
        return SegmentHit(
            build_id=row["build_id"],
            segment_id=row["segment_id"],
            evidence_id=row["evidence_id"],
            artifact_id=row["artifact_id"],
            locator=row["locator"],
            rule_name=row["rule_name"],
            segment_type=row["segment_type"],
            anchor_text=row["anchor_text"],
            normalized_anchor=row["normalized_anchor"],
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            text_sha256=row["text_sha256"],
            char_start=int(row["char_start"]),
            char_end=int(row["char_end"]),
            sources=self._sources_for_artifact(row["artifact_id"]),
        )

    def anchor(self, value: str, *, segment_type: str | None = None, limit: int = 100) -> list[SegmentHit]:
        normalized = " ".join(value.split()).casefold()
        if not normalized:
            raise ValueError("anchor cannot be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        build = self.current_build()
        if build is None:
            raise RuntimeError("segment index has not been built")
        clauses = ["build_id = ?", "normalized_anchor = ?"]
        params: list[object] = [build["build_id"], normalized]
        if segment_type is not None:
            clauses.append("segment_type = ?")
            params.append(segment_type)
        params.append(limit)
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evidence_segments
                WHERE {' AND '.join(clauses)}
                ORDER BY artifact_id, locator, char_start
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._hit(row) for row in rows]

    def repeated(self, *, min_artifacts: int = 2, limit: int = 100) -> list[RepeatedSegmentGroup]:
        """Return exact normalized segments repeated across distinct artifacts.

        Repetition is descriptive only. It can reflect normal agenda carry-forward, a historical
        version, boilerplate, or an item that genuinely recurs across meetings.
        """
        if min_artifacts < 2:
            raise ValueError("min_artifacts must be at least 2")
        if limit < 1:
            raise ValueError("limit must be positive")
        build = self.current_build()
        if build is None:
            raise RuntimeError("segment index has not been built")
        with self.store.connection() as connection:
            groups = connection.execute(
                """
                SELECT
                    segment_type,
                    text_sha256,
                    MIN(normalized_text) AS normalized_text,
                    COUNT(*) AS occurrence_count,
                    COUNT(DISTINCT artifact_id) AS artifact_count
                FROM evidence_segments
                WHERE build_id = ?
                GROUP BY segment_type, text_sha256
                HAVING COUNT(DISTINCT artifact_id) >= ?
                ORDER BY artifact_count DESC, occurrence_count DESC, text_sha256
                LIMIT ?
                """,
                (build["build_id"], min_artifacts, limit),
            ).fetchall()
            results: list[RepeatedSegmentGroup] = []
            for group in groups:
                rows = connection.execute(
                    """
                    SELECT * FROM evidence_segments
                    WHERE build_id = ? AND segment_type = ? AND text_sha256 = ?
                    ORDER BY artifact_id, locator, char_start
                    """,
                    (build["build_id"], group["segment_type"], group["text_sha256"]),
                ).fetchall()
                results.append(
                    RepeatedSegmentGroup(
                        segment_type=group["segment_type"],
                        text_sha256=group["text_sha256"],
                        normalized_text=group["normalized_text"],
                        occurrence_count=int(group["occurrence_count"]),
                        artifact_count=int(group["artifact_count"]),
                        occurrences=tuple(self._hit(row) for row in rows),
                    )
                )
        return results
