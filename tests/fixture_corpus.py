"""Generate a small, deliberately difficult public-record fixture corpus."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import fitz
import openpyxl


def _make_born_digital_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Contract award: $250,000\nVendor: Northstar Civic Systems")
    document.save(path)
    document.close()


def _make_scanned_pdf(path: Path) -> None:
    source = fitz.open()
    page = source.new_page()
    page.insert_text((72, 72), "Scanned memorandum: emergency procurement review")
    pixmap = page.get_pixmap(dpi=150)
    image_bytes = pixmap.tobytes("png")
    source.close()

    scanned = fitz.open()
    scanned_page = scanned.new_page(width=pixmap.width, height=pixmap.height)
    scanned_page.insert_image(scanned_page.rect, stream=image_bytes)
    scanned.save(path)
    scanned.close()


def _make_formula_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Awards"
    sheet.append(["contract_id", "vendor", "base_amount", "calculated_amount"])
    sheet.append(["C-002", "Lakeview Systems", 125000, "=C2*2"])
    workbook.save(path)
    workbook.close()


def build_fixture_corpus(root: str | Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    born_digital = root / "born_digital.pdf"
    scanned = root / "scanned.pdf"
    duplicate = root / "duplicate_of_born_digital.pdf"
    corrupted = root / "corrupted.pdf"
    version_one = root / "source_version_1.txt"
    version_two = root / "source_version_2.txt"
    conflict_a = root / "contract_record_a.csv"
    conflict_b = root / "contract_record_b.csv"
    formula_workbook = root / "contract_formula.xlsx"

    _make_born_digital_pdf(born_digital)
    _make_scanned_pdf(scanned)
    _make_formula_workbook(formula_workbook)
    shutil.copyfile(born_digital, duplicate)
    corrupted.write_bytes(b"%PDF-1.7\nthis is intentionally truncated and invalid")
    version_one.write_text("Award amount: $250,000\nStatus: proposed\n", encoding="utf-8")
    version_two.write_text("Award amount: $410,000\nStatus: approved\n", encoding="utf-8")

    for path, amount in ((conflict_a, "250000"), (conflict_b, "410000")):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["contract_id", "vendor", "amount"])
            writer.writerow(["C-001", "Northstar Civic Systems", amount])

    manifest = {
        "born_digital_pdf": born_digital.name,
        "scanned_pdf": scanned.name,
        "exact_duplicate": duplicate.name,
        "corrupted_pdf": corrupted.name,
        "same_source_versions": [version_one.name, version_two.name],
        "conflicting_structured_records": [conflict_a.name, conflict_b.name],
        "formula_workbook": formula_workbook.name,
        "expected_properties": {
            "born_digital_has_native_text": True,
            "scanned_has_native_text": False,
            "duplicate_sha256_matches_born_digital": True,
            "corrupted_pdf_extraction_should_fail_without_losing_artifact": True,
            "version_values_differ": True,
            "structured_amounts_conflict": True,
            "xlsx_formula_preserved_not_evaluated": True
        }
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
