from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofline import Ingestor
from proofline.candidate_analysis import CandidateObservationRunner
from proofline.lead_lifecycle import LeadLifecycle
from proofline.review_records import apply_review_record, load_review_record
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def _seed_lead(state: Path, tmp_path: Path) -> str:
    for index, changed_date in enumerate(("April 13, 2026", "October 31, 2026"), start=1):
        text = (
            "Ordinance 1/2026\n"
            "Authorize an amendment with Example Development Inc. for cleanup services for "
            "$185,000.00 with a common completion date of July 31, 2026. "
            f"A related milestone is {changed_date}. All remaining administrative language is "
            "substantially the same for this deterministic review-record fixture.\n"
        )
        path = tmp_path / f"review-meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/review/{index}",
            source_name=f"Board of Control — Review Meeting {index}",
        )

    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(
        SegmentationPlan(
            name="review-record-fixture",
            rules=(
                SegmentationRule(
                    name="board-items",
                    source_name_regex=r"^Board of Control",
                    anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
                    segment_type="agenda_item",
                    min_chars=40,
                ),
            ),
        )
    )
    candidates = CandidateObservationRunner(state).run_recurrence_variations(
        rule_name="board-items",
        threshold=0.60,
    )
    assert candidates.eligible == 1
    observation_id = candidates.items[0].observation_id
    assert observation_id is not None
    return LeadLifecycle(state).package_observation(observation_id).lead_id


def _write_record(path: Path, lead_id: str, *, status: str = "explained") -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-lead-review/v1",
                "lead_id": lead_id,
                "status": status,
                "reviewer": "Joseph Walker",
                "occurred_at": "2026-08-19T17:14:00+00:00",
                "rationale": "The underlying records describe sequential deadline amendments.",
                "notes": ["No misconduct inference."],
            }
        ),
        encoding="utf-8",
    )


def test_version_controlled_review_record_applies_idempotently(tmp_path) -> None:
    state = tmp_path / "state"
    lead_id = _seed_lead(state, tmp_path)
    record_path = tmp_path / "review.json"
    _write_record(record_path, lead_id)

    parsed = load_review_record(record_path)
    assert parsed.lead_id == lead_id
    assert parsed.status.value == "explained"
    assert parsed.occurred_at.utcoffset() is not None

    first = apply_review_record(state, record_path)
    second = apply_review_record(state, record_path)
    assert first.created is True
    assert second.created is False
    assert first.event.event_id == second.event.event_id

    packet = LeadLifecycle(state).get(lead_id)
    assert packet is not None
    assert packet["lead"]["status"] == "candidate"
    assert packet["current_status"] == "explained"
    assert len(packet["review_history"]) == 1
    assert packet["review_history"][0]["reviewer"] == "Joseph Walker"


def test_review_record_rejects_publication_status(tmp_path) -> None:
    state = tmp_path / "state"
    lead_id = _seed_lead(state, tmp_path)
    record_path = tmp_path / "published.json"
    _write_record(record_path, lead_id, status="published")

    with pytest.raises(ValueError, match="published is not a valid R0"):
        apply_review_record(state, record_path)


def test_review_record_requires_timezone(tmp_path) -> None:
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-lead-review/v1",
                "lead_id": "lead:test",
                "status": "explained",
                "reviewer": "Reviewer",
                "occurred_at": "2026-08-19T17:14:00",
                "rationale": "A rationale.",
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="timezone offset"):
        load_review_record(path)
