import json
from pathlib import Path


AUDIT = Path("experiments/akron-2026/r1_t21_packet_contextual_audit.json")


def _load() -> dict:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_t21_packet_contextual_audit_is_post_frozen_ocr() -> None:
    audit = _load()
    assert audit["schema"] == "proofline-akron-t21-packet-contextual-audit/v1"
    assert audit["stage"] == "post_frozen_ocr_contextual_audit_pre_supporting_document_expansion"
    basis = audit["basis"]
    assert basis["ocr_receipt_merge_commit"] == "1fc111dbb666049b7b84dae28bacbdf9048ab32e"
    assert basis["raw_ocr_run_id"] == 32528744848
    assert basis["raw_ocr_artifact_id"] == 9463263931
    assert basis["raw_ocr_artifact_digest"] == "sha256:6c7a8d418663728b3fb3263d46fd1cf8233b7184e9d7a3ab3d751d808aae9274"
    assert basis["raw_ocr_json_sha256"] == "d806ada4f1ea2848b1f8f14193459881d6f590e2a0f7f7172eff574e5fe6648f"
    assert basis["receipt_head_replay_run_id"] == 32529445844
    assert basis["receipt_head_replay_status"] == "success"


def test_t21_packet_contextual_audit_pins_frozen_pages() -> None:
    audit = _load()
    assert audit["basis"]["bronze_artifact_sha256"] == "87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    assert audit["frozen_page_text_sha256"] == [
        "0cb8d94d8ac4b452f9e9af627a150cd755b39d278ebe2848048dffeb79539b98",
        "5f92672868553054c3cb376fa6f7948cc0c429bad878000b0b1df808bc4a73cd",
        "ca95e84f7ab01d9fc2cf7d2065757c89900649f48e0fea71a267a2b3fb71b25e",
    ]


def test_t21_packet_contextual_audit_preserves_semantic_boundary() -> None:
    audit = _load()
    boundary = audit["authority_boundary"]
    assert boundary == {
        "detector_authorized": False,
        "event_identity_assigned": False,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "outcome_assigned": False,
        "packet_content_interpreted": True,
        "source_family_modified": False,
        "source_relation_created": False,
    }
    assert audit["contextual_observations"]["planning_case_key"]["normalized_key"] == "PC-2025-80-CU"
    assert audit["contextual_observations"]["stated_project_cost"]["amount"] == "677000.00"
    assert audit["next_publisher_bounded_surface"] == {
        "meeting_id": 682,
        "meeting_name": "April 27, 2026",
        "parent_item_id": 47559,
        "publisher_declared_supporting_document_count": 20,
        "status": "identified_not_content_opened_in_this_audit",
    }
