"""Append-only persistence for corpus watcher checks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .storage import ProoflineStore

_WATCH_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS source_checks (
    check_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    checked_at TEXT NOT NULL,
    state TEXT NOT NULL,
    artifact_id TEXT REFERENCES artifacts(artifact_id),
    previous_artifact_id TEXT REFERENCES artifacts(artifact_id),
    http_status INTEGER,
    content_type TEXT,
    etag TEXT,
    last_modified TEXT,
    error TEXT,
    attempts INTEGER NOT NULL CHECK(attempts >= 1),
    manifest_name TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_checks_source_time
ON source_checks(source_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_source_checks_run
ON source_checks(run_id);
CREATE TRIGGER IF NOT EXISTS source_checks_no_update
BEFORE UPDATE ON source_checks BEGIN
    SELECT RAISE(ABORT, 'source checks are append-only');
END;
CREATE TRIGGER IF NOT EXISTS source_checks_no_delete
BEFORE DELETE ON source_checks BEGIN
    SELECT RAISE(ABORT, 'source checks are append-only');
END;
"""


class WatcherStore:
    def __init__(self, db_path: str | Path):
        self.base = ProoflineStore(db_path)
        with self.base.connection() as connection:
            connection.executescript(_WATCH_SCHEMA)

    def add_source_check(
        self,
        *,
        check_id: str,
        run_id: str,
        source_id: str,
        checked_at: datetime,
        state: str,
        artifact_id: str | None,
        previous_artifact_id: str | None,
        http_status: int | None,
        content_type: str | None,
        etag: str | None,
        last_modified: str | None,
        error: str | None,
        attempts: int,
        manifest_name: str | None,
    ) -> None:
        with self.base.connection() as connection:
            connection.execute(
                """
                INSERT INTO source_checks(
                    check_id, run_id, source_id, checked_at, state, artifact_id,
                    previous_artifact_id, http_status, content_type, etag,
                    last_modified, error, attempts, manifest_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    run_id,
                    source_id,
                    checked_at.isoformat(),
                    state,
                    artifact_id,
                    previous_artifact_id,
                    http_status,
                    content_type,
                    etag,
                    last_modified,
                    error,
                    attempts,
                    manifest_name,
                ),
            )

    def recent_changes(
        self, *, limit: int = 100, include_unchanged: bool = False, run_id: str | None = None
    ) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be positive")
        clauses: list[str] = []
        params: list[object] = []
        if not include_unchanged:
            clauses.append("sc.state != 'unchanged'")
        if run_id is not None:
            clauses.append("sc.run_id = ?")
            params.append(run_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.base.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT sc.*, s.source_uri, s.source_name
                FROM source_checks sc
                JOIN sources s ON s.source_id = sc.source_id
                {where}
                ORDER BY sc.checked_at DESC, sc.rowid DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def count_checks(self) -> int:
        with self.base.connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM source_checks").fetchone()[0])
