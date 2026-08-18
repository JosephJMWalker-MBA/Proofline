"""SQLite persistence for Proofline's immutable evidence graph."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .hashing import source_id_from_uri
from .models import Artifact, EvidenceReference, EvidenceUnit, Lead, Observation, ProcessingEvent

_SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL UNIQUE,
    source_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256) = 64),
    byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
    media_type TEXT,
    stored_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    retrieved_at TEXT NOT NULL,
    native_identifier TEXT,
    supersedes_artifact_id TEXT REFERENCES artifacts(artifact_id),
    UNIQUE(source_id, artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_source_snapshots_source
ON source_snapshots(source_id, retrieved_at);

CREATE TABLE IF NOT EXISTS evidence_units (
    evidence_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    unit_type TEXT NOT NULL,
    locator TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    UNIQUE(artifact_id, unit_type, locator)
);

CREATE TABLE IF NOT EXISTS evidence_extractions (
    extraction_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
    occurred_at TEXT NOT NULL,
    method TEXT NOT NULL,
    extracted_text TEXT,
    quality_score REAL CHECK(quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 1.0)),
    software_version TEXT,
    model_version TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_evidence_extractions_evidence
ON evidence_extractions(evidence_id, occurred_at);

CREATE TABLE IF NOT EXISTS processing_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    stage TEXT NOT NULL,
    method TEXT NOT NULL,
    artifact_id TEXT REFERENCES artifacts(artifact_id),
    evidence_id TEXT REFERENCES evidence_units(evidence_id),
    software_version TEXT,
    model_version TEXT,
    quality_score REAL CHECK(quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 1.0)),
    warnings_json TEXT NOT NULL DEFAULT '[]',
    CHECK(artifact_id IS NOT NULL OR evidence_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    observation_type TEXT NOT NULL,
    explanation TEXT NOT NULL,
    method TEXT NOT NULL,
    score REAL CHECK(score IS NULL OR (score >= 0.0 AND score <= 1.0)),
    uncertainty TEXT,
    limitations_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation_evidence (
    observation_id TEXT NOT NULL REFERENCES observations(observation_id),
    evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    locator TEXT NOT NULL,
    excerpt TEXT,
    PRIMARY KEY(observation_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    why_surfaced TEXT NOT NULL,
    questions_json TEXT NOT NULL DEFAULT '[]',
    benign_explanations_json TEXT NOT NULL DEFAULT '[]',
    novelty REAL,
    anomaly_strength REAL,
    corroboration REAL,
    source_quality REAL,
    uncertainty REAL,
    status TEXT NOT NULL,
    reviewer_notes_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lead_observations (
    lead_id TEXT NOT NULL REFERENCES leads(lead_id),
    observation_id TEXT NOT NULL REFERENCES observations(observation_id),
    PRIMARY KEY(lead_id, observation_id)
);

CREATE TABLE IF NOT EXISTS lead_evidence (
    lead_id TEXT NOT NULL REFERENCES leads(lead_id),
    evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    locator TEXT NOT NULL,
    excerpt TEXT,
    PRIMARY KEY(lead_id, evidence_id)
);

CREATE TRIGGER IF NOT EXISTS artifacts_no_update
BEFORE UPDATE ON artifacts BEGIN
    SELECT RAISE(ABORT, 'artifacts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS artifacts_no_delete
BEFORE DELETE ON artifacts BEGIN
    SELECT RAISE(ABORT, 'artifacts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_update
BEFORE UPDATE ON source_snapshots BEGIN
    SELECT RAISE(ABORT, 'source snapshots are immutable');
END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_delete
BEFORE DELETE ON source_snapshots BEGIN
    SELECT RAISE(ABORT, 'source snapshots are immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_units_no_update
BEFORE UPDATE ON evidence_units BEGIN
    SELECT RAISE(ABORT, 'evidence units are immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_units_no_delete
BEFORE DELETE ON evidence_units BEGIN
    SELECT RAISE(ABORT, 'evidence units are immutable');
END;
CREATE TRIGGER IF NOT EXISTS extractions_no_update
BEFORE UPDATE ON evidence_extractions BEGIN
    SELECT RAISE(ABORT, 'evidence extractions are append-only');
END;
CREATE TRIGGER IF NOT EXISTS extractions_no_delete
BEFORE DELETE ON evidence_extractions BEGIN
    SELECT RAISE(ABORT, 'evidence extractions are append-only');
END;
CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON processing_events BEGIN
    SELECT RAISE(ABORT, 'processing events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON processing_events BEGIN
    SELECT RAISE(ABORT, 'processing events are append-only');
END;
"""


