import json
from pathlib import Path


SUMMARY = Path("experiments/akron-2026/r1_t21_explicit_reference_probe_summary.json")


def test_t21_probe_receipt_preserves_descriptive_authority_boundary():
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert payload["schema"] == "proofline-akron-t21-explicit-reference-probe-summary/v1"
    assert payload["reference"] == {
        "kind": "planning_case",
        "method": "proofline-explicit-public-record-reference/v1",
        "normalized_key": "PC-2025-80-CU",
    }
    assert payload["counts"] == {
        "agenda_item_match_count": 24,
        "agenda_tree_match_count": 24,
        "audited_supporting_document_match_count": 1,
        "matching_artifacts": 49,
        "matching_evidence_units": 49,
        "matching_sources": 49,
        "publisher_meeting_count": 24,
        "target_matching_evidence_units": 1,
    }
    boundary = payload["authority_boundary"]
    assert boundary == {
        "detector_authorized": False,
        "event_identity_assigned": False,
        "lead_count": None,
        "outcome_assigned": False,
        "source_family_modified": False,
        "source_relation_created": False,
    }
    assert payload["interpretation"]["disposition"] == "Unknown"


def test_t21_probe_receipt_preserves_meeting_presence_without_outcome_claim():
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))
    meetings = payload["publisher_meeting_presence"]
    assert len(meetings) == 24
    assert meetings[0] == {
        "date_time": "2026-02-09T18:30:00-05:00",
        "evidence_surfaces": ["agenda_item", "agenda_tree"],
        "meeting_id": 668,
    }
    assert meetings[-1] == {
        "date_time": "2026-09-14T18:30:00-04:00",
        "evidence_surfaces": ["agenda_item", "agenda_tree"],
        "meeting_id": 698,
    }
    assert all(item["evidence_surfaces"] == ["agenda_item", "agenda_tree"] for item in meetings)
    assert payload["interpretation"]["publisher_meeting_presence_is_not_event_outcome"] is True
    assert payload["publisher_meeting_presence_signature_sha256"] == (
        "0cba4b77ff26b82b2c5a1de8958207267823e666f23489c3c39653f2a5b49875"
    )
