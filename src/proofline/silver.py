"""Shared Silver-layer quality predicates used before Gold promotion."""

from __future__ import annotations

from .storage import ProoflineStore


def artifact_has_substantive_preferred_text(store: ProoflineStore, artifact_id: str) -> bool:
    """Return whether any preferred extraction contains non-whitespace text.

    Text is checked with Python's Unicode-aware ``str.strip`` rather than SQLite ``TRIM``.
    SQLite's default TRIM removes ordinary spaces only, so tab/newline-only extraction can
    otherwise be misclassified as substantive evidence.
    """
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT best.extracted_text
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
            WHERE eu.artifact_id = ?
            """,
            (artifact_id,),
        ).fetchall()
    return any(str(row["extracted_text"] or "").strip() for row in rows)
