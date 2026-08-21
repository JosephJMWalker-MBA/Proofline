from __future__ import annotations

from dataclasses import replace

import pytest

from proofline.hashing import sha256_text
from proofline.spatial_anchor import anchor_source_span
from proofline.spatial_text import SpatialPageResult, SpatialWord


def _page(source_text: str, words: tuple[SpatialWord, ...]) -> SpatialPageResult:
    return SpatialPageResult(
        spatial_id="spatial:test-anchor",
        evidence_id="evidence:test-anchor",
        artifact_id="artifact:test-anchor",
        page_number=1,
        page_bbox=(0.0, 0.0, 200.0, 200.0),
        source_text_method="pymupdf_native_text",
        spatial_method="pymupdf_native_words/v1",
        software_version="test",
        model_version=None,
        source_text_sha256=sha256_text(source_text),
        source_text_quality=1.0,
        word_signature_sha256="word-signature:test",
        words=words,
    )


def test_anchor_source_span_preserves_same_line_word_membership() -> None:
    text = "Fee $110,000\n"
    page = _page(
        text,
        (
            SpatialWord(1, "Fee", (10.0, 10.0, 30.0, 20.0), 0, 0, 0),
            SpatialWord(2, "$110,000", (40.0, 10.0, 90.0, 20.0), 0, 0, 1),
        ),
    )

    start = text.index("$110,000")
    anchor = anchor_source_span(page, text, char_start=start, char_end=start + len("$110,000"))

    assert anchor.word_order_indices == (2,)
    assert anchor.line_identities == ((0, 0),)
    assert anchor.crosses_line_identity is False
    assert anchor.anchor_id.startswith("spatial-text-anchor:")


def test_anchor_source_span_binds_currency_symbol_across_line_identity() -> None:
    text = "Total $\n1,699,297\n"
    page = _page(
        text,
        (
            SpatialWord(1, "Total", (10.0, 10.0, 40.0, 20.0), 0, 0, 0),
            SpatialWord(2, "$", (50.0, 10.0, 55.0, 20.0), 0, 0, 1),
            SpatialWord(3, "1,699,297", (50.0, 30.0, 100.0, 40.0), 0, 1, 0),
        ),
    )

    start = text.index("$")
    end = start + len("$\n1,699,297")
    first = anchor_source_span(page, text, char_start=start, char_end=end)
    second = anchor_source_span(page, text, char_start=start, char_end=end)

    assert first == second
    assert first.word_order_indices == (2, 3)
    assert first.line_identities == ((0, 0), (0, 1))
    assert first.crosses_line_identity is True
    serialized = first.to_dict()
    assert serialized["word_order_indices"] == [2, 3]
    assert serialized["line_identities"] == [[0, 0], [0, 1]]


def test_anchor_source_span_rejects_wrong_source_text_lineage() -> None:
    text = "$100\n"
    page = _page(text, (SpatialWord(1, "$100", (10.0, 10.0, 30.0, 20.0), 0, 0, 0),))

    with pytest.raises(ValueError, match="source text does not match"):
        anchor_source_span(page, "$200\n", char_start=0, char_end=4)


def test_anchor_source_span_fails_closed_when_word_alignment_skips_content() -> None:
    text = "A hidden B\n"
    page = _page(
        text,
        (
            SpatialWord(1, "A", (10.0, 10.0, 20.0, 20.0), 0, 0, 0),
            SpatialWord(2, "B", (40.0, 10.0, 50.0, 20.0), 0, 0, 1),
        ),
    )

    with pytest.raises(ValueError, match="skip non-whitespace"):
        anchor_source_span(page, text, char_start=0, char_end=len(text) - 1)


def test_anchor_source_span_rejects_partial_word_and_invalid_method() -> None:
    text = "$100\n"
    page = _page(text, (SpatialWord(1, "$100", (10.0, 10.0, 30.0, 20.0), 0, 0, 0),))

    with pytest.raises(ValueError, match="starts inside"):
        anchor_source_span(page, text, char_start=1, char_end=4)

    with pytest.raises(ValueError, match="method must be non-empty"):
        anchor_source_span(page, text, char_start=0, char_end=4, method="")


def test_anchor_source_span_rejects_duplicate_word_order_indices() -> None:
    text = "A B\n"
    page = _page(
        text,
        (
            SpatialWord(1, "A", (10.0, 10.0, 20.0, 20.0), 0, 0, 0),
            SpatialWord(1, "B", (30.0, 10.0, 40.0, 20.0), 0, 0, 1),
        ),
    )

    with pytest.raises(ValueError, match="duplicate spatial word order index"):
        anchor_source_span(page, text, char_start=0, char_end=3)
