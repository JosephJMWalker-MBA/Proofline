from __future__ import annotations

import pytest

from proofline.hashing import sha256_text
from proofline.spatial_anchor import SPATIAL_TEXT_ANCHOR_METHOD, anchor_source_span
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


def test_anchor_method_is_v2() -> None:
    assert SPATIAL_TEXT_ANCHOR_METHOD == "proofline-spatial-text-anchor/source-span-v2"


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
    assert anchor.leading_boundary_punctuation == ""
    assert anchor.trailing_boundary_punctuation == ""
    assert anchor.expanded_to_word_boundary is False
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
    assert first.expanded_to_word_boundary is False
    serialized = first.to_dict()
    assert serialized["word_order_indices"] == [2, 3]
    assert serialized["line_identities"] == [[0, 0], [0, 1]]


def test_anchor_source_span_expands_over_trailing_unicode_punctuation_only() -> None:
    text = "Paid $57,988.38, next\n"
    page = _page(
        text,
        (
            SpatialWord(1, "Paid", (10.0, 10.0, 30.0, 20.0), 0, 0, 0),
            SpatialWord(2, "$57,988.38,", (40.0, 10.0, 100.0, 20.0), 0, 0, 1),
            SpatialWord(3, "next", (110.0, 10.0, 140.0, 20.0), 0, 0, 2),
        ),
    )

    raw = "$57,988.38"
    start = text.index(raw)
    anchor = anchor_source_span(page, text, char_start=start, char_end=start + len(raw))

    assert anchor.word_order_indices == (2,)
    assert anchor.leading_boundary_punctuation == ""
    assert anchor.trailing_boundary_punctuation == ","
    assert anchor.expanded_to_word_boundary is True


def test_anchor_source_span_expands_over_leading_and_trailing_unicode_punctuation() -> None:
    text = "($100)\n"
    page = _page(
        text,
        (SpatialWord(1, "($100)", (10.0, 10.0, 50.0, 20.0), 0, 0, 0),),
    )

    start = text.index("$100")
    anchor = anchor_source_span(page, text, char_start=start, char_end=start + len("$100"))

    assert anchor.word_order_indices == (1,)
    assert anchor.leading_boundary_punctuation == "("
    assert anchor.trailing_boundary_punctuation == ")"
    assert anchor.expanded_to_word_boundary is True


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


def test_anchor_source_span_rejects_expansion_over_letters_or_digits() -> None:
    text = "$100USD\n"
    page = _page(
        text,
        (SpatialWord(1, "$100USD", (10.0, 10.0, 60.0, 20.0), 0, 0, 0),),
    )

    with pytest.raises(ValueError, match="ends inside substantive"):
        anchor_source_span(page, text, char_start=0, char_end=4)

    text2 = "X$100\n"
    page2 = _page(
        text2,
        (SpatialWord(1, "X$100", (10.0, 10.0, 50.0, 20.0), 0, 0, 0),),
    )
    with pytest.raises(ValueError, match="starts inside substantive"):
        anchor_source_span(page2, text2, char_start=1, char_end=5)


def test_anchor_source_span_rejects_expansion_over_non_punctuation_symbol() -> None:
    text = "$100+\n"
    page = _page(
        text,
        (SpatialWord(1, "$100+", (10.0, 10.0, 50.0, 20.0), 0, 0, 0),),
    )

    with pytest.raises(ValueError, match="ends inside substantive"):
        anchor_source_span(page, text, char_start=0, char_end=4)


def test_anchor_source_span_requires_nonempty_method() -> None:
    text = "$100\n"
    page = _page(text, (SpatialWord(1, "$100", (10.0, 10.0, 30.0, 20.0), 0, 0, 0),))

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