class ProoflineStore:
    """Small SQLite repository with explicit provenance invariants."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(_SCHEMA)

    def add_source(self, source_uri: str, source_name: str | None = None) -> str:
        source_id = source_id_from_uri(source_uri)
        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sources(source_id, source_uri, source_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source_id, source_uri, source_name, datetime.now(UTC).isoformat()),
            )
        return source_id

    def add_artifact(self, artifact: Artifact, stored_path: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO artifacts(
                    artifact_id, sha256, byte_size, media_type, stored_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.sha256,
                    artifact.byte_size,
                    artifact.media_type,
                    stored_path,
                    datetime.now(UTC).isoformat(),
                ),
            )
            return cursor.rowcount == 1

    def latest_artifact_for_source(self, source_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT artifact_id FROM source_snapshots
                WHERE source_id = ?
                ORDER BY retrieved_at DESC, rowid DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return str(row["artifact_id"]) if row else None

    def add_source_snapshot(
        self,
        *,
        snapshot_id: str,
        source_id: str,
        artifact_id: str,
        retrieved_at: datetime,
        native_identifier: str | None,
        supersedes_artifact_id: str | None,
    ) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO source_snapshots(
                    snapshot_id, source_id, artifact_id, retrieved_at,
                    native_identifier, supersedes_artifact_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    source_id,
                    artifact_id,
                    retrieved_at.isoformat(),
                    native_identifier,
                    supersedes_artifact_id,
                ),
            )
            return cursor.rowcount == 1

    def add_evidence_unit(self, unit: EvidenceUnit) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO evidence_units(
                    evidence_id, artifact_id, unit_type, locator, char_start, char_end
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    unit.evidence_id,
                    unit.artifact_id,
                    unit.unit_type.value,
                    unit.locator,
                    unit.char_start,
                    unit.char_end,
                ),
            )
            return cursor.rowcount == 1

    def add_evidence_extraction(
        self,
        *,
        extraction_id: str,
        evidence_id: str,
        occurred_at: datetime,
        method: str,
        extracted_text: str | None,
        quality_score: float | None,
        software_version: str | None = None,
        model_version: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO evidence_extractions(
                    extraction_id, evidence_id, occurred_at, method, extracted_text,
                    quality_score, software_version, model_version, warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    extraction_id,
                    evidence_id,
                    occurred_at.isoformat(),
                    method,
                    extracted_text,
                    quality_score,
                    software_version,
                    model_version,
                    json.dumps(list(warnings)),
                ),
            )
            return cursor.rowcount == 1

    def add_processing_event(self, event: ProcessingEvent) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO processing_events(
                    event_id, occurred_at, stage, method, artifact_id, evidence_id,
                    software_version, model_version, quality_score, warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.occurred_at.isoformat(),
                    event.stage,
                    event.method,
                    event.artifact_id,
                    event.evidence_id,
                    event.software_version,
                    event.model_version,
                    event.quality_score,
                    json.dumps(list(event.warnings)),
                ),
            )
            return cursor.rowcount == 1

    def _validate_ref(self, connection: sqlite3.Connection, ref: EvidenceReference) -> None:
        row = connection.execute(
            "SELECT artifact_id, locator FROM evidence_units WHERE evidence_id = ?",
            (ref.evidence_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown evidence reference: {ref.evidence_id}")
        if row["artifact_id"] != ref.artifact_id or row["locator"] != ref.locator:
            raise ValueError(f"evidence reference does not match stored evidence: {ref.evidence_id}")

    def add_observation(self, observation: Observation) -> bool:
        with self.connection() as connection:
            for ref in observation.evidence_refs:
                self._validate_ref(connection, ref)
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO observations(
                    observation_id, observation_type, explanation, method, score,
                    uncertainty, limitations_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.observation_id,
                    observation.observation_type,
                    observation.explanation,
                    observation.method,
                    observation.score,
                    observation.uncertainty,
                    json.dumps(list(observation.limitations)),
                    observation.status.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.executemany(
                """
                INSERT INTO observation_evidence(
                    observation_id, evidence_id, artifact_id, locator, excerpt
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        observation.observation_id,
                        ref.evidence_id,
                        ref.artifact_id,
                        ref.locator,
                        ref.excerpt,
                    )
                    for ref in observation.evidence_refs
                ],
            )
            return True

    def add_lead(self, lead: Lead) -> bool:
        with self.connection() as connection:
            for observation_id in lead.observation_ids:
                if connection.execute(
                    "SELECT 1 FROM observations WHERE observation_id = ?", (observation_id,)
                ).fetchone() is None:
                    raise ValueError(f"unknown observation: {observation_id}")
            for ref in lead.evidence_refs:
                self._validate_ref(connection, ref)
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO leads(
                    lead_id, title, why_surfaced, questions_json,
                    benign_explanations_json, novelty, anomaly_strength, corroboration,
                    source_quality, uncertainty, status, reviewer_notes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead.lead_id,
                    lead.title,
                    lead.why_surfaced,
                    json.dumps(list(lead.questions_worth_asking)),
                    json.dumps(list(lead.possible_benign_explanations)),
                    lead.novelty,
                    lead.anomaly_strength,
                    lead.corroboration,
                    lead.source_quality,
                    lead.uncertainty,
                    lead.status.value,
                    json.dumps(list(lead.reviewer_notes)),
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.executemany(
                "INSERT INTO lead_observations(lead_id, observation_id) VALUES (?, ?)",
                [(lead.lead_id, item) for item in lead.observation_ids],
            )
            connection.executemany(
                """
                INSERT INTO lead_evidence(lead_id, evidence_id, artifact_id, locator, excerpt)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(lead.lead_id, r.evidence_id, r.artifact_id, r.locator, r.excerpt) for r in lead.evidence_refs],
            )
            return True

    def status(self, *, review_threshold: float = 0.70) -> dict[str, int]:
        tables = {
            "sources": "sources",
            "artifacts": "artifacts",
            "source_snapshots": "source_snapshots",
            "evidence_units": "evidence_units",
            "extractions": "evidence_extractions",
            "processing_events": "processing_events",
            "observations": "observations",
            "leads": "leads",
        }
        with self.connection() as connection:
            result = {
                key: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for key, table in tables.items()
            }
            result["changed_sources"] = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT source_id FROM source_snapshots
                        GROUP BY source_id HAVING COUNT(DISTINCT artifact_id) > 1
                    )
                    """
                ).fetchone()[0]
            )
            result["needs_review"] = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM evidence_units eu
                    WHERE COALESCE((
                        SELECT quality_score FROM evidence_extractions ee
                        WHERE ee.evidence_id = eu.evidence_id
                        ORDER BY ee.occurred_at DESC, ee.rowid DESC LIMIT 1
                    ), 0.0) < ?
                    """,
                    (review_threshold,),
                ).fetchone()[0]
            )
        return result

    def trace_observation(self, observation_id: str) -> dict | None:
        with self.connection() as connection:
            obs = connection.execute(
                "SELECT * FROM observations WHERE observation_id = ?", (observation_id,)
            ).fetchone()
            if obs is None:
                return None
            refs = connection.execute(
                "SELECT * FROM observation_evidence WHERE observation_id = ? ORDER BY evidence_id",
                (observation_id,),
            ).fetchall()
            evidence = []
            for ref in refs:
                unit = connection.execute(
                    "SELECT * FROM evidence_units WHERE evidence_id = ?", (ref["evidence_id"],)
                ).fetchone()
                artifact = connection.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?", (ref["artifact_id"],)
                ).fetchone()
                extraction = connection.execute(
                    """
                    SELECT * FROM evidence_extractions WHERE evidence_id = ?
                    ORDER BY occurred_at DESC, rowid DESC LIMIT 1
                    """,
                    (ref["evidence_id"],),
                ).fetchone()
                sources = connection.execute(
                    """
                    SELECT s.source_id, s.source_uri, s.source_name, ss.snapshot_id,
                           ss.retrieved_at, ss.native_identifier, ss.supersedes_artifact_id
                    FROM source_snapshots ss
                    JOIN sources s ON s.source_id = ss.source_id
                    WHERE ss.artifact_id = ?
                    ORDER BY ss.retrieved_at
                    """,
                    (ref["artifact_id"],),
                ).fetchall()
                evidence.append(
                    {
                        "reference": dict(ref),
                        "unit": dict(unit) if unit else None,
                        "latest_extraction": dict(extraction) if extraction else None,
                        "artifact": dict(artifact) if artifact else None,
                        "sources": [dict(item) for item in sources],
                    }
                )
            return {
                "observation": dict(obs),
                "evidence": evidence,
            }
