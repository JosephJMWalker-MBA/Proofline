from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_SUMMARY = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_record_family_evolution_summary.json"
)
_SELECTION = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_record_family_packet_selection.json"
)


def test_t21_record_family_evolution_receipt_is_pinned() -> None:
    summary = json.loads(_SUMMARY.read_text(encoding="utf-8"))
    selection = json.loads(_SELECTION.read_text(encoding="utf-8"))

    assert summary["schema"] == "proofline-akron-t21-record-family-evolution-summary/v1"
    assert summary["stage"] == (
        "post_packet_sync_raw_byte_evolution_receipt_before_ocr_or_contextual_interpretation"
    )
    assert summary["canonical_run"] == {
        "artifact_digest": "sha256:f0796a3f555ce02a5f584001003a9a7b2da9f23096b70b6b0152b9c0bd5ca8b2",
        "artifact_id": 9459168882,
        "freeze_head": "923f85a06cb0c531d91b0b7bef62f8eb1cf2f9c3",
        "job_id": 96879483971,
        "raw_result_sha256": "dd747691c0e51827cf75f75075db6e0f09d9cd0388caacd356fa74bd89ecc3ef",
        "run_id": 32516590296,
    }
    assert summary["counts"] == {
        "consecutive_bronze_change_count": 0,
        "packet_source_count": 24,
        "publisher_times_after_observation_count": 1,
        "repeated_bronze_artifact_group_count": 1,
        "unique_bronze_artifact_count": 1,
    }
    assert summary["evolution_signature_sha256"] == (
        "6dee28ce1d206491032750bc17e675e8410c961b00499f598d5d4dc627c43c48"
    )
    assert summary["selection"]["selection_signature_sha256"] == (
        "b46265ee254267230fa62dfc6dbc4a537fa608bd5052844fd19ffedb2a320921"
    )
    assert summary["selection"]["selection_signature_sha256"] == selection[
        "selection_signature_sha256"
    ]
    assert selection["selected_packet_count"] == 24

    artifact = summary["unique_bronze_packet"]
    assert artifact["artifact_id"] == (
        "artifact:87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    )
    assert artifact["sha256"] == (
        "87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    )
    assert artifact["byte_size"] == 1151866
    assert artifact["page_count"] == 3
    assert artifact["nonblank_native_page_count"] == 0
    assert artifact["native_low_quality_page_count"] == 3
    assert artifact["native_text_signature_sha256"] == (
        "2d8155eb7a8171a2f0052623256263cc16f1237c2d6a7fb9e91f83d11dd2b63d"
    )

    boundary = summary["authority_boundary"]
    assert boundary == {
        "detector_authorized": False,
        "event_identity_assigned": False,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "outcome_assigned": False,
        "source_family_modified": False,
        "source_relation_created": False,
    }
    assert summary["interpretation_boundary"] == {
        "base_packet_content_interpreted": False,
        "disposition": "Unknown",
        "ocr_performed_in_this_stage": False,
        "publisher_source_identity_distinct_from_artifact_identity": True,
    }
