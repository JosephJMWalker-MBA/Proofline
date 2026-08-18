"""Optional OCR backends for progressive evidence extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .extractors import text_quality


@dataclass(frozen=True, slots=True)
class OcrPageResult:
    page_number: int
    text: str
    method: str
    quality_score: float
    software_version: str | None = None
    model_version: str | None = None
    warnings: tuple[str, ...] = ()


class OcrBackend(Protocol):
    """Backend contract used by the progressive extractor."""

    name: str

    def extract_page(self, path: str | Path, page_number: int) -> OcrPageResult:
        """OCR one 1-indexed PDF page without changing evidence identity."""


class PyMuPDFTesseractBackend:
    """Use PyMuPDF's Tesseract bridge when a local Tesseract install exists.

    Tesseract remains an external optional runtime dependency. Importing or
    using Proofline does not require it until this backend is invoked.
    """

    name = "pymupdf_tesseract_ocr"

    def __init__(self, *, language: str = "eng", dpi: int = 200) -> None:
        if dpi < 72:
            raise ValueError("OCR dpi must be at least 72")
        self.language = language
        self.dpi = dpi

    def extract_page(self, path: str | Path, page_number: int) -> OcrPageResult:
        import pymupdf

        if page_number < 1:
            raise ValueError("page_number must be 1-indexed and positive")

        with pymupdf.open(str(path)) as document:
            if page_number > len(document):
                raise ValueError(f"page {page_number} exceeds document length {len(document)}")
            page = document[page_number - 1]
            try:
                text_page = page.get_textpage_ocr(
                    language=self.language,
                    dpi=self.dpi,
                    full=True,
                )
            except Exception as exc:
                raise RuntimeError(
                    "Tesseract OCR is unavailable or failed. Install Tesseract and the requested "
                    f"language data before using this backend: {exc}"
                ) from exc
            text = page.get_text("text", textpage=text_page) or ""

        quality = text_quality(text)
        warnings: tuple[str, ...] = ()
        if quality < 0.70:
            warnings = ("OCR text remains below the default review threshold",)
        return OcrPageResult(
            page_number=page_number,
            text=text,
            method=self.name,
            quality_score=quality,
            software_version=f"PyMuPDF {pymupdf.VersionBind}; Tesseract via PyMuPDF",
            model_version=f"language={self.language};dpi={self.dpi}",
            warnings=warnings,
        )
