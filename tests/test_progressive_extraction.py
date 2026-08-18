from __future__ import annotations

import json

import openpyxl

from proofline import (
    Ingestor,
    OcrPageResult,
    ProgressiveExtractor,
    ProoflineStore,
    extraction_attempts,
    preferred_extraction,
    review_queue,
)
from tests.fixture_corpus import build_fixture_corpus


class FakeOcrBackend:
    name = "fake_ocr"

    def __init__(self, version: str = "fake-1") -> None:
        self.version = version

    def extract_page(self, path, page_number: int) -> OcrPageResult:
        return OcrPageResult(
            page_number=page_number,
            text="Scanned memorandum: emergency procurement review",
            method=self.name,
            quality_score=0.99,
            software_version=self.version,
            model_version="fixture-model",
        )


def test_ocr_escalation_preserves_evidence_identity_and_attempt_history(tmp_path) -> None:
    corpus = tmp_path / "corpus"
    manifest = build_fixture_corpus(corpus)
    state = tmp_path / "state"
    ingest = Ingestor(state).ingest(corpus / manifest["scanned_pdf"])
    store = ProoflineStore(state / "proofline.db")

    with store.connection() as connection:
        evidence_id = connection.execute(
            "SELECT evidence_id FROM evidence_units WHERE artifact_id = ?",
            (ingest.artifact_id,),
        ).fetchone()[0]

    before = extraction_attempts(store, evidence_id)
    assert len(before) == 1
    assert before[0]["method"] == "pymupdf_native_text"
    assert review_queue(state)[0].evidence_id == evidence_id

    result = ProgressiveExtractor(state).run_ocr(ingest.artifact_id, FakeOcrBackend())
    assert result.attempted == 1
    assert result.added == 1
    assert result.failed == 0

    after = extraction_attempts(store, evidence_id)
    assert len(after) == 2
    assert preferred_extraction(store, evidence_id)["method"] == "fake_ocr"
    assert review_queue(state) == []

    # A second normal pass should not spend OCR work on evidence that already
    # clears the configured quality threshold.
    skipped = ProgressiveExtractor(state).run_ocr(ingest.artifact_id, FakeOcrBackend())
    assert skipped.attempted == 0
    assert skipped.skipped == 1
    assert len(extraction_attempts(store, evidence_id)) == 2

    # A producer upgrade is a distinct append-only attempt even if it emits
    # identical text. Evidence identity does not change.
    upgraded = ProgressiveExtractor(state).run_ocr(
        ingest.artifact_id, FakeOcrBackend("fake-2"), force=True
    )
    assert upgraded.added == 1
    attempts = extraction_attempts(store, evidence_id)
    assert len(attempts) == 3
    assert {item["software_version"] for item in attempts if item["method"] == "fake_ocr"} == {
        "fake-1",
        "fake-2",
    }
    with store.connection() as connection:
        persisted_id = connection.execute(
            "SELECT evidence_id FROM evidence_units WHERE artifact_id = ?",
            (ingest.artifact_id,),
        ).fetchone()[0]
    assert persisted_id == evidence_id


def test_csv_xlsx_and_json_create_citeable_native_evidence(tmp_path) -> None:
    state = tmp_path / "state"

    csv_path = tmp_path / "contracts.csv"
    csv_path.write_text(
        "contract_id,vendor,amount\nC-001,Northstar Civic Systems,250000\n",
        encoding="utf-8",
    )
    csv_result = Ingestor(state).ingest(csv_path)
    assert csv_result.evidence_units_seen == 2

    xlsx_path = tmp_path / "contracts.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Awards"
    sheet.append(["contract_id", "vendor", "calculation"])
    sheet.append(["C-002", "Lakeview Systems", "=125000*2"])
    workbook.save(xlsx_path)
    workbook.close()

    xlsx_result = Ingestor(state).ingest(xlsx_path)
    assert xlsx_result.evidence_units_seen == 2

    json_path = tmp_path / "record.json"
    json_path.write_text(json.dumps({"permit": "P-17", "status": "issued"}), encoding="utf-8")
    json_result = Ingestor(state).ingest(json_path)
    assert json_result.evidence_units_seen == 1

    store = ProoflineStore(state / "proofline.db")
    with store.connection() as connection:
        csv_rows = connection.execute(
            "SELECT locator FROM evidence_units WHERE artifact_id = ? ORDER BY locator",
            (csv_result.artifact_id,),
        ).fetchall()
        xlsx_rows = connection.execute(
            "SELECT evidence_id, locator FROM evidence_units WHERE artifact_id = ? ORDER BY locator",
            (xlsx_result.artifact_id,),
        ).fetchall()

    assert [row["locator"] for row in csv_rows] == ["sheet:CSV!A1:C1", "sheet:CSV!A2:C2"]
    assert [row["locator"] for row in xlsx_rows] == [
        "sheet:Awards!A1:C1",
        "sheet:Awards!A2:C2",
    ]
    formula_attempt = preferred_extraction(store, xlsx_rows[1]["evidence_id"])
    assert "=125000*2" in formula_attempt["extracted_text"]
    assert "not evaluated" in formula_attempt["warnings_json"]
