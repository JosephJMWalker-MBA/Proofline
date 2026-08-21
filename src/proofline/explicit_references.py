"""Deterministic extraction of explicit public-record reference keys.

This module deliberately extracts only literal, machine-readable identifiers and
bounded temporal references. It does not perform fuzzy entity resolution, infer
record families from prose similarity, or assign outcome/semantic authority.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Mapping

from .hashing import stable_id

EXPLICIT_REFERENCE_METHOD = "proofline-explicit-public-record-reference/v1"

_CASE_RE = re.compile(r"\bPC\s*-\s*(\d{4})\s*-\s*(\d{1,4})\s*-\s*([A-Z][A-Z0-9&]*)\b", re.IGNORECASE)
_DOCKET_RE = re.compile(r"\bD\s*-\s*(\d{1,5}(?:\s*-\s*\d{1,5})?)\b", re.IGNORECASE)
_ORDINANCE_RE = re.compile(
    r"\bORDINANCE(?:\s+NO\.?)?\s+(\d{1,4}\s*-\s*\d{4})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(\d{2}|\d{4})\b")
_MONTH_NAMES = {name.casefold(): index for index, name in enumerate(calendar.month_name) if name}
_MONTH_NAMES.update({name.casefold(): index for index, name in enumerate(calendar.month_abbr) if name})
_MONTH_TOKEN = "|".join(sorted((re.escape(name) for name in _MONTH_NAMES), key=len, reverse=True))
_MONTH_DATE_RE = re.compile(
    rf"\b({_MONTH_TOKEN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)

_STRONG_JOIN_KINDS = frozenset({"planning_case", "docket", "ordinance"})


@dataclass(frozen=True, slots=True)
class ExplicitReference:
    reference_id: str
    evidence_id: str
    kind: str
    normalized_key: str
    raw_text: str
    char_start: int
    char_end: int
    join_eligible: bool
    normalization_basis: str
    method: str = EXPLICIT_REFERENCE_METHOD

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExactReferenceMatch:
    match_id: str
    kind: str
    normalized_key: str
    evidence_ids: tuple[str, ...]
    method: str = EXPLICIT_REFERENCE_METHOD

    def to_dict(self) -> dict:
        return asdict(self)


def _reference(
    *,
    evidence_id: str,
    kind: str,
    normalized_key: str,
    raw_text: str,
    char_start: int,
    char_end: int,
    join_eligible: bool,
    normalization_basis: str,
) -> ExplicitReference:
    return ExplicitReference(
        reference_id=stable_id(
            "reference",
            EXPLICIT_REFERENCE_METHOD,
            evidence_id,
            kind,
            normalized_key,
            str(char_start),
            str(char_end),
        ),
        evidence_id=evidence_id,
        kind=kind,
        normalized_key=normalized_key,
        raw_text=raw_text,
        char_start=char_start,
        char_end=char_end,
        join_eligible=join_eligible,
        normalization_basis=normalization_basis,
    )


def _valid_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_explicit_references(
    text: str,
    *,
    evidence_id: str,
    context_date: date | None = None,
) -> tuple[ExplicitReference, ...]:
    """Extract literal public-record keys and bounded date references.

    Dates are intentionally not join-eligible by themselves. Month/day references
    without a year are normalized only when a trusted evidence context date is
    supplied; the resulting reference records that contextual normalization basis.
    """
    if not evidence_id:
        raise ValueError("evidence_id must be non-empty")

    found: list[ExplicitReference] = []

    for match in _CASE_RE.finditer(text):
        normalized = f"PC-{match.group(1)}-{int(match.group(2))}-{match.group(3).upper()}"
        found.append(
            _reference(
                evidence_id=evidence_id,
                kind="planning_case",
                normalized_key=normalized,
                raw_text=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                join_eligible=True,
                normalization_basis="literal_identifier",
            )
        )

    for match in _DOCKET_RE.finditer(text):
        number = re.sub(r"\s+", "", match.group(1))
        normalized = f"D-{number}"
        found.append(
            _reference(
                evidence_id=evidence_id,
                kind="docket",
                normalized_key=normalized,
                raw_text=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                join_eligible=True,
                normalization_basis="literal_identifier",
            )
        )

    for match in _ORDINANCE_RE.finditer(text):
        normalized_number = re.sub(r"\s+", "", match.group(1))
        found.append(
            _reference(
                evidence_id=evidence_id,
                kind="ordinance",
                normalized_key=f"ORDINANCE-{normalized_number}",
                raw_text=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                join_eligible=True,
                normalization_basis="literal_identifier",
            )
        )

    occupied_date_spans: set[tuple[int, int]] = set()
    for match in _NUMERIC_DATE_RE.finditer(text):
        month, day, raw_year = int(match.group(1)), int(match.group(2)), match.group(3)
        year = int(raw_year)
        if len(raw_year) == 2:
            year += 2000
        parsed = _valid_date(year, month, day)
        if parsed is None:
            continue
        occupied_date_spans.add((match.start(), match.end()))
        found.append(
            _reference(
                evidence_id=evidence_id,
                kind="date",
                normalized_key=parsed.isoformat(),
                raw_text=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                join_eligible=False,
                normalization_basis="literal_date",
            )
        )

    for match in _MONTH_DATE_RE.finditer(text):
        span = (match.start(), match.end())
        if span in occupied_date_spans:
            continue
        month = _MONTH_NAMES[match.group(1).casefold()]
        day = int(match.group(2))
        raw_year = match.group(3)
        if raw_year is None:
            if context_date is None:
                continue
            year = context_date.year
            basis = "context_year"
        else:
            year = int(raw_year)
            basis = "literal_date"
        parsed = _valid_date(year, month, day)
        if parsed is None:
            continue
        found.append(
            _reference(
                evidence_id=evidence_id,
                kind="date",
                normalized_key=parsed.isoformat(),
                raw_text=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                join_eligible=False,
                normalization_basis=basis,
            )
        )

    found.sort(key=lambda item: (item.char_start, item.char_end, item.kind, item.normalized_key))
    return tuple(found)


def exact_reference_matches(
    evidence_texts: Mapping[str, str],
    *,
    context_dates: Mapping[str, date] | None = None,
) -> tuple[ExactReferenceMatch, ...]:
    """Return cross-evidence matches for exact strong reference keys only.

    A date, shared vocabulary, filename, address fragment, or text similarity is
    never sufficient to create a match in this method version.
    """
    contexts = context_dates or {}
    by_key: dict[tuple[str, str], set[str]] = {}
    for evidence_id in sorted(evidence_texts):
        references = extract_explicit_references(
            evidence_texts[evidence_id],
            evidence_id=evidence_id,
            context_date=contexts.get(evidence_id),
        )
        for reference in references:
            if not reference.join_eligible or reference.kind not in _STRONG_JOIN_KINDS:
                continue
            by_key.setdefault((reference.kind, reference.normalized_key), set()).add(evidence_id)

    matches: list[ExactReferenceMatch] = []
    for (kind, normalized_key), evidence_ids in sorted(by_key.items()):
        ordered = tuple(sorted(evidence_ids))
        if len(ordered) < 2:
            continue
        matches.append(
            ExactReferenceMatch(
                match_id=stable_id(
                    "reference-match",
                    EXPLICIT_REFERENCE_METHOD,
                    kind,
                    normalized_key,
                    *ordered,
                ),
                kind=kind,
                normalized_key=normalized_key,
                evidence_ids=ordered,
            )
        )
    return tuple(matches)
