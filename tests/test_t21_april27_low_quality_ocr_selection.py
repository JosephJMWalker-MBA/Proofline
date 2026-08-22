import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_april27_low_quality_ocr_selection.json"
RECEIPT_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_april27_supporting_document_acquisition_summary.json"


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_t21_low_quality_ocr_selection_is_exact_and_representation_only():
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert selection["schema"] == "proofline-akron-t21-april27-low-quality-ocr-selection/v1"
    assert selection["selection_method"] == "artifact.native_low_quality_page_count > 0"
    assert selection["selected_artifact_count"] == 4
    assert selection["selected_source_page_count"] == 48
    assert selection["selected_native_low_quality_page_count"] == 41

    rows = selection["selected_artifacts"]
    assert [row["publish_id"] for row in rows] == [102589, 102590, 102593, 102597]
    assert sum(row["page_count"] for row in rows) == 48
    assert sum(row["native_low_quality_page_count"] for row in rows) == 41
    assert _sha256_json(rows) == selection["selection_signature_sha256"]

    receipt_rows = receipt["inventory"]["document_rows"]
    expected = [
        row
        for row in receipt_rows
        if row["native_low_quality_page_count"] > 0
    ]
    assert len(expected) == 4
    for selected, source in zip(rows, expected, strict=True):
        for key in (
            "publish_id",
            "source_uri_sha256",
            "artifact_sha256",
            "page_count",
            "native_low_quality_page_count",
            "page_metadata_signature_sha256",
        ):
            assert selected[key] == source[key]

    boundary = selection["authority_boundary"]
    assert boundary["selection_is_semantic"] is False
    assert boundary["supporting_document_content_interpreted"] is False
    assert boundary["ocr_performed_in_this_stage"] is False
    assert boundary["event_identity_assigned"] is False
    assert boundary["outcome_assigned"] is False
    assert boundary["detector_authorized"] is False
    assert boundary["lead_count"] is None
