"""Fail-closed normalization of explicit publisher agenda-status labels.

This module gives downstream chronology code a bounded vocabulary for labels the
publisher places around agenda items. A status observation is procedural evidence
only: it never assigns passage, denial, withdrawal, meeting occurrence, causation,
or any other terminal outcome.

Version 1 intentionally accepts only exact, structurally recognizable labels.
Unknown prose stays unknown rather than being fuzzily classified.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .hashing import stable_id

AGENDA_STATUS_METHOD = "proofline-explicit-agenda-status/v1"


@dataclass(frozen=True, slots=True)
class AgendaStatusObservation:
    status_id: str
    evidence_id: str
    raw_label: str
    normalized_status: str
    procedural_category: str
    terminal_outcome_assigned: bool = False
    method: str = AGENDA_STATUS_METHOD

    def to_dict(self) -> dict:
        return asdict(self)


# Order is significant: more specific referral/hearing labels must be tested before
# their shorter prefixes. The patterns are anchored so explanatory prose does not
# accidentally become publisher-status evidence.
_STATUS_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "first_reading_referred_public_hearing",
        "referral",
        re.compile(
            r"^FIRST\s+READING\s+AND\s+REFERRED\s*:\s*"
            r"(?:UP\s+FOR|TO\s+BE\s+SCHEDULED\s+FOR)\s+PUBLIC\s+HEARING"
            r"(?:\s+[^:]+)?\s*:?$",
            re.IGNORECASE,
        ),
    ),
    (
        "first_reading_referred",
        "referral",
        re.compile(r"^FIRST\s+READING\s+AND\s+REFERRED\s*:?$", re.IGNORECASE),
    ),
    (
        "public_hearing",
        "hearing",
        re.compile(
            r"^(?:UP\s+FOR|TO\s+BE\s+SCHEDULED\s+FOR)\s+PUBLIC\s+HEARING"
            r"(?:\s+[^:]+)?\s*:?$",
            re.IGNORECASE,
        ),
    ),
    (
        "referred",
        "referral",
        re.compile(r"^REFERRED\s*:?$", re.IGNORECASE),
    ),
    (
        "time",
        "hold",
        re.compile(r"^TIME\s*:?$", re.IGNORECASE),
    ),
    (
        "no_items",
        "empty_section",
        re.compile(r"^NO\s+ITEMS\s*:?$", re.IGNORECASE),
    ),
)


def _canonical_label(label: str) -> str:
    return " ".join(label.strip().split())


def classify_agenda_status_label(
    label: str,
    *,
    evidence_id: str,
) -> AgendaStatusObservation | None:
    """Normalize one explicit publisher agenda-status label.

    The caller is responsible for structural association between a publisher label
    and an agenda item. This function deliberately does not search arbitrary prose
    for status words because phrases such as "time to approve" or "was referred"
    are not equivalent to publisher-declared agenda placement.
    """
    if not evidence_id:
        raise ValueError("evidence_id must be non-empty")
    if not isinstance(label, str):
        raise TypeError("label must be a string")

    canonical = _canonical_label(label)
    if not canonical:
        return None

    for normalized_status, category, pattern in _STATUS_PATTERNS:
        if pattern.fullmatch(canonical):
            return AgendaStatusObservation(
                status_id=stable_id(
                    "agenda-status",
                    AGENDA_STATUS_METHOD,
                    evidence_id,
                    normalized_status,
                    canonical.casefold(),
                ),
                evidence_id=evidence_id,
                raw_label=label,
                normalized_status=normalized_status,
                procedural_category=category,
            )
    return None
