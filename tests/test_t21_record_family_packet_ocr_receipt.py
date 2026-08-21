from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_SUMMARY = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_record_family_packet_ocr_summary.json"
)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_t21_packet_ocr_receipt_pins_raw_result_before_interpretation() -> None:
    p = json.loads(_SUMMARY.read_text(encoding="utf-8"))

    assert p["schema"] == "proofline-akron-t21-record-family-packet-ocr-summary/v1"
    assert p["stage"] == "post_raw_packet_ocr_receipt_before_contextual_interpretation"
    assert p["canonical_run"] == {
        "artifact_digest": "sha256:6c7a8d418663728b3fb3263d46fd1cf8233b7184e9d7a3ab3d751d808aae9274",
        "artifact_id": 9463263931,
        "harness_commit": "7f3e4e76e7ca502193ae02f6e0c8079ac9cdf23e",
        "head_sha": "979299502a4a8b209865b5e4d1e29150d14276a1",
        "job_id": 96916303071,
        "raw_packet_ocr_sha256": "d806ada4f1ea2848b1f8f14193459881d6f590e2a0f7f7172eff574e5fe6648f",
        "run_id": 32528744848,
    }

    frozen = p["frozen_inputs"]
    assert frozen["bronze_artifact_id"] == (
        "artifact:87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    )
    assert frozen["bronze_sha256"] == (
        "87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    )
    assert frozen["bronze_byte_size"] == 1_151_866
    assert frozen["bronze_page_count"] == 3
    assert frozen["quality_floor"] == 0.70
    assert frozen["ocr_language"] == "eng"
    assert frozen["ocr_dpi"] == 200

    assert p["ocr_result"] == {
        "added": 3,
        "attempted": 3,
        "backend": "pymupdf_tesseract_ocr",
        "candidates": 3,
        "failed": 0,
        "failure_count": 0,
        "skipped": 0,
    }

    silver = p["silver_result"]
    assert silver["page_count"] == 3
    assert silver["preferred_ocr_page_count"] == 3
    assert silver["nonblank_page_count"] == 3
    assert silver["quality_floor_page_count"] == 3
    assert silver["total_character_count"] == 3259
    assert silver["total_line_count"] == 182
    assert silver["page_metadata_signature_sha256"] == (
        "57842c8f8c211193011580e5d78a7448aad77cedec06f771f6464865a9f87a32"
    )
    assert [page["text_sha256"] for page in silver["pages"]] == [
        "0cb8d94d8ac4b452f9e9af627a150cd755b39d278ebe2848048dffeb79539b98",
        "5f92672868553054c3cb376fa6f7948cc0c429bad878000b0b1df808bc4a73cd",
        "ca95e84f7ab01d9fc2cf7d2065757c89900649f48e0fea71a267a2b3fb71b25e",
    ]
    assert all(page["quality_score"] == 1.0 for page in silver["pages"])
    assert all(page["nonblank"] is True for page in silver["pages"])
    assert all(page["meets_quality_floor"] is True for page in silver["pages"])

    assert "text" not in set(_walk_keys(p))
    assert p["lineage_reuse"] == {
        "publisher_source_identity_count": 24,
        "silver_extracted_once_for_content_addressed_artifact": True,
        "source_family_modified": False,
        "source_relation_created": False,
        "unique_bronze_artifact_count": 1,
    }
    assert p["interpretation_boundary"] == {
        "detector_authorized": False,
        "disposition": "Unknown",
        "event_identity_assigned": False,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "ocr_text_read_contextually_before_this_receipt": False,
        "outcome_assigned": False,
        "packet_content_interpreted": False,
    }
