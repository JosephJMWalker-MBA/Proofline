from __future__ import annotations

import pymupdf
import pytest

from proofline.hashing import sha256_text
from proofline.spatial_text import (
    extract_native_spatial_page,
    parse_ocr_model_version,
    spatial_words_from_pymupdf,
)


def test_spatial_words_normalize_deterministic_order_and_lines() -> None:
    raw = [
        (80.0, 20.0, 100.0, 30.0, "fee", 1, 0, 1),
        (10.0, 20.0, 40.0, 30.0, "filing", 1, 0, 0),
        (10.0, 10.0, 50.0, 18.0, "header", 0, 0, 0),
    ]

    words = spatial_words_from_pymupdf(raw)

    assert [word.text for word in words] == ["header", "filing", "fee"]
    assert [word.order_index for word in words] == [1, 2, 3]
    assert words[1].block_index == 1
    assert words[1].line_index == 0
    assert words[1].word_index == 0
    assert words[1].x_center == 25.0
    assert words[1].y_center == 25.0


def test_native_spatial_page_is_stable_and_bound_to_existing_page_evidence(tmp_path) -> None:
    path = tmp_path / "native.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "CASH ASSESSED: $220,682.90")
    page.insert_text((72, 100), "OTHER USE RATE PER LINEAR FOOT 8.40")
    document.save(path)
    document.close()

    first = extract_native_spatial_page(
        path,
        artifact_id="artifact:test",
        evidence_id="evidence:test-page-1",
        page_number=1,
    )
    second = extract_native_spatial_page(
        path,
        artifact_id="artifact:test",
        evidence_id="evidence:test-page-1",
        page_number=1,
    )

    assert first == second
    assert first.evidence_id == "evidence:test-page-1"
    assert first.artifact_id == "artifact:test"
    assert first.page_number == 1
    assert first.source_text_method == "pymupdf_native_text"
    assert first.spatial_method == "pymupdf_native_words/v1"
    assert first.model_version is None
    assert first.source_text_quality > 0.70
    assert first.words
    assert first.word_signature_sha256 == second.word_signature_sha256
    assert first.spatial_id == second.spatial_id

    with pymupdf.open(path) as reopened:
        expected_text = reopened[0].get_text("text") or ""
    assert first.source_text_sha256 == sha256_text(expected_text)

    lines = first.lines()
    assert len(lines) == 2
    assert "CASH ASSESSED:" in lines[0].text
    assert "$220,682.90" in lines[0].text
    assert lines[0].bbox[0] < lines[0].bbox[2]


def test_native_spatial_page_rejects_invalid_page_number(tmp_path) -> None:
    path = tmp_path / "one-page.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "one")
    document.save(path)
    document.close()

    with pytest.raises(ValueError, match="1-indexed"):
        extract_native_spatial_page(
            path,
            artifact_id="artifact:test",
            evidence_id="evidence:test",
            page_number=0,
        )

    with pytest.raises(ValueError, match="exceeds document length"):
        extract_native_spatial_page(
            path,
            artifact_id="artifact:test",
            evidence_id="evidence:test",
            page_number=2,
        )


def test_parse_ocr_model_version_preserves_existing_provenance_contract() -> None:
    assert parse_ocr_model_version(None) == ("eng", 200)
    assert parse_ocr_model_version("language=eng;dpi=200") == ("eng", 200)
    assert parse_ocr_model_version("language=spa;dpi=300") == ("spa", 300)

    with pytest.raises(ValueError, match="unsupported OCR model version"):
        parse_ocr_model_version("eng@200")
    with pytest.raises(ValueError, match="invalid OCR model version"):
        parse_ocr_model_version("language=eng;dpi=71")
