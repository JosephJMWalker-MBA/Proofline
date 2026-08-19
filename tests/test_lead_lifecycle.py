from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from proofline import Ingestor
from proofline.candidate_analysis import CandidateObservationRunner
from proofline.lead_lifecycle import LeadLifecycle
from proofline.models import LeadStatus
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def _seed_candidate(state, tmp_path) -> str:
    dates = ("April 13, 2026", "October 31, 2026")
    for index, changed_date in enumerate(dates, start=1):
        text = (
            "Ordinance 1/2026\n"
            "Authorize an amendment with Example Development Inc. for cleanup services for "
            "$185,000.00 with a common completion date of July 31, 2026. "
            f"A related milestone is {changed_date}. All remaining administrative language is "
            "substantially the same for this deterministic lead fixture.\n"
        )
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/lead/{index}",
            source_name=f"Board of Control — Lead Meeting {index}",
        )
    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(
        SegmentationPlan(
            name="lead-fixture",
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
    result = CandidateObservationRunner(state).run_recurrence_variations(
        rule_name="board-items",
        threshold=0.60,
    )
    assert result.eligible == 1
    observation_id = result.items[0].observation_id
    assert observation_id is not None
    return observation_id


def test_candidate_observation_packages_into_immutable_lead_idempotently(tmp_path) -> None:
    state = tmp_path / "state"
    observation_id = _seed_candidate(state, tmp_path)
    lifecycle = LeadLifecycle(state)

    first = lifecycle.package_observation(observation_id)
    second = lifecycle.package_observation(observation_id)
    assert first.lead_id == second.lead_id
    assert first.created is True
    assert second.created is False

    packet = lifecycle.get(first.lead_id)
    assert packet is not None
    assert packet["current_status"] == "candidate"
    assert packet["observation_ids"] == [observation_id]
    assert len(packet["evidence"]) == 2
    assert packet["review_history"] == []

    lead = packet["lead"]
    assert lead["status"] == "candidate"
    assert lead["novelty"] is None
    assert lead["anomaly_strength"] is None
    assert lead["corroboration"] is None
    assert lead["source_quality"] is None
    assert lead["uncertainty"] is None
    assert "ordinary" in lead["benign_explanations_json"].casefold() or "routine" in lead[
        "benign_explanations_json"
    ].casefold()

    with lifecycle.store.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="lead packets are immutable"):
            connection.execute(
                "UPDATE leads SET status='explained' WHERE lead_id = ?", (first.lead_id,)
            )
        with pytest.raises(sqlite3.IntegrityError, match="lead evidence links are immutable"):
            connection.execute("DELETE FROM lead_evidence WHERE lead_id = ?", (first.lead_id,))


def test_review_events_derive_current_status_without_mutating_packet(tmp_path) -> None:
    state = tmp_path / "state"
    observation_id = _seed_candidate(state, tmp_path)
    lifecycle = LeadLifecycle(state)
    lead_id = lifecycle.package_observation(observation_id).lead_id

    triage = lifecycle.review(
        lead_id,
        status=LeadStatus.TRIAGED,
        reviewer="Reviewer One",
        rationale="Evidence packet has enough provenance for human triage.",
        occurred_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    )
    explained = lifecycle.review(
        lead_id,
        status=LeadStatus.EXPLAINED,
        reviewer="Reviewer One",
        rationale="The underlying records describe sequential deadline amendments.",
        notes=("No misconduct inference.",),
        occurred_at=datetime(2026, 8, 19, 12, 5, tzinfo=UTC),
    )

    packet = lifecycle.get(lead_id)
    assert packet is not None
    assert packet["lead"]["status"] == "candidate"
    assert packet["current_status"] == "explained"
    assert [event["status"] for event in packet["review_history"]] == ["triaged", "explained"]
    assert packet["review_history"][1]["rationale"].startswith("The underlying records")

    with lifecycle.store.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="lead review events are append-only"):
            connection.execute(
                "UPDATE lead_review_events SET rationale='rewritten' WHERE event_id = ?",
                (explained.event_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="lead review events are append-only"):
            connection.execute("DELETE FROM lead_review_events WHERE event_id = ?", (triage.event_id,))


def test_r0_review_api_cannot_publish(tmp_path) -> None:
    state = tmp_path / "state"
    observation_id = _seed_candidate(state, tmp_path)
    lifecycle = LeadLifecycle(state)
    lead_id = lifecycle.package_observation(observation_id).lead_id

    with pytest.raises(ValueError, match="review status must be one of"):
        lifecycle.review(
            lead_id,
            status=LeadStatus.PUBLISHED,
            reviewer="Reviewer",
            rationale="Publication should not be available through the R0 review lifecycle.",
        )
