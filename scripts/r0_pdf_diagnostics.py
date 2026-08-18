"""Inspect low-quality PDF artifacts without interpreting their substantive content."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pymupdf


def _count(iterator) -> int:
    if iterator is None:
        return 0
    try:
        return sum(1 for _ in iterator)
    except Exception:
        return -1


def _document_embedded_names(document) -> list[str]:
    method = getattr(document, "embfile_names", None)
    if method is None:
        return []
    try:
        return list(method())
    except Exception:
        return []


def diagnose(state_dir: Path, *, threshold: float = 0.70) -> list[dict]:
    db_path = state_dir / "proofline.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT
                s.source_name,
                s.source_uri,
                a.artifact_id,
                a.byte_size,
                a.stored_path,
                COALESCE((
                    SELECT ee.quality_score
                    FROM evidence_units eu2
                    JOIN evidence_extractions ee ON ee.evidence_id = eu2.evidence_id
                    WHERE eu2.artifact_id = a.artifact_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                             ee.occurred_at DESC,
                             ee.rowid DESC
                    LIMIT 1
                ), 0.0) AS best_quality
            FROM sources s
            JOIN source_snapshots ss ON ss.source_id = s.source_id
            JOIN artifacts a ON a.artifact_id = ss.artifact_id
            WHERE a.media_type = 'application/pdf'
              AND COALESCE((
                    SELECT MAX(ee2.quality_score)
                    FROM evidence_units eu3
                    JOIN evidence_extractions ee2 ON ee2.evidence_id = eu3.evidence_id
                    WHERE eu3.artifact_id = a.artifact_id
                  ), 0.0) < ?
            ORDER BY s.source_name, s.source_uri
            """,
            (threshold,),
        ).fetchall()
    finally:
        connection.close()

    diagnostics: list[dict] = []
    for row in rows:
        path = state_dir / row["stored_path"]
        raw = path.read_bytes()
        item = {
            "source_name": row["source_name"],
            "source_uri": row["source_uri"],
            "artifact_id": row["artifact_id"],
            "byte_size": row["byte_size"],
            "best_quality": row["best_quality"],
            "pdf_markers": {
                "embedded_files_token": b"/EmbeddedFiles" in raw,
                "filespec_token": b"/Filespec" in raw or b"/FileSpec" in raw,
                "uri_token": b"/URI" in raw,
                "launch_token": b"/Launch" in raw,
            },
        }
        try:
            with pymupdf.open(path) as document:
                item["page_count"] = len(document)
                item["xref_length"] = document.xref_length()
                item["embedded_file_names"] = _document_embedded_names(document)
                item["metadata"] = {
                    key: value
                    for key, value in (document.metadata or {}).items()
                    if value
                }
                pages: list[dict] = []
                for page_number, page in enumerate(document, start=1):
                    text = page.get_text("text") or ""
                    pages.append(
                        {
                            "page_number": page_number,
                            "width": round(page.rect.width, 2),
                            "height": round(page.rect.height, 2),
                            "text_length": len(text),
                            "image_count": len(page.get_images(full=True)),
                            "links": page.get_links(),
                            "annotation_count": _count(page.annots()),
                            "widget_count": _count(page.widgets()),
                        }
                    )
                item["pages"] = pages
        except Exception as exc:
            item["open_error"] = f"{type(exc).__name__}: {exc}"
        diagnostics.append(item)

    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state_dir")
    parser.add_argument("--threshold", type=float, default=0.70)
    args = parser.parse_args()
    payload = diagnose(Path(args.state_dir), threshold=args.threshold)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
