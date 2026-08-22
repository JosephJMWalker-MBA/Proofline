import json
from pathlib import Path

RECEIPT = Path("experiments/akron-2026/r1_t21_april27_supporting_document_acquisition_summary.json")


def test_t21_april27_acquisition_receipt_is_content_free_and_pinned():
    payload = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert payload["schema"] == "proofline-akron-t21-april27-supporting-document-acquisition-receipt/v1"
    assert payload["stage"] == "raw_bronze_inventory_receipt_before_contextual_document_reading"

    chronology = payload["merge_chronology"]
    assert chronology["acquisition_completed_before_merges"] is True
    assert chronology["pr_87_merge_commit"] == "3adf7934c8848fe4d86d7b7f3b6ce4399535cbbc"
    assert chronology["pr_88_merge_commit"] == "07b9b864aa795e440d8a8f1dfe423406406b47cb"

    run = payload["canonical_run"]
    assert run["workflow_run_id"] == 32532934705
    assert run["job_id"] == 96928413041
    assert run["head_sha"] == "d83b64bfc45225370091bac75c74b9fc38da7094"
    assert run["artifact_id"] == 9464651696
    assert run["artifact_digest"] == "sha256:00a65ee433acc0f9906011467952d25c26ce31614582e9420dd89d43bcaaf9f6"
    assert run["raw_acquisition_json_sha256"] == "012242bc20fbd07b1e70fdf58bc0b7a95b24e926d33f472fbc730eb004d53f07"

    selection = payload["selection"]
    assert selection["selected_document_count"] == 20
    assert selection["selection_signature_sha256"] == "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"

    inv = payload["inventory"]
    assert inv["available_source_count"] == 20
    assert inv["unavailable_source_count"] == 0
    assert inv["unique_bronze_artifact_count"] == 20
    assert inv["duplicate_bronze_artifact_group_count"] == 0
    assert inv["pdf_artifact_count"] == 20
    assert inv["unique_artifact_page_count"] == 88
    assert inv["unique_artifact_native_nonblank_page_count"] == 47
    assert inv["unique_artifact_native_low_quality_page_count"] == 41
    assert len(inv["document_rows"]) == 20

    ocr = payload["next_mechanical_ocr_candidates"]
    assert ocr["selection_rule"] == "artifact.native_low_quality_page_count > 0"
    assert ocr["candidate_artifact_count"] == 4
    assert ocr["candidate_page_count"] == 41

    guards = payload["receipt_guards"]
    assert guards == {
        "link_text_embedded": False,
        "ocr_not_performed_in_acquisition_stage": True,
        "selected_document_content_embedded": False,
        "source_uri_embedded": False,
    }

    forbidden = {"text", "extracted_text", "link_text", "source_uri"}
    for row in inv["document_rows"]:
        assert not forbidden.intersection(row)
