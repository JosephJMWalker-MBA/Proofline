"""Deterministic source-text span anchoring into spatial word geometry.

R1.T20 introduces this layer after T19b showed that reparsing isolated spatial
lines can lose already-valid page-level facts whose source span crosses extractor
line identity. The anchor consumes an existing source-text span; it does not
parse, classify, or assign semantics.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass

from .hashing import sha256_text, stable_id
from .spatial_text import SpatialPageResult, SpatialWord


SPATIAL_TEXT_ANCHOR_METHOD = "proofline-spatial-text-anchor/source-span-v2"


@dataclass(frozen=True, slots=True)
class SpatialTextAnchor:
    anchor_id: str
    method: str
    spatial_id: str
    evidence_id: str
    source_text_sha256: str
    source_span_sha256: str
    char_start: int
    char_end: int
    word_order_indices: tuple[int, ...]
    line_identities: tuple[tuple[int, int], ...]
    crosses_line_identity: bool
    leading_boundary_punctuation: str
    trailing_boundary_punctuation: str
    expanded_to_word_boundary: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        data["word_order_indices"] = list(self.word_order_indices)
        data["line_identities"] = [list(item) for item in self.line_identities]
        return data


@dataclass(frozen=True, slots=True)
class _AlignedWord:
    word: SpatialWord
    char_start: int
    char_end: int


def _align_words_to_source(
    page: SpatialPageResult,
    source_text: str,
) -> tuple[_AlignedWord, ...]:
    """Align spatial words to the exact source text in deterministic source order.

    The page text and word geometry come from the same native/OCR extraction.
    Alignment may cross arbitrary whitespace but fails if it would need to skip
    non-whitespace source content.
    """
    if sha256_text(source_text) != page.source_text_sha256:
        raise ValueError("spatial anchor source text does not match page source-text hash")

    cursor = 0
    aligned: list[_AlignedWord] = []
    seen_order_indices: set[int] = set()
    for word in page.words:
        if word.order_index in seen_order_indices:
            raise ValueError(f"duplicate spatial word order index: {word.order_index}")
        seen_order_indices.add(word.order_index)
        if not word.text:
            raise ValueError(f"spatial word {word.order_index} has empty text")

        start = source_text.find(word.text, cursor)
        if start < 0:
            raise ValueError(
                f"cannot align spatial word {word.order_index} to source text after char {cursor}"
            )
        skipped = source_text[cursor:start]
        if skipped and not skipped.isspace():
            raise ValueError(
                "spatial/source alignment would skip non-whitespace content before "
                f"word {word.order_index}"
            )
        end = start + len(word.text)
        aligned.append(_AlignedWord(word=word, char_start=start, char_end=end))
        cursor = end

    tail = source_text[cursor:]
    if tail and not tail.isspace():
        raise ValueError("spatial/source alignment leaves trailing non-whitespace content")
    return tuple(aligned)


def _is_unicode_punctuation_only(text: str) -> bool:
    return bool(text) and all(unicodedata.category(char).startswith("P") for char in text)


def anchor_source_span(
    page: SpatialPageResult,
    source_text: str,
    *,
    char_start: int,
    char_end: int,
    method: str = SPATIAL_TEXT_ANCHOR_METHOD,
) -> SpatialTextAnchor:
    """Bind one existing source-text span to the spatial words that realize it.

    Whitespace inside the source span does not need its own word geometry. Every
    non-whitespace character in the span must be covered by aligned spatial words.

    PyMuPDF may retain adjacent prose punctuation in the same spatial word token
    even when the structured parser correctly terminates a fact before/after that
    punctuation. V2 therefore permits deterministic word-boundary expansion only
    across Unicode punctuation. Expansion across letters, digits, currency symbols,
    or other substantive symbols remains a hard failure and is never guessed away.
    """
    if not method:
        raise ValueError("spatial anchor method must be non-empty")
    if char_start < 0 or char_end <= char_start or char_end > len(source_text):
        raise ValueError("spatial anchor source span is out of bounds or empty")

    source_span = source_text[char_start:char_end]
    if not source_span.strip():
        raise ValueError("spatial anchor source span must contain non-whitespace content")

    aligned = _align_words_to_source(page, source_text)
    selected = [
        item
        for item in aligned
        if item.char_start < char_end and item.char_end > char_start
    ]
    if not selected:
        raise ValueError("spatial anchor span has no overlapping spatial words")

    leading_boundary_punctuation = ""
    trailing_boundary_punctuation = ""

    first = selected[0]
    if first.char_start < char_start:
        prefix = source_text[first.char_start:char_start]
        if not _is_unicode_punctuation_only(prefix):
            raise ValueError("spatial anchor span starts inside substantive spatial-word content")
        leading_boundary_punctuation = prefix

    last = selected[-1]
    if last.char_end > char_end:
        suffix = source_text[char_end:last.char_end]
        if not _is_unicode_punctuation_only(suffix):
            raise ValueError("spatial anchor span ends inside substantive spatial-word content")
        trailing_boundary_punctuation = suffix

    covered: set[int] = set()
    for item in selected:
        left = max(char_start, item.char_start)
        right = min(char_end, item.char_end)
        covered.update(range(left, right))
    uncovered_non_whitespace = [
        index
        for index in range(char_start, char_end)
        if not source_text[index].isspace() and index not in covered
    ]
    if uncovered_non_whitespace:
        raise ValueError(
            "spatial anchor span contains non-whitespace content without word geometry: "
            f"{uncovered_non_whitespace}"
        )

    word_order_indices = tuple(item.word.order_index for item in selected)
    line_identities_list: list[tuple[int, int]] = []
    for item in selected:
        identity = (item.word.block_index, item.word.line_index)
        if identity not in line_identities_list:
            line_identities_list.append(identity)
    line_identities = tuple(line_identities_list)
    source_span_sha256 = sha256_text(source_span)
    expanded_to_word_boundary = bool(
        leading_boundary_punctuation or trailing_boundary_punctuation
    )

    return SpatialTextAnchor(
        anchor_id=stable_id(
            "spatial-text-anchor",
            method,
            page.spatial_id,
            page.evidence_id,
            str(char_start),
            str(char_end),
            ",".join(str(index) for index in word_order_indices),
            source_span_sha256,
            leading_boundary_punctuation,
            trailing_boundary_punctuation,
        ),
        method=method,
        spatial_id=page.spatial_id,
        evidence_id=page.evidence_id,
        source_text_sha256=page.source_text_sha256,
        source_span_sha256=source_span_sha256,
        char_start=char_start,
        char_end=char_end,
        word_order_indices=word_order_indices,
        line_identities=line_identities,
        crosses_line_identity=len(line_identities) > 1,
        leading_boundary_punctuation=leading_boundary_punctuation,
        trailing_boundary_punctuation=trailing_boundary_punctuation,
        expanded_to_word_boundary=expanded_to_word_boundary,
    )
