from __future__ import annotations

import pymupdf
import pytest

from proofline.pdf_structure import probe_pdf_tables


def _write_table_pdf(path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    x0, y0 = 72.0, 72.0
    cell_width, cell_height = 120.0, 30.0

    for row in range(4):
        page.draw_line((x0, y0 + row * cell_height), (x0 + 2 * cell_width, y0 + row * cell_height))
    for column in range(3):
        page.draw_line((x0 + column * cell_width, y0), (x0 + column * cell_width, y0 + 3 * cell_height))

    rows = [
        ("Estimated TOTAL Project Cost", "Applicable Fee"),
        ("$0 - $20,000", "$250"),
        ("$20,001 - $100,000", "$750"),
    ]
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            page.insert_text(
                (x0 + column_index * cell_width + 4, y0 + row_index * cell_height + 20),
                text,
                fontsize=7,
            )

    document.save(path)
    document.close()


def test_native_pdf_table_probe_preserves_row_column_geometry(tmp_path) -> None:
    path = tmp_path / "fee-schedule.pdf"
    _write_table_pdf(path)

    result = probe_pdf_tables(path)

    assert result.page_count == 1
    assert result.method == "pymupdf_find_tables_default_lines/v1"
    assert result.software_version.startswith("PyMuPDF ")
    assert result.failures == ()
    assert len(result.tables) == 1

    table = result.tables[0]
    assert table.page_number == 1
    assert table.table_index == 1
    assert table.row_count == 3
    assert table.column_count == 2
    assert table.header_names == ("Estimated TOTAL Project Cost", "Applicable Fee")
    assert table.header_external is False

    cells = {(cell.row_index, cell.column_index): cell for cell in table.cells}
    assert cells[(1, 0)].text == "$0 - $20,000"
    assert cells[(1, 1)].text == "$250"
    assert cells[(2, 0)].text == "$20,001 - $100,000"
    assert cells[(2, 1)].text == "$750"
    assert cells[(1, 0)].bbox is not None
    assert cells[(1, 0)].bbox[0] < cells[(1, 1)].bbox[0]
    assert cells[(1, 0)].bbox[1] == cells[(1, 1)].bbox[1]


def test_native_pdf_table_probe_retains_legitimate_null_result(tmp_path) -> None:
    path = tmp_path / "plain.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "This page has no table.")
    document.save(path)
    document.close()

    result = probe_pdf_tables(path)

    assert result.page_count == 1
    assert result.tables == ()
    assert result.failures == ()


def test_native_pdf_table_probe_can_be_bounded_to_declared_pages(tmp_path) -> None:
    path = tmp_path / "two-pages.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "page one")
    document.new_page().insert_text((72, 72), "page two")
    document.save(path)
    document.close()

    result = probe_pdf_tables(path, page_numbers={2})
    assert result.page_count == 2
    assert result.tables == ()
    assert result.failures == ()

    with pytest.raises(ValueError, match="out of range"):
        probe_pdf_tables(path, page_numbers={3})
