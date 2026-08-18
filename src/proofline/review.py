"""Human-review queries for low-confidence evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import ProoflineStore


@dataclass(frozen=True, slots=True)
class ReviewItem:
    evidence_id: str
    artifact_id: str
    unit_type: str
    locator: str
    quality_score: float | None
    method: str | None
    extraction_id: str | None
    source_uri: str | None
    source_name: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def preferred_extraction(store: ProoflineStore, evidence_id: str) -> dict | None:
    """Return the highest-quality extraction, preferring newer attempts on ties."""
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM evidence_extractions
            WHERE evidence_id = ?
            ORDER BY COALESCE(quality_score, -1.0) DESC, occurred_at DESC, rowid DESC
            LIMIT 1
            """,
            (evidence_id,),
        ).fetchone()
    return dict(row) if row else None


def extraction_attempts(store: ProoflineStore, evidence_id: str) -> list[dict]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM evidence_extractions
            WHERE evidence_id = ?
            ORDER BY occurred_at ASC, rowid ASC
            """,
            (evidence_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def review_count(state_dir: str | Path = ".proofline", *, threshold: float = 0.70) -> int:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    store = ProoflineStore(Path(state_dir) / "proofline.db")
    with store.connection() as connection:
        return int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM evidence_units eu
                WHERE COALESCE((
                    SELECT ee.quality_score
                    FROM evidence_extractions ee
                    WHERE ee.evidence_id = eu.evidence_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                             ee.occurred_at DESC,
                             ee.rowid DESC
                    LIMIT 1
                ), 0.0) < ?
                """,
                (threshold,),
            ).fetchone()[0]
        )


def review_queue(
    state_dir: str | Path = ".proofline", *, threshold: float = 0.70, limit: int = 100
) -> list[ReviewItem]:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    if limit < 1:
        raise ValueError("limit must be positive")

    store = ProoflineStore(Path(state_dir) / "proofline.db")
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT
                eu.evidence_id,
                eu.artifact_id,
                eu.unit_type,
                eu.locator,
                best.quality_score,
                best.method,
                best.extraction_id,
                source.source_uri,
                source.source_name
            FROM evidence_units eu
            LEFT JOIN evidence_extractions best
              ON best.extraction_id = (
                SELECT ee.extraction_id
                FROM evidence_extractions ee
                WHERE ee.evidence_id = eu.evidence_id
                ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                         ee.occurred_at DESC,
                         ee.rowid DESC
                LIMIT 1
              )
            LEFT JOIN (
                SELECT ss.artifact_id, s.source_uri, s.source_name
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.rowid IN (
                    SELECT MAX(ss2.rowid)
                    FROM source_snapshots ss2
                    GROUP BY ss2.artifact_id
                )
            ) source ON source.artifact_id = eu.artifact_id
            WHERE COALESCE(best.quality_score, 0.0) < ?
            ORDER BY COALESCE(best.quality_score, 0.0) ASC, eu.artifact_id, eu.locator
            LIMIT ?
            """,
            (threshold, limit),
        ).fetchall()

    return [
        ReviewItem(
            evidence_id=row["evidence_id"],
            artifact_id=row["artifact_id"],
            unit_type=row["unit_type"],
            locator=row["locator"],
            quality_score=row["quality_score"],
            method=row["method"],
            extraction_id=row["extraction_id"],
            source_uri=row["source_uri"],
            source_name=row["source_name"],
        )
        for row in rows
    ]
