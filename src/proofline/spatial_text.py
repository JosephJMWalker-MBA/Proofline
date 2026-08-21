"""Deterministic spatial text derivation for PDF evidence.

R1.T17 deliberately keeps this layer parallel to canonical Silver. It preserves
word geometry from the same native or OCR text page used for flat extraction,
without changing evidence units, search, structured facts, or financial semantics.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .extractors import text_quality
from .hashing import sha256_text, stable_id


BBox = tuple[float, float, float, float]


def _bbox(value) -> BBox:
    if value is None or len(value) != 4:
        raise ValueError("spatial word/page bounding boxes must contain four coordinates")
    return tuple(round(float(part), 3) for part in value)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class SpatialWord:
    order_index: int
    text: str
    bbox: BBox
    block_index: int
    line_index: int
    word_index: int

    @property
    def x_center(self) -> float:
        return round((self.bbox[0] + self.bbox[2]) / 2.0, 3)

    @property
    def y_center(self) -> float:
        return round((self.bbox[1] + self.bbox[3]) / 2.0, 3)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["bbox"] = list(self.bbox)
        data["x_center"] = self.x_center
        data["y_center"] = self.y_center
        return data


@dataclass(frozen=True, slots=True)
class SpatialLine:
    block_index: int
    line_index: int
    bbox: BBox
    text: str
    words: tuple[SpatialWord, ...]

    def to_dict(self) -> dict:
        return {
            "block_index": self.block_index,
            "line_index": self.line_index,
            "bbox": list(self.bbox),
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }


@dataclass(frozen=True, slots=True)
class SpatialPageResult:
    spatial_id: str
    evidence_id: str
    artifact_id: str
    page_number: int
    page_bbox: BBox
    source_text_method: str
    spatial_method: str
    software_version: str
    model_version: str | None
    source_text_sha256: str
    source_text_quality: float
    word_signature_sha256: str
    words: tuple[SpatialWord, ...]

    def lines(self) -> tuple[SpatialLine, ...]:
        grouped: dict[tuple[int, int], list[SpatialWord]] = {}
        for word in self.words:
            grouped.setdefault((word.block_index, word.line_index), []).append(word)

        lines: list[SpatialLine] = []
        for (block_index, line_index), words in sorted(grouped.items()):
            ordered = sorted(words, key=lambda item: (item.word_index, item.bbox, item.text))
            x0 = min(word.bbox[0] for word in ordered)
            y0 = min(word.bbox[1] for word in ordered)
            x1 = max(word.bbox[2] for word in ordered)
            y1 = max(word.bbox[3] for word in ordered)
            lines.append(
                SpatialLine(
                    block_index=block_index,
                    line_index=line_index,
                    bbox=(x0, y0, x1, y1),
                    text=" ".join(word.text for word in ordered),
                    words=tuple(ordered),
                )
            )
        return tuple(lines)

    def to_dict(self) -> dict:
        return {
            "spatial_id": self.spatial_id,
            "evidence_id": self.evidence_id,
            "artifact_id": self.artifact_id,
            "page_number": self.page_number,
            "page_bbox": list(self.page_bbox),
            "source_text_method": self.source_text_method,
            "spatial_method": self.spatial_method,
            "software_version": self.software_version,
            "model_version": self.model_version,
            "source_text_sha256": self.source_text_sha256,
            "source_text_quality": self.source_text_quality,
            "word_signature_sha256": self.word_signature_sha256,
            "word_count": len(self.words),
            "line_count": len(self.lines()),
            "words": [word.to_dict() for word in self.words],
        }


def spatial_words_from_pymupdf(raw_words) -> tuple[SpatialWord, ...]:
    """Normalize PyMuPDF word tuples into a deterministic common contract."""
    normalized: list[tuple[BBox, str, int, int, int]] = []
    for raw in raw_words or []:
        if len(raw) < 8:
            raise ValueError(f"unexpected PyMuPDF word tuple: {raw!r}")
        box = _bbox(raw[:4])
        text = "" if raw[4] is None else str(raw[4])
        normalized.append((box, text, int(raw[5]), int(raw[6]), int(raw[7])))

    normalized.sort(
        key=lambda item: (
            item[2],
            item[3],
            item[4],
            item[0][1],
            item[0][0],
            item[0][3],
            item[0][2],
            item[1],
        )
    )
    return tuple(
        SpatialWord(
            order_index=index,
            text=text,
            bbox=box,
            block_index=block_index,
            line_index=line_index,
            word_index=word_index,
        )
        for index, (box, text, block_index, line_index, word_index) in enumerate(
            normalized, start=1
        )
    )


def _word_signature(words: tuple[SpatialWord, ...]) -> str:
    payload = [
        {
            "order_index": word.order_index,
            "text": word.text,
            "bbox": list(word.bbox),
            "block_index": word.block_index,
            "line_index": word.line_index,
            "word_index": word.word_index,
        }
        for word in words
    ]
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _result(
    *,
    artifact_id: str,
    evidence_id: str,
    page_number: int,
    page_bbox,
    source_text: str,
    source_text_method: str,
    spatial_method: str,
    software_version: str,
    model_version: str | None,
    raw_words,
) -> SpatialPageResult:
    words = spatial_words_from_pymupdf(raw_words)
    source_text_sha256 = sha256_text(source_text)
    word_signature_sha256 = _word_signature(words)
    spatial_id = stable_id(
        "spatial",
        evidence_id,
        source_text_method,
        source_text_sha256,
        spatial_method,
        software_version,
        model_version or "",
        word_signature_sha256,
    )
    return SpatialPageResult(
        spatial_id=spatial_id,
        evidence_id=evidence_id,
        artifact_id=artifact_id,
        page_number=page_number,
        page_bbox=_bbox(page_bbox),
        source_text_method=source_text_method,
        spatial_method=spatial_method,
        software_version=software_version,
        model_version=model_version,
        source_text_sha256=source_text_sha256,
        source_text_quality=text_quality(source_text),
        word_signature_sha256=word_signature_sha256,
        words=words,
    )


def extract_native_spatial_page(
    path: str | Path,
    *,
    artifact_id: str,
    evidence_id: str,
    page_number: int,
) -> SpatialPageResult:
    """Extract native flat text and native word geometry from the same PDF page."""
    import pymupdf

    if page_number < 1:
        raise ValueError("page_number must be 1-indexed and positive")
    with pymupdf.open(str(path)) as document:
        if page_number > len(document):
            raise ValueError(f"page {page_number} exceeds document length {len(document)}")
        page = document[page_number - 1]
        text = page.get_text("text") or ""
        raw_words = page.get_text("words", sort=False) or []
        return _result(
            artifact_id=artifact_id,
            evidence_id=evidence_id,
            page_number=page_number,
            page_bbox=page.rect,
            source_text=text,
            source_text_method="pymupdf_native_text",
            spatial_method="pymupdf_native_words/v1",
            software_version=f"PyMuPDF {pymupdf.VersionBind}",
            model_version=None,
            raw_words=raw_words,
        )


def extract_ocr_spatial_page(
    path: str | Path,
    *,
    artifact_id: str,
    evidence_id: str,
    page_number: int,
    language: str = "eng",
    dpi: int = 200,
) -> SpatialPageResult:
    """Extract OCR flat text and OCR word geometry from the same Tesseract TextPage."""
    import pymupdf

    if page_number < 1:
        raise ValueError("page_number must be 1-indexed and positive")
    if dpi < 72:
        raise ValueError("OCR dpi must be at least 72")
    with pymupdf.open(str(path)) as document:
        if page_number > len(document):
            raise ValueError(f"page {page_number} exceeds document length {len(document)}")
        page = document[page_number - 1]
        try:
            text_page = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
        except Exception as exc:
            raise RuntimeError(
                "Tesseract OCR is unavailable or failed. Install Tesseract and the requested "
                f"language data before spatial OCR extraction: {exc}"
            ) from exc
        text = page.get_text("text", textpage=text_page) or ""
        raw_words = page.get_text("words", textpage=text_page, sort=False) or []
        return _result(
            artifact_id=artifact_id,
            evidence_id=evidence_id,
            page_number=page_number,
            page_bbox=page.rect,
            source_text=text,
            source_text_method="pymupdf_tesseract_ocr",
            spatial_method="pymupdf_tesseract_words/v1",
            software_version=f"PyMuPDF {pymupdf.VersionBind}; Tesseract via PyMuPDF",
            model_version=f"language={language};dpi={dpi}",
            raw_words=raw_words,
        )


def parse_ocr_model_version(model_version: str | None) -> tuple[str, int]:
    """Recover Tesseract language/dpi from Proofline's existing OCR provenance string."""
    if not model_version:
        return "eng", 200
    match = re.fullmatch(r"language=([^;]+);dpi=(\d+)", model_version.strip())
    if match is None:
        raise ValueError(f"unsupported OCR model version: {model_version!r}")
    language = match.group(1)
    dpi = int(match.group(2))
    if not language or dpi < 72:
        raise ValueError(f"invalid OCR model version: {model_version!r}")
    return language, dpi
