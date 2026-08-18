"""Deterministic native extraction before any OCR escalation."""

from __future__ import annotations

import csv
import json
import platform
from collections.abc import Iterator
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
    software_version: str | None = None
    model_version: str | None = None
    warnings: tuple[str, ...] = ()


def text_quality(text: str | None) -> float:
    """Estimate text usability without assuming English or Latin characters."""
    if not text or not text.strip():
        return 0.0

    stripped = text.strip()
    total = len(stripped)
    printable_ratio = sum(ch.isprintable() or ch in "\n\r\t" for ch in stripped) / total
    alnum_space_ratio = sum(ch.isalnum() or ch.isspace() for ch in stripped) / total
    structure_score = min(1.0, alnum_space_ratio / 0.55)
    length_score = min(1.0, total / 80.0)
    replacement_ratio = stripped.count("\ufffd") / total

    score = 0.55 * printable_ratio + 0.30 * structure_score + 0.15 * length_score
    score -= min(0.50, replacement_ratio * 4.0)
    return round(max(0.0, min(1.0, score)), 4)


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _structured_row_text(headers: list[str], values: list[object]) -> str:
    raw = ["" if value is None else str(value) for value in values]
    mapping: dict[str, str] = {}
    for index, value in enumerate(raw):
        key = headers[index].strip() if index < len(headers) and headers[index].strip() else _column_name(index)
        if key in mapping:
            key = f"{key}__{_column_name(index)}"
        mapping[key] = value
    return json.dumps({"columns": mapping, "raw": raw}, ensure_ascii=False, sort_keys=True)


def _header_row_text(values: list[object]) -> str:
    raw = ["" if value is None else str(value) for value in values]
    return json.dumps(
        {"columns": {_column_name(i): value for i, value in enumerate(raw)}, "raw": raw},
        ensure_ascii=False,
        sort_keys=True,
    )


def extract_pdf_native(path: str | Path) -> Iterator[ExtractedUnit]:
    import fitz

    software_version = f"PyMuPDF {fitz.VersionBind}"
    with fitz.open(str(path)) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text")
            quality = text_quality(text)
            warnings: tuple[str, ...] = ()
            if quality < 0.70:
                warnings = ("native text is absent or low quality; OCR review may be needed",)
            yield ExtractedUnit(
                unit_type=EvidenceUnitType.PAGE,
                locator=f"page:{page_index + 1}",
                text=text or None,
                method="pymupdf_native_text",
                quality_score=quality,
                software_version=software_version,
                warnings=warnings,
            )


def extract_plain_text(path: str | Path) -> Iterator[ExtractedUnit]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    quality = text_quality(text)
    warnings = () if quality >= 0.70 else ("text content is low quality",)
    yield ExtractedUnit(
        unit_type=EvidenceUnitType.RECORD,
        locator="record:1",
        text=text,
        method="utf8_text",
        quality_score=quality,
        software_version=f"Python {platform.python_version()}",
        warnings=warnings,
    )


def extract_csv(path: str | Path) -> Iterator[ExtractedUnit]:
    software_version = f"Python {platform.python_version()}"
    with Path(path).open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        first_row = next(reader, None)
        if first_row is None:
            return

        headers = [cell.strip() or _column_name(index) for index, cell in enumerate(first_row)]
        if any(str(value).strip() for value in first_row):
            last_column = _column_name(max(0, len(first_row) - 1))
            yield ExtractedUnit(
                unit_type=EvidenceUnitType.SPREADSHEET_RANGE,
                locator=f"sheet:CSV!A1:{last_column}1",
                text=_header_row_text(first_row),
                method="python_csv",
                quality_score=1.0,
                software_version=software_version,
            )

        for row_index, row in enumerate(reader, start=2):
            if not any(str(value).strip() for value in row):
                continue
            last_column = _column_name(max(0, len(row) - 1))
            yield ExtractedUnit(
                unit_type=EvidenceUnitType.SPREADSHEET_RANGE,
                locator=f"sheet:CSV!A{row_index}:{last_column}{row_index}",
                text=_structured_row_text(headers, row),
                method="python_csv",
                quality_score=1.0,
                software_version=software_version,
            )


def extract_xlsx(path: str | Path) -> Iterator[ExtractedUnit]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
    software_version = f"openpyxl {openpyxl.__version__}"
    warning = ("formulas are preserved as source expressions and are not evaluated",)
    try:
        for sheet in workbook.worksheets:
            row_iterator = sheet.iter_rows(values_only=True)
            first_row = next(row_iterator, None)
            if first_row is None:
                continue

            first_values = list(first_row)
            headers = ["" if value is None else str(value) for value in first_values]
            if any(value is not None and str(value).strip() for value in first_values):
                last_column = _column_name(max(0, len(first_values) - 1))
                yield ExtractedUnit(
                    unit_type=EvidenceUnitType.SPREADSHEET_RANGE,
                    locator=f"sheet:{sheet.title}!A1:{last_column}1",
                    text=_header_row_text(first_values),
                    method="openpyxl_values_and_formulas",
                    quality_score=1.0,
                    software_version=software_version,
                    warnings=warning,
                )

            for row_index, row in enumerate(row_iterator, start=2):
                values = list(row)
                if not any(value is not None and str(value).strip() for value in values):
                    continue
                last_column = _column_name(max(0, len(values) - 1))
                yield ExtractedUnit(
                    unit_type=EvidenceUnitType.SPREADSHEET_RANGE,
                    locator=f"sheet:{sheet.title}!A{row_index}:{last_column}{row_index}",
                    text=_structured_row_text(headers, values),
                    method="openpyxl_values_and_formulas",
                    quality_score=1.0,
                    software_version=software_version,
                    warnings=warning,
                )
    finally:
        workbook.close()


def extract_native(path: str | Path, media_type: str | None) -> Iterator[ExtractedUnit]:
    suffix = Path(path).suffix.lower()
    normalized_type = (media_type or "").split(";", 1)[0].strip().lower()

    if normalized_type == "application/pdf" or suffix == ".pdf":
        return extract_pdf_native(path)
    if normalized_type == "text/csv" or suffix == ".csv":
        return extract_csv(path)
    if normalized_type in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel.sheet.macroenabled.12",
    } or suffix in {".xlsx", ".xlsm"}:
        return extract_xlsx(path)
    if normalized_type.startswith("text/") or normalized_type in {
        "application/json",
        "application/xml",
        "application/xhtml+xml",
    } or suffix in {".txt", ".md", ".json", ".xml"}:
        return extract_plain_text(path)
    return iter(())
