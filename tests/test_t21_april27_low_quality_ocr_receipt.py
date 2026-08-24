import hashlib
import json
from pathlib import Path


RECEIPT = Path("experiments/akron-2026/r1_t21_april27_low_quality_ocr_receipt.json")
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
PAGE_HASH_SIGNATURE = "bb87cbbe7443e25b23861745b4df922af8a972c6d1fe2275d923ac2b9de42807"


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key(child, key) for child in value)
    return False


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_t21_april27_low_quality_ocr_receipt_is_pre_reading_and_pinned():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "proofline-akron-t21-april27-low-quality-ocr-receipt/v1"
    assert receipt["stage"] == "raw_silver_ocr_receipt_before_contextual_supporting_document_reading"
    assert receipt["canonical_run"] == {
        "head_sha": "e6fd4fd81bf7f4f017896a98f67c697d552b35e4",
        "job_id": 97299320376,
        "raw_low_quality_ocr_json_sha256": "f7027285870fdec87328d2218391b7b28a13df3f4edf933cddca7a92b169c566",
        "workflow_artifact_digest": "sha256:81426a330498c708ae107df63c73fa401a01597d86f80eb38c64b136a41ccd69",
        "workflow_artifact_id": 9504466994,
        "workflow_run_id": 32681674473,
    }
    assert receipt["ocr"] == {"added": 41, "attempted": 41, "candidates": 48, "failed": 0, "skipped": 7}
    assert receipt["silver_summary"] == {
        "artifact_count": 4,
        "page_count": 48,
        "preferred_method_counts": {"pymupdf_native_text": 7, "pymupdf_tesseract_ocr": 41},
        "preferred_nonblank_page_count": 47,
        "preferred_ocr_page_count": 41,
        "preferred_quality_floor_page_count": 47,
    }


def test_t21_april27_low_quality_ocr_receipt_freezes_all_page_text_hashes_without_prose():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    page_hashes = receipt["page_text_hashes"]
    assert len(page_hashes) == 48
    assert _sha256_json(page_hashes) == PAGE_HASH_SIGNATURE
    assert receipt["page_text_hashes_signature_sha256"] == PAGE_HASH_SIGNATURE
    assert _contains_key(receipt, "text") is False
    assert receipt["receipt_guards"] == {
        "contextual_reading_performed_before_receipt": False,
        "ocr_text_embedded": False,
        "page_text_hashes_embedded": True,
    }


def test_t21_april27_low_quality_ocr_receipt_preserves_single_residual_exception():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    exceptions = receipt["residual_quality_exceptions"]
    assert len(exceptions) == 1
    assert exceptions[0] == {
        "meets_quality_floor": False,
        "method": "pymupdf_tesseract_ocr",
        "nonblank": False,
        "page_number": 5,
        "publish_id": 102590,
        "quality_score": 0.0,
        "text_sha256": EMPTY_SHA256,
        "warnings": ["OCR text remains below the default review threshold"],
    }


def test_t21_april27_low_quality_ocr_receipt_keeps_authority_closed():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["authority_boundary"] == {
        "detector_authorized": False,
        "event_identity_assigned": False,
        "hearing_occurrence_asserted": False,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "outcome_assigned": False,
        "source_family_modified": False,
        "source_relation_created": False,
        "supporting_document_content_interpreted": False,
    }
