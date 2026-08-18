from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import fitz
import pytest

from proofline import EvidenceReference, Observation, ProoflineStore
from proofline.cli import main
from proofline.ingest import Ingestor


def _make_pdf(path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_ingest_preserves_pdf_and_creates_page_evidence(tmp_path) -> None:
    pdf = tmp_path / "record.pdf"
    _make_pdf(pdf, "Public contract amount: $250,000")
    state = tmp_path / "state"

    result = Ingestor(state).ingest(pdf, source_uri="https://example.gov/record.pdf")

    assert result.new_artifact is True
    assert result.new_snapshot is True
    assert result.evidence_units_seen == 1
    assert result.new_extractions == 1
    assert (state / result.stored_path).read_bytes() == pdf.read_bytes()

    status = ProoflineStore(state / "proofline.db").status()
    assert status["artifacts"] == 1
    assert status["evidence_units"] == 1
    assert status["needs_review"] == 0


def test_same_source_new_bytes_creates_version_not_overwrite(tmp_path) -> None:
    record = tmp_path / "record.txt"
    state = tmp_path / "state"
    source_uri = "https://example.gov/record.txt"
    t0 = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

    record.write_text("version one", encoding="utf-8")
    first = Ingestor(state).ingest(record, source_uri=source_uri, retrieved_at=t0)
    record.write_text("version two", encoding="utf-8")
    second = Ingestor(state).ingest(
        record, source_uri=source_uri, retrieved_at=t0 + timedelta(minutes=1)
    )

    assert first.artifact_id != second.artifact_id
    assert second.supersedes_artifact_id == first.artifact_id
    status = ProoflineStore(state / "proofline.db").status()
    assert status["artifacts"] == 2
    assert status["changed_sources"] == 1
    assert (state / first.stored_path).read_text(encoding="utf-8") == "version one"
    assert (state / second.stored_path).read_text(encoding="utf-8") == "version two"


def test_processing_events_are_append_only(tmp_path) -> None:
    record = tmp_path / "record.txt"
    record.write_text("public record", encoding="utf-8")
    state = tmp_path / "state"
    Ingestor(state).ingest(record)

    connection = sqlite3.connect(state / "proofline.db")
    try:
        event_id = connection.execute("SELECT event_id FROM processing_events LIMIT 1").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM processing_events WHERE event_id = ?", (event_id,))
    finally:
        connection.close()


def test_observation_trace_reaches_source_uri(tmp_path) -> None:
    record = tmp_path / "record.txt"
    record.write_text("Contract amount: $250,000", encoding="utf-8")
    state = tmp_path / "state"
    result = Ingestor(state).ingest(record, source_uri="https://example.gov/contracts/1")
    store = ProoflineStore(state / "proofline.db")

    with store.connection() as connection:
        row = connection.execute(
            "SELECT evidence_id, locator FROM evidence_units WHERE artifact_id = ?",
            (result.artifact_id,),
        ).fetchone()

    ref = EvidenceReference(
        evidence_id=row["evidence_id"],
        artifact_id=result.artifact_id,
        locator=row["locator"],
        excerpt="Contract amount: $250,000",
    )
    observation = Observation(
        observation_id="obs:test-trace",
        observation_type="structured_value",
        explanation="A contract amount was extracted from the source record.",
        evidence_refs=(ref,),
        method="test_detector",
    )
    assert store.add_observation(observation) is True

    trace = store.trace_observation(observation.observation_id)
    assert trace is not None
    assert trace["evidence"][0]["artifact"]["sha256"] == result.sha256
    assert trace["evidence"][0]["sources"][0]["source_uri"] == "https://example.gov/contracts/1"


def test_cli_ingest_and_status(tmp_path, capsys) -> None:
    record = tmp_path / "record.txt"
    record.write_text("hello public record", encoding="utf-8")
    state = tmp_path / "state"

    assert main(["--state-dir", str(state), "ingest", str(record)]) == 0
    ingest_payload = json.loads(capsys.readouterr().out)
    assert ingest_payload["new_artifact"] is True

    assert main(["--state-dir", str(state), "status"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["artifacts"] == 1
    assert status_payload["evidence_units"] == 1
