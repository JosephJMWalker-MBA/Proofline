import json
from pathlib import Path

RECEIPT = Path("experiments/akron-2026/r1_t21_agenda_status_sequence_summary.json")

COLUMNS = [
    "meeting_id",
    "time",
    "publisher_time_relation_to_observation",
    "item_id",
    "publish_id",
    "agenda_tree_artifact_sha256",
    "status_block_index",
    "normalized_status",
    "procedural_category",
]


def test_t21_agenda_status_sequence_receipt_is_frozen_and_non_terminal():
    payload = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert payload["schema"] == "proofline-akron-t21-agenda-status-sequence-receipt/v1"
    assert payload["stage"] == "frozen_publisher_agenda_status_sequence_before_terminal_outcome_trace"
    assert payload["observation_time"] == "2026-08-24T20:51:00-04:00"

    run = payload["canonical_run"]
    assert run["workflow_run_id"] == 32795506240
    assert run["job_id"] == 97645841505
    assert run["head_sha"] == "b78dfec159e36452a150c0c1d1ad213835360b56"
    assert run["artifact_id"] == 9544854543
    assert run["artifact_digest"] == "sha256:34f4042ad017f39d2174f11d790cda773297a7ecead58e1ab56a5cdb02ba4fb0"
    assert run["raw_sequence_json_sha256"] == "db8eb4f504d0d05a692d0549551ab18b0ad28c0ae4ed9ef74297d85cd76cf9ba"
    assert run["attachment_manifest_json_sha256"] == "7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a"

    assert payload["selection"] == {
        "selected_item_count": 24,
        "selection_signature_sha256": "b46265ee254267230fa62dfc6dbc4a537fa608bd5052844fd19ffedb2a320921",
    }
    assert payload["sequence_signature_sha256"] == "b7dcaef68e02b2644397fef46479fd7322d964677d50bc27472856019ea9e906"
    assert payload["shared_item_text_sha256"] == "f24e80ac974c1c604f81bc42ce053e719a1898791657b3ba8ae3e7fd087bdab7"

    counts = payload["counts"]
    assert counts == {
        "by_normalized_status": {"referred": 1, "time": 23},
        "publisher_times_after_observation_count": 1,
        "resolved_status_count": 24,
        "selected_item_count": 24,
        "unresolved_status_count": 0,
    }

    discovery = payload["publisher_discovery"]
    assert discovery["meeting_count"] == 33
    assert discovery["agenda_tree_count"] == 33
    assert discovery["agenda_item_count"] == 1475
    assert discovery["publisher_relation_count"] == 2327
    assert discovery["publisher_relation_rejection_count"] == 0

    assert payload["sequence_columns"] == COLUMNS
    rows = [dict(zip(COLUMNS, row, strict=True)) for row in payload["sequence_rows"]]
    assert len(rows) == 24
    assert [row["time"] for row in rows] == sorted(row["time"] for row in rows)
    assert rows[0]["meeting_id"] == 668
    assert rows[0]["item_id"] == 46485
    assert rows[0]["normalized_status"] == "referred"
    assert rows[0]["procedural_category"] == "referral"
    assert rows[-1]["meeting_id"] == 698
    assert rows[-1]["item_id"] == 48997
    assert rows[-1]["normalized_status"] == "time"
    assert rows[-1]["publisher_time_relation_to_observation"] == "after_observation"

    assert sum(row["normalized_status"] == "referred" for row in rows) == 1
    assert sum(row["normalized_status"] == "time" for row in rows) == 23
    assert sum(row["publisher_time_relation_to_observation"] == "after_observation" for row in rows) == 1
    assert all(row["normalized_status"] in {"referred", "time"} for row in rows)
    assert all(row["procedural_category"] in {"referral", "hold"} for row in rows)
    assert all(isinstance(row["status_block_index"], int) and row["status_block_index"] >= 0 for row in rows)
    assert all(
        isinstance(row["agenda_tree_artifact_sha256"], str)
        and len(row["agenda_tree_artifact_sha256"]) == 64
        for row in rows
    )

    assert payload["interpretation"] == {
        "disposition": "Unknown",
        "first_observed_status": "referred",
        "future_publisher_row_count": 1,
        "future_publisher_row_is_not_event_occurrence": True,
        "recurring_time_is_not_terminal_disposition": True,
        "subsequent_time_status_count": 23,
    }

    boundary = payload["authority_boundary"]
    assert boundary == {
        "absence_treated_as_disposition": False,
        "causality_assigned": False,
        "detector_authorized": False,
        "hearing_occurrence_inferred_from_status": False,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "outcome_assigned": False,
        "status_is_procedural_evidence_only": True,
    }

    assert payload["receipt_guards"] == {
        "causal_explanation_assigned": False,
        "detector_or_lead_authority_added": False,
        "raw_agenda_text_embedded": False,
        "source_uri_embedded": False,
        "terminal_outcome_assigned": False,
    }

    forbidden = {"raw_label", "item_text", "source_uri"}
    assert not forbidden.intersection(payload)
    assert all(not forbidden.intersection(row) for row in rows)
