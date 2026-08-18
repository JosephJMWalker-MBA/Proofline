"""Summarize an R0 Proofline SQLite state without interpreting misconduct."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def scalar(connection: sqlite3.Connection, query: str, params=()):
    return connection.execute(query, params).fetchone()[0]


def rows(connection: sqlite3.Connection, query: str, params=()):
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def summarize(db_path: Path) -> dict:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
        }

        summary: dict = {
            "sources": scalar(connection, "SELECT COUNT(*) FROM sources"),
            "artifacts": scalar(connection, "SELECT COUNT(*) FROM artifacts"),
            "source_snapshots": scalar(connection, "SELECT COUNT(*) FROM source_snapshots"),
            "evidence_units": scalar(connection, "SELECT COUNT(*) FROM evidence_units"),
            "extractions": scalar(connection, "SELECT COUNT(*) FROM evidence_extractions"),
            "processing_events": scalar(connection, "SELECT COUNT(*) FROM processing_events"),
            "source_groups": rows(
                connection,
                """
                SELECT
                  CASE
                    WHEN source_name LIKE 'Board of Control%' THEN 'Board of Control'
                    WHEN source_name LIKE 'City Council%' THEN 'City Council'
                    WHEN source_name LIKE 'Discovery index:%' THEN 'Discovery index'
                    ELSE 'Other'
                  END AS source_group,
                  COUNT(*) AS count
                FROM sources
                GROUP BY source_group
                ORDER BY source_group
                """,
            ),
            "evidence_types": rows(
                connection,
                "SELECT unit_type, COUNT(*) AS count FROM evidence_units GROUP BY unit_type ORDER BY unit_type",
            ),
            "quality": rows(
                connection,
                """
                SELECT
                  ROUND(MIN(best_quality), 4) AS min_quality,
                  ROUND(AVG(best_quality), 4) AS avg_quality,
                  ROUND(MAX(best_quality), 4) AS max_quality,
                  SUM(CASE WHEN best_quality < 0.70 THEN 1 ELSE 0 END) AS below_070
                FROM (
                  SELECT eu.evidence_id,
                    COALESCE((
                      SELECT ee.quality_score
                      FROM evidence_extractions ee
                      WHERE ee.evidence_id = eu.evidence_id
                      ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                               ee.occurred_at DESC,
                               ee.rowid DESC
                      LIMIT 1
                    ), 0.0) AS best_quality
                  FROM evidence_units eu
                )
                """,
            )[0],
            "shared_artifacts": rows(
                connection,
                """
                SELECT ss.artifact_id, COUNT(DISTINCT ss.source_id) AS source_count
                FROM source_snapshots ss
                GROUP BY ss.artifact_id
                HAVING COUNT(DISTINCT ss.source_id) > 1
                ORDER BY source_count DESC, ss.artifact_id
                LIMIT 50
                """,
            ),
            "revision_listing_sources": scalar(
                connection,
                "SELECT COUNT(*) FROM sources WHERE source_name LIKE '%VERSIONS%'",
            ),
        }

        if "source_checks" in tables:
            summary["watch_states"] = rows(
                connection,
                "SELECT state, COUNT(*) AS count FROM source_checks GROUP BY state ORDER BY state",
            )

        if "evidence_facts" in tables:
            summary["structured_facts"] = rows(
                connection,
                "SELECT fact_type, COUNT(*) AS count FROM evidence_facts GROUP BY fact_type ORDER BY fact_type",
            )
            summary["largest_money_facts"] = rows(
                connection,
                """
                SELECT ef.numeric_value, ef.raw_text, ef.evidence_id, ef.artifact_id, ef.locator,
                       s.source_uri, s.source_name
                FROM evidence_facts ef
                LEFT JOIN source_snapshots ss ON ss.artifact_id = ef.artifact_id
                LEFT JOIN sources s ON s.source_id = ss.source_id
                WHERE ef.fact_type = 'money'
                ORDER BY ef.numeric_value DESC, ef.evidence_id
                LIMIT 25
                """,
            )

        if "search_index_builds" in tables:
            summary["search_build"] = rows(
                connection,
                "SELECT * FROM search_index_builds ORDER BY built_at DESC, rowid DESC LIMIT 1",
            )
        if "structured_index_builds" in tables:
            summary["structured_build"] = rows(
                connection,
                "SELECT * FROM structured_index_builds ORDER BY built_at DESC, rowid DESC LIMIT 1",
            )

        return summary
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db")
    args = parser.parse_args()
    print(json.dumps(summarize(Path(args.db)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
