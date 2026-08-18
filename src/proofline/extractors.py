"""Deterministic native extraction before any OCR escalation."""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path

from .models import EvidenceUnitType


@dataclass(frozen=True, slots=True)
class ExtractedUnit:
    unit_type: EvidenceUnitType
    locator: str
    text: str | None
    method: str
    quality_score: float
    warnings: tuple[str, ...] = ()


def text_quality(text: str | None) -> float:
    """Estimate whether extracted text resembles usable text, not factual correctness."""
    if not text or not text.strip():
        return 0.0
    stripped = text.strip()
    total = len(stripped)
    printable_ratio = sum(ch in string.printable for ch in stripped) / total
    readable_ratio = sum(ch.isalnum() or ch.isspace() or ch in string.punctuation for ch in stripped) / total
    length_score = min(1.0, total / 80.0)
    return round(max(0.0, min(1.0, 0.45 * printable_ratio + 0.45 * readable_ratio + 0.10 * length_score)), 4)


def extract_pdf_native(path: str | Path) -> list[ExtractedUnit]:
    import fitz

    units: list[ExtractedUnit] = []
    with fitz.open(str(path)) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text")
            quality = text_quality(text)
            warnings: tuple[str, ...] = ()
            if quality < 0.70:
                warnings = ("native text is absent or low quality; OCR review may be needed",)
            units.append(
                ExtractedUnit(
                    unit_type=EvidenceUnitType.PAGE,
                    locator=f"page:{page_index + 1}",
                    text=text or None,
                    method="pymupdf_native_text",
                    quality_score=quality,
                    warnings=warnings,
                )
            )
    return units


def extract_plain_text(path: str | Path) -> list[ExtractedUnit]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    quality = text_quality(text)
    warnings = () if quality >= 0.70 else ("text content is low quality",)
    return [
        ExtractedUnit(
            unit_type=EvidenceUnitType.RECORD,
            locator="record:1",
            text=text,
            method="utf8_text",
            quality_score=quality,
            warnings=warnings,
        )
    ]


def extract_native(path: str | Path, media_type: str | None) -> list[ExtractedUnit]:
    if media_type == "application/pdf" or Path(path).suffix.lower() == ".pdf":
        return extract_pdf_native(path)
    if media_type and media_type.startswith("text/"):
        return extract_plain_text(path)
    return []
