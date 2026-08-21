"""Deterministic, non-canonical probing of native PDF table structure.

This module deliberately does not alter ingestion, Silver evidence identity, search,
or structured facts. It exposes layout evidence so experiments can measure whether
native PDF geometry is sufficient before Proofline adopts any canonical structure
representation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


def _bbox(value) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if len(value) != 4:
        raise ValueError("PDF table bounding boxes must contain exactly four coordinates")
    return tuple(round(float(part), 3) for part in value)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class PdfTableCell:
    row_index: int
    column_index: int
    bbox: tuple[float, float, float, float] | None
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PdfTableStructure:
    page_number: int
    table_index: int
    bbox: tuple[float, float, float, float]
    row_count: int
    column_count: int
    header_names: tuple[str, ...]
    header_external: bool
    cells: tuple[PdfTableCell, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["cells"] = [cell.to_dict() for cell in self.cells]
        return data


@dataclass(frozen=True, slots=True)
class PdfTableProbeFailure:
    page_number: int
    error_type: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PdfTableProbeResult:
    page_count: int
    method: str
    software_version: str
    tables: tuple[PdfTableStructure, ...]
    failures: tuple[PdfTableProbeFailure, ...]

    def to_dict(self) -> dict:
        return {
            "page_count": self.page_count,
            "method": self.method,
            "software_version": self.software_version,
            "table_count": len(self.tables),
            "failure_count": len(self.failures),
            "tables": [table.to_dict() for table in self.tables],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def _table_sort_key(table) -> tuple:
    bbox = _bbox(table.bbox)
    if bbox is None:
        raise ValueError("detected PDF table has no bounding box")
    extracted = table.extract() or []
    text_key = tuple(tuple("" if cell is None else str(cell) for cell in row) for row in extracted)
    return (*bbox, int(table.row_count), int(table.col_count), text_key)


def _serialize_table(table, *, page_number: int, table_index: int) -> PdfTableStructure:
    bbox = _bbox(table.bbox)
    if bbox is None:
        raise ValueError("detected PDF table has no bounding box")

    extracted = table.extract() or []
    cells: list[PdfTableCell] = []
    for row_index in range(int(table.row_count)):
        row_values = extracted[row_index] if row_index < len(extracted) else []
        row_boxes = table.rows[row_index].cells if row_index < len(table.rows) else []
        for column_index in range(int(table.col_count)):
            value = row_values[column_index] if column_index < len(row_values) else ""
            box = row_boxes[column_index] if column_index < len(row_boxes) else None
            cells.append(
                PdfTableCell(
                    row_index=row_index,
                    column_index=column_index,
                    bbox=_bbox(box),
                    text="" if value is None else str(value),
                )
            )

    header = table.header
    header_names = tuple("" if value is None else str(value) for value in (header.names or []))
    return PdfTableStructure(
        page_number=page_number,
        table_index=table_index,
        bbox=bbox,
        row_count=int(table.row_count),
        column_count=int(table.col_count),
        header_names=header_names,
        header_external=bool(header.external),
        cells=tuple(cells),
    )


def probe_pdf_tables(
    path: str | Path,
    *,
    page_numbers: set[int] | None = None,
) -> PdfTableProbeResult:
    """Measure native table geometry without changing canonical evidence.

    ``page_numbers`` is one-based when supplied. A page-level detection failure is
    recorded and probing continues so a single malformed page cannot silently erase
    measurements from the rest of the artifact.
    """
    import pymupdf

    source = Path(path)
    method = "pymupdf_find_tables_default_lines/v1"
    software_version = f"PyMuPDF {pymupdf.VersionBind}"
    tables: list[PdfTableStructure] = []
    failures: list[PdfTableProbeFailure] = []

    with pymupdf.open(str(source)) as document:
        page_count = len(document)
        if page_numbers is not None:
            invalid = sorted(number for number in page_numbers if number < 1 or number > page_count)
            if invalid:
                raise ValueError(f"requested PDF page numbers are out of range: {invalid}")

        for page_index, page in enumerate(document):
            page_number = page_index + 1
            if page_numbers is not None and page_number not in page_numbers:
                continue
            try:
                detected = sorted(page.find_tables().tables, key=_table_sort_key)
                for table_index, table in enumerate(detected, start=1):
                    tables.append(
                        _serialize_table(
                            table,
                            page_number=page_number,
                            table_index=table_index,
                        )
                    )
            except Exception as exc:  # page-level provenance is more useful than all-or-nothing failure
                failures.append(
                    PdfTableProbeFailure(
                        page_number=page_number,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )

    return PdfTableProbeResult(
        page_count=page_count,
        method=method,
        software_version=software_version,
        tables=tuple(tables),
        failures=tuple(failures),
    )
