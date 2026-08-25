from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proofline.evidence_chronology import build_chronology

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def sources():
    return (
        load("r1_t21_agenda_status_sequence_summary.json"),
        load("r1_t21_evidence_relationship_summary.json"),
        load("r1_t21_terminal_record_candidate_scan_summary.json"),
        load("r1_t21_public_access_eastwood_search_summary.json"),
        load("r1_t21_passed_legislation_recall_expansion_summary.json"),
    )


def test_frozen_chronology_shape_and_boundaries():
    chronology = build_chronology(*sources())
    assert chronology["counts"] == {
        "observed_publisher_placement_count": 23,
        "future_publisher_metadata_count": 1,
        "observed_referred_count": 1,
        "observed_time_count": 22,
        "placements_with_target_evidence_count": 5,
        "target_evidence_node_count": 8,
        "evidence_relationship_count": 6,
        "search_checkpoint_count": 3,
    }
    assert chronology["outcome"]["status"] == "unknown"
    assert chronology["authority_boundary"]["time_is_not_terminal_disposition"] is True
    assert chronology["authority_boundary"]["bounded_nonfinding_is_not_legislative_event"] is True
    assert chronology["authority_boundary"]["terminal_outcome_assigned"] is False


def test_future_metadata_is_separate_from_observed_placements():
    chronology = build_chronology(*sources())
    assert [row["meeting_id"] for row in chronology["future_publisher_metadata"]] == [698]
    assert 698 not in {row["meeting_id"] for row in chronology["publisher_placements"]}
    assert chronology["future_publisher_metadata"][0]["publisher_time_relation_to_observation"] == "after_observation"


def test_march_9_preserves_time_and_explicit_evidence_without_outcome_upgrade():
    chronology = build_chronology(*sources())
    march9 = next(row for row in chronology["publisher_placements"] if row["meeting_id"] == 671)
    assert march9["normalized_status"] == "time"
    assert march9["target_evidence_present"] is True
    assert len(march9["target_evidence_node_ids"]) == 3
    assert len(march9["evidence_relationship_ids"]) == 4
    assert chronology["outcome"]["status"] == "unknown"


def test_search_nonfindings_are_observation_checkpoints_not_meeting_events():
    chronology = build_chronology(*sources())
    assert [row["id"] for row in chronology["search_checkpoints"]] == [
        "search-checkpoint:marked-agenda-numbered-vote-scan",
        "search-checkpoint:passed-legislation-narrow",
        "search-checkpoint:passed-legislation-expanded",
    ]
    assert all("meeting_id" not in row for row in chronology["search_checkpoints"])
    expanded = chronology["search_checkpoints"][-1]["target_result"]
    assert expanded["street_number_and_location_group_count"] == 0
    assert expanded["distinctive_use_tokens_group_count"] == 0
    assert expanded["use_and_location_group_count"] == 0
    assert expanded["broad_action_and_location_group_count"] == 12
    assert expanded["broad_matches_are_target_identity"] is False


def test_new_terminal_candidate_fails_closed():
    agenda, relationships, marked, narrow, expanded = sources()
    marked = copy.deepcopy(marked)
    marked["counts"]["target_exact_title_match_count"] = 1
    with pytest.raises(ValueError, match="chronology-only authority"):
        build_chronology(agenda, relationships, marked, narrow, expanded)


def test_strong_expanded_target_candidate_fails_closed():
    agenda, relationships, marked, narrow, expanded = sources()
    expanded = copy.deepcopy(expanded)
    expanded["screening_observations"]["street_number_and_location_group_count"] = 1
    with pytest.raises(ValueError, match="strong target-identity candidate"):
        build_chronology(agenda, relationships, marked, narrow, expanded)
