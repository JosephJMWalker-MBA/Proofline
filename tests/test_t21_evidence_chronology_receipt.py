from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "akron-2026"


def test_frozen_t21_chronology_receipt_boundary():
    receipt = json.loads((ROOT / "r1_t21_evidence_chronology_summary.json").read_text())
    assert receipt["schema"] == "proofline-akron-t21-evidence-chronology-receipt/v1"
    assert receipt["counts"] == {
        "evidence_relationship_count": 6,
        "future_publisher_metadata_count": 1,
        "observed_publisher_placement_count": 23,
        "observed_referred_count": 1,
        "observed_time_count": 22,
        "placements_with_target_evidence_count": 5,
        "search_checkpoint_count": 3,
        "target_evidence_node_count": 8,
    }
    assert receipt["publisher_placement_population_signature_sha256"] == "6e2e7fd9e6a5a2306f4905c5b6e8435b2c9313b76d8e2bf6f7279007d30053f1"
    assert receipt["future_metadata_population_signature_sha256"] == "8a6fb1091f0fa8a2cb3ce6faec0f9fc7e6a4d01de820a1cbc4321b0510b9c91f"
    assert receipt["search_checkpoint_population_signature_sha256"] == "4ade72e56ea473b49da58e8200610b0e789b17bc12d11ef2fc209458ba4f5e4d"
    assert receipt["chronology_signature_sha256"] == "87baac451279933ea0e0eceaa5702de9b3a518a4250d5eda79fb210068d1c8fe"
    assert [row["meeting_id"] for row in receipt["future_publisher_metadata"]] == [698]
    assert receipt["future_publisher_metadata"][0]["publisher_time_relation_to_observation"] == "after_observation"
    assert all("meeting_id" not in row for row in receipt["search_checkpoints"])
    assert receipt["search_checkpoints"][-1]["target_result"]["broad_matches_are_target_identity"] is False
    assert receipt["authority_boundary"]["bounded_nonfinding_is_not_legislative_event"] is True
    assert receipt["authority_boundary"]["time_is_not_terminal_disposition"] is True
    assert receipt["authority_boundary"]["terminal_outcome_assigned"] is False
    assert receipt["outcome"]["status"] == "unknown"


def test_march_9_receipt_preserves_multi_surface_evidence_without_terminal_upgrade():
    receipt = json.loads((ROOT / "r1_t21_evidence_chronology_summary.json").read_text())
    march9 = next(row for row in receipt["publisher_placements"] if row["meeting_id"] == 671)
    assert march9["normalized_status"] == "time"
    assert len(march9["target_evidence_node_ids"]) == 3
    assert len(march9["evidence_relationship_ids"]) == 4
    assert receipt["outcome"]["status"] == "unknown"
