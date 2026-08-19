"""Durable, version-controlled human review records for Proofline leads.

Review records are external declarations of human judgment. Applying one never mutates the
immutable lead packet; it deterministically appends (or reuses) the corresponding review event.
This lets reproducible corpus builds reconstruct human disposition history from explicit files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .hashing import stable_id
from .lead_lifecycle import LeadLifecycle, LeadReviewEvent
from .models import LeadStatus

_SCHEMA = "proofline-lead-review/v1"


@dataclass(frozen=True, slots=True)
class LeadReviewRecord:
    lead_id: str
    status: LeadStatus
    reviewer: str
    occurred_at: datetime
    rationale: str
    notes: tuple[str, ...] = ()
    schema: str = _SCHEMA

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["occurred_at"] = self.occurred_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class ReviewRecordApplication:
    path: str
    event: LeadReviewEvent
    created: bool

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "event": self.event.to_dict(),
            "created": self.created,
        }


def load_review_record(path: str | Path) -> LeadReviewRecord:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != _SCHEMA:
        raise ValueError(f"review record schema must be {_SCHEMA!r}")

    lead_id = payload.get("lead_id")
    reviewer = payload.get("reviewer")
    rationale = payload.get("rationale")
    status_value = payload.get("status")
    occurred_value = payload.get("occurred_at")
    notes_value = payload.get("notes", [])

    if not isinstance(lead_id, str) or not lead_id.strip():
        raise ValueError("review record lead_id must be a non-empty string")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("review record reviewer must be a non-empty string")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("review record rationale must be a non-empty string")
    if not isinstance(status_value, str):
        raise ValueError("review record status must be a string")
    try:
        status = LeadStatus(status_value)
    except ValueError as exc:
        raise ValueError(f"unknown review record status: {status_value!r}") from exc
    if status is LeadStatus.PUBLISHED:
        raise ValueError("published is not a valid R0 review-record disposition")
    if not isinstance(occurred_value, str):
        raise ValueError("review record occurred_at must be an ISO-8601 string")
    try:
        occurred_at = datetime.fromisoformat(occurred_value)
    except ValueError as exc:
        raise ValueError("review record occurred_at must be valid ISO-8601") from exc
    if occurred_at.tzinfo is None:
        raise ValueError("review record occurred_at must include a timezone offset")
    if not isinstance(notes_value, list) or not all(isinstance(item, str) for item in notes_value):
        raise ValueError("review record notes must be a list of strings")

    return LeadReviewRecord(
        lead_id=lead_id.strip(),
        status=status,
        reviewer=reviewer.strip(),
        occurred_at=occurred_at,
        rationale=rationale.strip(),
        notes=tuple(item.strip() for item in notes_value),
    )


def _event_id(record: LeadReviewRecord) -> str:
    return stable_id(
        "lead-review-event",
        record.lead_id,
        record.occurred_at.isoformat(),
        record.status.value,
        record.reviewer,
        record.rationale,
        *record.notes,
    )


def apply_review_record(
    state_dir: str | Path,
    path: str | Path,
) -> ReviewRecordApplication:
    record = load_review_record(path)
    lifecycle = LeadLifecycle(state_dir)
    expected_event_id = _event_id(record)

    for event in lifecycle.review_history(record.lead_id):
        if event.event_id == expected_event_id:
            return ReviewRecordApplication(path=str(path), event=event, created=False)

    event = lifecycle.review(
        record.lead_id,
        status=record.status,
        reviewer=record.reviewer,
        rationale=record.rationale,
        notes=record.notes,
        occurred_at=record.occurred_at,
    )
    if event.event_id != expected_event_id:
        raise AssertionError("applied review event identity did not match review record")
    return ReviewRecordApplication(path=str(path), event=event, created=True)
