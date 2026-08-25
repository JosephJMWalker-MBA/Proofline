"""Fail-closed extraction of publisher-style numbered vote record candidates.

A numbered instrument with an explicit vote is strong evidence that a legislative
record deserves terminal-disposition review. It is still only a *candidate* at
this layer. This module never infers passage, failure, approval, denial,
withdrawal, meeting occurrence, or any other terminal outcome from vote
arithmetic or surrounding prose.

Version 1 recognizes only records whose publisher text begins a line with an
explicit ``ORDINANCE NO.`` or ``RESOLUTION NO.`` identifier and contains an
exact two-part ``Vote: A-B`` before the next numbered instrument or the
publisher's ``NEW LEGISLATION`` boundary. Unnumbered pending legislation and
free-form mentions fail closed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .hashing import stable_id

TERMINAL_RECORD_CANDIDATE_METHOD = "proofline-numbered-vote-record-candidate/v1"

_INSTRUMENT_START_RE = re.compile(
    r"(?im)^[ \t]*(?P<kind>ORDINANCE|RESOLUTION)\s+NO\.?\s+"
    r"(?P<number>\d+)-(?P<year>\d{4})\b"
)
_NEW_LEGISLATION_RE = re.compile(r"(?im)^[ \t]*NEW\s+LEGISLATION[ \t]*$")
_VOTE_RE = re.compile(
    r"(?i)\bVote\s*:\s*(?P<ayes>\d+)\s*-\s*(?P<nays>\d+)\b(?!\s*-\s*\d)"
)


@dataclass(frozen=True, slots=True)
class NumberedVoteRecordCandidate:
    candidate_id: str
    evidence_id: str
    instrument_type: str
    instrument_number: int
    instrument_year: int
    raw_record_text: str
    normalized_record_text: str
    vote_ayes: int
    vote_nays: int
    candidate_basis: str = "numbered_instrument_with_explicit_vote"
    terminal_outcome_assigned: bool = False
    method: str = TERMINAL_RECORD_CANDIDATE_METHOD

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def extract_numbered_vote_record_candidates(
    text: str,
    *,
    evidence_id: str,
) -> tuple[NumberedVoteRecordCandidate, ...]:
    """Return exact numbered-instrument + vote candidates from publisher text.

    Candidate extraction deliberately stops short of disposition semantics. A
    ``Vote: 12-0`` and a ``Vote: 0-12`` are represented identically except for
    their observed counts; neither is labeled passed or failed here.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not evidence_id:
        raise ValueError("evidence_id must be non-empty")
    if not text:
        return ()

    starts = tuple(_INSTRUMENT_START_RE.finditer(text))
    new_legislation_boundaries = tuple(_NEW_LEGISLATION_RE.finditer(text))
    candidates: list[NumberedVoteRecordCandidate] = []
    for index, start in enumerate(starts):
        structural_ends = [
            starts[index + 1].start() if index + 1 < len(starts) else len(text)
        ]
        structural_ends.extend(
            boundary.start()
            for boundary in new_legislation_boundaries
            if boundary.start() > start.start()
        )
        end = min(structural_ends)
        raw_chunk = text[start.start() : end].strip()
        vote = _VOTE_RE.search(raw_chunk)
        if vote is None:
            continue

        # Keep only the numbered record through its first exact explicit vote.
        # This prevents unrelated later prose from becoming part of the candidate.
        raw_record = raw_chunk[: vote.end()].strip()
        normalized = _normalize_text(raw_record)
        kind = start.group("kind").casefold()
        number = int(start.group("number"))
        year = int(start.group("year"))
        ayes = int(vote.group("ayes"))
        nays = int(vote.group("nays"))

        candidates.append(
            NumberedVoteRecordCandidate(
                candidate_id=stable_id(
                    "terminal-record-candidate",
                    TERMINAL_RECORD_CANDIDATE_METHOD,
                    evidence_id,
                    kind,
                    str(number),
                    str(year),
                    normalized.casefold(),
                    str(ayes),
                    str(nays),
                ),
                evidence_id=evidence_id,
                instrument_type=kind,
                instrument_number=number,
                instrument_year=year,
                raw_record_text=raw_record,
                normalized_record_text=normalized,
                vote_ayes=ayes,
                vote_nays=nays,
            )
        )

    return tuple(candidates)
