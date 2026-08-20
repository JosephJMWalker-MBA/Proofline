"""Deterministic structured indexing for dates, monetary values, and identifiers."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .hashing import stable_id
from .storage import ProoflineStore

_PARSER_VERSION_V1 = "proofline-structured/v1"
_PARSER_VERSION = "proofline-structured/v2"
_SUPPORTED_PARSER_VERSIONS = {_PARSER_VERSION_V1, _PARSER_VERSION}

_MONEY_RE_V1 = re.compile(
    r"(?<!\w)(?:(?P<usd>USD)\s*|(?P<dollar>\$)\s*)"
    r"(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?<!\w)(?:(?P<usd>USD)\s*|(?P<dollar>\$)\s*)"
    r"(?P<number>\d{1,3}(?:\s*,\s*\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?P<suffix>[A-Za-z]{1,4})?"
    r"(?!\w)",
    re.IGNORECASE,
)
_MONEY_MAGNITUDES = {
    "K": Decimal("1000"),
    "M": Decimal("1000000"),
    "MM": Decimal("1000000"),
    "B": Decimal("1000000000"),
    "BN": Decimal("1000000000"),
}
_ISO_DATE_RE = re.compile(
    r"\b(?P<year>19\d{2}|20\d{2})[-/](?P<month>0?[1-9]|1[0-2])[-/](?P<day>0?[1-9]|[12]\d|3[01])\b"
)
_US_DATE_RE = re.compile(
    r"\b(?P<month>0?[1-9]|1[0-2])/(?P<day>0?[1-9]|[12]\d|3[01])/(?P<year>19\d{2}|20\d{2})\b"
)
_MONTH_DATE_RE = re.compile(
    r"\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?[,]?\s+(?P<year>19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)
_FIELD_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")

_MONEY_FIELD_TOKENS = {
    "amount",
    "budget",
    "cost",
    "expenditure",
    "fee",
    "payment",
    "price",
    "spend",
    "total",
    "value",
}
_IDENTIFIER_FIELD_TOKENS = {
    "case",
    "contract",
    "docket",
    "id",
    "identifier",
    "invoice",
    "number",
    "permit",
    "record",
    "reference",
}
_DATE_FIELD_TOKENS = {
    "date",
    "dated",
    "effective",
    "issued",
    "received",
    "signed",
}

_STRUCTURED_SCHEMA = """
CREATE TABLE IF NOT EXISTS structured_index_builds (
    build_id TEXT PRIMARY KEY,
    built_at TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    fact_count INTEGER NOT NULL,
    parser_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_facts (
    fact_id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    field_name TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT,
    numeric_value REAL,
    unit TEXT,
    char_start INTEGER,
    char_end INTEGER
);

CREATE INDEX IF NOT EXISTS idx_evidence_facts_type_numeric
ON evidence_facts(build_id, fact_type, numeric_value);
CREATE INDEX IF NOT EXISTS idx_evidence_facts_type_text
ON evidence_facts(build_id, fact_type, normalized_text);
CREATE INDEX IF NOT EXISTS idx_evidence_facts_evidence
ON evidence_facts(build_id, evidence_id);
"""


@dataclass(frozen=True, slots=True)
class StructuredFact:
    fact_type: str
    raw_text: str
    normalized_text: str | None = None
    numeric_value: float | None = None
    unit: str | None = None
    field_name: str | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass(frozen=True, slots=True)
class StructuredBuildResult:
    build_id: str
    built_at: str
    evidence_count: int
    fact_count: int
    parser_version: str = _PARSER_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StructuredHit:
    build_id: str
    fact_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    fact_type: str
    field_name: str | None
    raw_text: str
    normalized_text: str | None
    numeric_value: float | None
    unit: str | None
    char_start: int | None
    char_end: int | None
    sources: tuple[dict, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = list(self.sources)
        return data


def _resolve_parser_version(parser_version: str | None) -> str:
    resolved = parser_version or _PARSER_VERSION
    if resolved not in _SUPPORTED_PARSER_VERSIONS:
        supported = ", ".join(sorted(_SUPPORTED_PARSER_VERSIONS))
        raise ValueError(f"unsupported structured parser version: {resolved}; expected one of {supported}")
    return resolved


def _normalize_field_name(name: str) -> tuple[str, set[str]]:
    normalized = _FIELD_NORMALIZE_RE.sub("_", name.casefold()).strip("_")
    tokens = {token for token in normalized.split("_") if token}
    return normalized, tokens


def _field_kind(name: str) -> str | None:
    normalized, tokens = _normalize_field_name(name)
    if normalized.endswith("_date") or tokens & _DATE_FIELD_TOKENS:
        return "date"
    if normalized.endswith("_id") or normalized.endswith("_number"):
        return "identifier"
    if tokens & _MONEY_FIELD_TOKENS:
        return "money"
    if tokens & _IDENTIFIER_FIELD_TOKENS and ({"id", "number", "identifier", "reference"} & tokens):
        return "identifier"
    return None


def _decimal_value_v1(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    if cleaned.upper().startswith("USD"):
        cleaned = cleaned[3:].strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _decimal_value(value: str, *, parser_version: str | None = None) -> Decimal | None:
    resolved = _resolve_parser_version(parser_version)
    if resolved == _PARSER_VERSION_V1:
        return _decimal_value_v1(value)

    cleaned = value.strip()
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    elif cleaned.upper().startswith("USD"):
        cleaned = cleaned[3:].strip()

    magnitude = Decimal("1")
    suffix_match = re.search(r"(?i)([A-Z]{1,4})$", cleaned)
    if suffix_match:
        suffix = suffix_match.group(1).upper()
        magnitude = _MONEY_MAGNITUDES.get(suffix)
        if magnitude is None:
            return None
        cleaned = cleaned[: suffix_match.start()]

    cleaned = re.sub(r"\s+", "", cleaned).replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned) * magnitude
    except InvalidOperation:
        return None


def _normalized_money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_date_scalar(value: str) -> date | None:
    stripped = value.strip()
    for pattern in (_ISO_DATE_RE, _US_DATE_RE):
        match = pattern.fullmatch(stripped)
        if match:
            return _safe_date(
                int(match.group("year")), int(match.group("month")), int(match.group("day"))
            )
    month_match = _MONTH_DATE_RE.fullmatch(stripped)
    if month_match:
        month_text = month_match.group("month")[:3].casefold()
        month_lookup = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        return _safe_date(
            int(month_match.group("year")),
            month_lookup[month_text],
            int(month_match.group("day")),
        )
    return None


def _structured_columns(text: str) -> dict[str, str] | None:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    columns = payload.get("columns")
    if not isinstance(columns, dict):
        return None
    return {str(key): "" if value is None else str(value) for key, value in columns.items()}


def extract_structured_facts(
    text: str, *, parser_version: str | None = None
) -> tuple[StructuredFact, ...]:
    """Extract conservative deterministic facts from one preferred evidence text.

    Structured spreadsheet rows are interpreted from source field semantics.
    Free-form prose is scanned only for explicit currency/date syntax. These
    paths are mutually exclusive so serialized row JSON does not manufacture
    duplicate prose facts from its own representation.

    ``parser_version`` exists so frozen experiment receipts can reproduce the
    exact deterministic behavior that generated them. New callers default to
    the latest parser contract.
    """
    resolved_parser = _resolve_parser_version(parser_version)
    facts: list[StructuredFact] = []
    seen: set[tuple] = set()

    def add(fact: StructuredFact) -> None:
        key = (
            fact.fact_type,
            fact.field_name,
            fact.normalized_text,
            fact.numeric_value,
            fact.unit,
            fact.char_start,
            fact.char_end,
        )
        if key not in seen:
            seen.add(key)
            facts.append(fact)

    columns = _structured_columns(text)
    if columns is not None:
        for field_name, raw_value in columns.items():
            value = raw_value.strip()
            if not value or value.startswith("="):
                continue
            kind = _field_kind(field_name)
            if kind == "money":
                parsed = _decimal_value(value, parser_version=resolved_parser)
                if parsed is not None:
                    add(
                        StructuredFact(
                            fact_type="money",
                            field_name=field_name,
                            raw_text=raw_value,
                            normalized_text=_normalized_money(parsed),
                            numeric_value=float(parsed),
                            unit="USD",
                        )
                    )
            elif kind == "date":
                parsed_date = _parse_date_scalar(value)
                if parsed_date is not None:
                    add(
                        StructuredFact(
                            fact_type="date",
                            field_name=field_name,
                            raw_text=raw_value,
                            normalized_text=parsed_date.isoformat(),
                        )
                    )
            elif kind == "identifier" and len(value) <= 160:
                add(
                    StructuredFact(
                        fact_type="identifier",
                        field_name=field_name,
                        raw_text=raw_value,
                        normalized_text=value.casefold(),
                    )
                )
        return tuple(facts)

    money_pattern = _MONEY_RE_V1 if resolved_parser == _PARSER_VERSION_V1 else _MONEY_RE
    for match in money_pattern.finditer(text):
        parsed = _decimal_value(match.group(0), parser_version=resolved_parser)
        if parsed is None:
            continue
        add(
            StructuredFact(
                fact_type="money",
                raw_text=match.group(0),
                normalized_text=_normalized_money(parsed),
                numeric_value=float(parsed),
                unit="USD",
                char_start=match.start(),
                char_end=match.end(),
            )
        )

    for pattern in (_ISO_DATE_RE, _US_DATE_RE, _MONTH_DATE_RE):
        for match in pattern.finditer(text):
            parsed_date = _parse_date_scalar(match.group(0))
            if parsed_date is None:
                continue
            add(
                StructuredFact(
                    fact_type="date",
                    raw_text=match.group(0),
                    normalized_text=parsed_date.isoformat(),
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )

    return tuple(facts)


def parse_query_date(value: str) -> str:
    """Require unambiguous ISO query boundaries for range search."""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("date query boundaries must use YYYY-MM-DD") from exc


class StructuredIndex:
    """Rebuildable deterministic index over preferred Silver evidence."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        with self.store.connection() as connection:
            connection.executescript(_STRUCTURED_SCHEMA)

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

    def rebuild(
        self,
        *,
        batch_size: int = 1000,
        parser_version: str | None = None,
    ) -> StructuredBuildResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        resolved_parser = _resolve_parser_version(parser_version)
        build_id = f"structured:{uuid.uuid4()}"
        built_at = datetime.now(UTC).isoformat()
        evidence_count = 0
        fact_count = 0

        with self.store.connection() as connection:
            connection.execute("DELETE FROM evidence_facts")
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
                    evidence_count += 1
                    facts = extract_structured_facts(
                        row["extracted_text"], parser_version=resolved_parser
                    )
                    for ordinal, fact in enumerate(facts):
                        fact_id = stable_id(
                            "fact",
                            build_id,
                            row["evidence_id"],
                            fact.fact_type,
                            fact.field_name or "",
                            fact.normalized_text or "",
                            str(fact.char_start if fact.char_start is not None else ""),
                            str(fact.char_end if fact.char_end is not None else ""),
                            str(ordinal),
                        )
                        connection.execute(
                            """
                            INSERT INTO evidence_facts(
                                fact_id, build_id, evidence_id, artifact_id, locator,
                                fact_type, field_name, raw_text, normalized_text,
                                numeric_value, unit, char_start, char_end
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                fact_id,
                                build_id,
                                row["evidence_id"],
                                row["artifact_id"],
                                row["locator"],
                                fact.fact_type,
                                fact.field_name,
                                fact.raw_text,
                                fact.normalized_text,
                                fact.numeric_value,
                                fact.unit,
                                fact.char_start,
                                fact.char_end,
                            ),
                        )
                        fact_count += 1

            connection.execute(
                """
                INSERT INTO structured_index_builds(
                    build_id, built_at, evidence_count, fact_count, parser_version
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (build_id, built_at, evidence_count, fact_count, resolved_parser),
            )

        return StructuredBuildResult(
            build_id=build_id,
            built_at=built_at,
            evidence_count=evidence_count,
            fact_count=fact_count,
            parser_version=resolved_parser,
        )

    def current_build(self) -> dict | None:
        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM structured_index_builds
                ORDER BY built_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def _hits(self, rows) -> list[StructuredHit]:
        return [
            StructuredHit(
                build_id=row["build_id"],
                fact_id=row["fact_id"],
                evidence_id=row["evidence_id"],
                artifact_id=row["artifact_id"],
                locator=row["locator"],
                fact_type=row["fact_type"],
                field_name=row["field_name"],
                raw_text=row["raw_text"],
                normalized_text=row["normalized_text"],
                numeric_value=(
                    float(row["numeric_value"]) if row["numeric_value"] is not None else None
                ),
                unit=row["unit"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                sources=self._sources_for_artifact(row["artifact_id"]),
            )
            for row in rows
        ]

    def money(
        self,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
        limit: int = 100,
    ) -> list[StructuredHit]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("minimum cannot exceed maximum")
        build = self.current_build()
        if build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")
        clauses = ["build_id = ?", "fact_type = 'money'"]
        params: list[object] = [build["build_id"]]
        if minimum is not None:
            clauses.append("numeric_value >= ?")
            params.append(minimum)
        if maximum is not None:
            clauses.append("numeric_value <= ?")
            params.append(maximum)
        params.append(limit)
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evidence_facts
                WHERE {' AND '.join(clauses)}
                ORDER BY numeric_value DESC, evidence_id, fact_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return self._hits(rows)

    def dates(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[StructuredHit]:
        if limit < 1:
            raise ValueError("limit must be positive")
        start_value = parse_query_date(start) if start else None
        end_value = parse_query_date(end) if end else None
        if start_value and end_value and start_value > end_value:
            raise ValueError("start date cannot follow end date")
        build = self.current_build()
        if build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")
        clauses = ["build_id = ?", "fact_type = 'date'"]
        params: list[object] = [build["build_id"]]
        if start_value:
            clauses.append("normalized_text >= ?")
            params.append(start_value)
        if end_value:
            clauses.append("normalized_text <= ?")
            params.append(end_value)
        params.append(limit)
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evidence_facts
                WHERE {' AND '.join(clauses)}
                ORDER BY normalized_text ASC, evidence_id, fact_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return self._hits(rows)

    def identifier(self, value: str, *, limit: int = 100) -> list[StructuredHit]:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("identifier cannot be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        build = self.current_build()
        if build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evidence_facts
                WHERE build_id = ? AND fact_type = 'identifier' AND normalized_text = ?
                ORDER BY evidence_id, fact_id
                LIMIT ?
                """,
                (build["build_id"], normalized, limit),
            ).fetchall()
        return self._hits(rows)
