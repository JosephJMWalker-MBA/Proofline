import json
from pathlib import Path


RECEIPT_V2 = Path("experiments/akron-2026/r1_t21_april27_supporting_document_acquisition_summary_v2.json")
LOW_SELECTION_V2 = Path("experiments/akron-2026/r1_t21_april27_low_quality_ocr_selection_v2.json")
FULL_SELECTION = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def test_corrected_receipt_v2_preserves_canonical_measurement_and_selection():
    receipt = json.loads(RECEIPT_V2.read_text(encoding="utf-8"))
    full = json.loads(FULL_SELECTION.read_text(encoding="utf-8"))

    assert receipt["schema"] == "proofline-akron-t21-april27-supporting-document-acquisition-receipt/v2"
    assert receipt["canonical_run"]["raw_acquisition_json_sha256"] == "012242bc20fbd07b1e70fdf58bc0b7a95b24e926d33f472fbc730eb004d53f07"
    assert receipt["selection"]["selection_signature_sha256"] == full["selection_signature_sha256"]
    assert receipt["selection"]["canonical_acquisition_identity_match_count"] == 20
    assert receipt["selection"]["canonical_acquisition_identity_mismatch_count"] == 0
    assert receipt["correction"]["canonical_measurement_changed"] is False
    assert receipt["correction"]["selected_source_set_changed"] is False
    assert receipt["correction"]["ocr_performed_before_correction"] is False
    assert receipt["receipt_guards"]["v1_receipt_must_not_be_used_for_downstream_identity_or_artifact_metadata"] is True


def test_corrected_ocr_frontier_is_exactly_four_artifacts_and_41_pages():
    receipt = json.loads(RECEIPT_V2.read_text(encoding="utf-8"))
    low = json.loads(LOW_SELECTION_V2.read_text(encoding="utf-8"))
    frontier = receipt["ocr_frontier"]

    assert frontier["selected_publish_ids"] == [102589, 102590, 102593, 102597]
    assert frontier["selected_artifact_count"] == 4
    assert frontier["selected_source_page_count"] == 48
    assert frontier["selected_low_quality_page_count"] == 41
    assert frontier["selection_signature_sha256"] == "cd86100e5a6ff2d54159ae0437db95f79bdcfed24a054c1ed330792f3c07c357"
    assert low["selection_signature_sha256"] == frontier["selection_signature_sha256"]
    assert low["selected_artifacts"] == frontier["selected_artifacts"]
