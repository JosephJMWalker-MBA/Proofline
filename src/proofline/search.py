"""Disposable lexical search index over preferred Proofline evidence."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .storage import ProoflineStore

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_TOKENIZER = "unicode61 remove_diacritics 2"

_SEARCH_SCHEMA = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
    build_id UNINDEXED,
    evidence_id UNINDEXED,
    artifact_id UNINDEXED,
    locator UNINDEXED,
    content,
    method UNINDEXED,
    quality_score UNINDEXED,
    tokenize='{_TOKENIZER}'
);

CREATE TABLE IF NOT EXISTS search_index_builds (
    build_id TEXT PRIMARY KEY,
    built_at TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    tokenizer TEXT NOT NULL,
    query_mode TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    build_id: str
    built_at: str
    evidence_count: int
    tokenizer: str
    query_mode: str = "all_terms"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SearchHit:
    build_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    snippet: str
    bm25: float
    method: str | None
    quality_score: float | None
    sources: tuple[dict, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = list(self.sources)
        return data


def normalize_lexical_query(query: str) -> str:
    """Convert user text to a deterministic FTS5 all-terms query."""
    tokens = _TOKEN_RE.findall(query.casefold())
    if not tokens:
        raise ValueError("query contains no searchable terms")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


class SearchIndex:
    """Rebuildable FTS5 index. Evidence tables remain the system of record."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self._initialize()

    def _initialize(self) -> None:
        try:
            with self.store.connection() as connection:
                connection.executescript(_SEARCH_SCHEMA)
        except sqlite3.OperationalError as exc:
            if "fts5" in str(exc).lower():
                raise RuntimeError("this SQLite build does not include FTS5 support") from exc
            raise

    def rebuild(self) -> IndexBuildResult:
        build_id = f"index:{uuid.uuid4()}"
        built_at = datetime.now(UTC).isoformat()
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    eu.evidence_id,
                    eu.artifact_id,
                    eu.locator,
                    best.extracted_text,
                    best.method,
                    best.quality_score
                FROM evidence_units eu
                JOIN evidence_extractions best
                  ON best.extraction_id = (
                    SELECT ee.extraction_id
                    FROM evidence_extractions ee
                    WHERE ee.evidence_id = eu.evidence_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                             ee.occurred_at DESC,
                             ee.rowid DESC
                    LIMIT 1
                  )
                WHERE best.extracted_text IS NOT NULL
                  AND TRIM(best.extracted_text) != ''
                ORDER BY eu.evidence_id
                """
            ).fetchall()

            connection.execute("DELETE FROM evidence_fts")
            connection.executemany(
                """
                INSERT INTO evidence_fts(
                    build_id, evidence_id, artifact_id, locator,
                    content, method, quality_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        build_id,
                        row["evidence_id"],
                        row["artifact_id"],
                        row["locator"],
                        row["extracted_text"],
                        row["method"],
                        row["quality_score"],
                    )
                    for row in rows
                ],
            )
            connection.execute(
                """
                INSERT INTO search_index_builds(
                    build_id, built_at, evidence_count, tokenizer, query_mode
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (build_id, built_at, len(rows), _TOKENIZER, "all_terms"),
            )

        return IndexBuildResult(
            build_id=build_id,
            built_at=built_at,
            evidence_count=len(rows),
            tokenizer=_TOKENIZER,
        )

    def current_build(self) -> dict | None:
        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM search_index_builds
                ORDER BY built_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def _sources_for_artifact(self, artifact_id: str) -> tuple[dict, ...]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT s.source_id, s.source_uri, s.source_name, ss.native_identifier
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.artifact_id = ?
                ORDER BY s.source_uri
                """,
                (artifact_id,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def search(self, query: str, *, limit: int = 20) -> list[SearchHit]:
        if limit < 1:
            raise ValueError("limit must be positive")
        fts_query = normalize_lexical_query(query)
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    build_id,
                    evidence_id,
                    artifact_id,
                    locator,
                    snippet(evidence_fts, 4, '[', ']', ' … ', 24) AS snippet,
                    bm25(evidence_fts) AS score,
                    method,
                    quality_score
                FROM evidence_fts
                WHERE evidence_fts MATCH ?
                ORDER BY score ASC, evidence_id ASC
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()

        return [
            SearchHit(
                build_id=row["build_id"],
                evidence_id=row["evidence_id"],
                artifact_id=row["artifact_id"],
                locator=row["locator"],
                snippet=row["snippet"],
                bm25=float(row["score"]),
                method=row["method"],
                quality_score=(
                    float(row["quality_score"]) if row["quality_score"] is not None else None
                ),
                sources=self._sources_for_artifact(row["artifact_id"]),
            )
            for row in rows
        ]

    def lookup_native_identifier(self, native_identifier: str) -> list[SearchHit]:
        """Return indexed evidence tied to an exact publisher-native identifier."""
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    f.build_id,
                    f.evidence_id,
                    f.artifact_id,
                    f.locator,
                    substr(f.content, 1, 500) AS snippet,
                    f.method,
                    f.quality_score
                FROM source_snapshots ss
                JOIN evidence_fts f ON f.artifact_id = ss.artifact_id
                WHERE ss.native_identifier = ?
                ORDER BY f.evidence_id
                """,
                (native_identifier,),
            ).fetchall()

        return [
            SearchHit(
                build_id=row["build_id"],
                evidence_id=row["evidence_id"],
                artifact_id=row["artifact_id"],
                locator=row["locator"],
                snippet=row["snippet"],
                bm25=0.0,
                method=row["method"],
                quality_score=(
                    float(row["quality_score"]) if row["quality_score"] is not None else None
                ),
                sources=self._sources_for_artifact(row["artifact_id"]),
            )
            for row in rows
        ]
