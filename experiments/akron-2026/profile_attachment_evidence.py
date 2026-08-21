#!/usr/bin/env python3
"""Profile the bounded Akron OnBase attachment evidence layer.

This experiment deliberately measures extraction and structured facts before any
Akron-specific matter/financial-role policy is introduced. It may run OCR only on
pages whose preferred native extraction remains below the declared quality floor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.storage import ProoflineStore
from proofline.structured import StructuredIndex
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-attachment-evidence-profile/v1"
RELATION_TYPE = "supporting_document_of"


def _tesseract_version() -> str | None:
    try:
        completed = subprocess.run(
            ["tesseract", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    first = (completed.stdout or completed.stderr).splitlines()
    return first[0].strip() if first else None


def _artifact_metadata(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT artifact_id, sha256, media_type, byte_size, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"missing attachment artifact: {artifact_id}")
    return dict(row)


def _page_profile(store: ProoflineStore, artifact_id: str, *, threshold: float) -> dict:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT
                eu.evidence_id,
                eu.locator,
                best.method,
                best.extracted_text,
                best.quality_score,
                best.software_version,
                best.model_version
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
            WHERE eu.artifact_id = ? AND eu.unit_type = 'page'
            ORDER BY CAST(SUBSTR(eu.locator, 6) AS INTEGER), eu.evidence_id
            """,
            (artifact_id,),
        ).fetchall()

    pages = []
    for row in rows:
        text = row["extracted_text"] or ""
        quality = float(row["quality_score"] or 0.0)
        pages.append(
            {
                "evidence_id": row["evidence_id"],
                "locator": row["locator"],
                "method": row["method"],
                "quality_score": quality,
                "text_chars": len(text.strip()),
                "nonblank": bool(text.strip()),
                "meets_quality_floor": quality >= threshold,
                "software_version": row["software_version"],
                "model_version": row["model_version"],
            }
        )

    methods = Counter(page["method"] for page in pages)
    return {
        "page_count": len(pages),
        "nonblank_page_count": sum(page["nonblank"] for page in pages),
        "high_quality_page_count": sum(page["meets_quality_floor"] for page in pages),
        "low_quality_page_count": sum(not page["meets_quality_floor"] for page in pages),
        "total_text_chars": sum(page["text_chars"] for page in pages),
        "preferred_method_counts": dict(sorted(methods.items())),
        "pages": pages,
    }


def _facts_for_artifacts(
    store: ProoflineStore,
    *,
    build_id: str,
    artifact_ids: list[str],
    source_by_artifact: dict[str, str],
) -> dict:
    if not artifact_ids:
        return {"fact_count": 0, "fact_type_counts": {}, "money": [], "dates": []}
    placeholders = ",".join("?" for _ in artifact_ids)
    with store.connection() as connection:
        rows = connection.execute(
            f"""
            SELECT artifact_id, locator, fact_type, raw_text, normalized_text,
                   numeric_value, unit, char_start, char_end
            FROM evidence_facts
            WHERE build_id = ? AND artifact_id IN ({placeholders})
            ORDER BY artifact_id, locator, fact_type, char_start, normalized_text
            """,
            [build_id, *artifact_ids],
        ).fetchall()

    counts = Counter(row["fact_type"] for row in rows)
    money = []
    dates = []
    for row in rows:
        item = {
            "source_uri": source_by_artifact.get(row["artifact_id"]),
            "artifact_id": row["artifact_id"],
            "locator": row["locator"],
            "raw_text": row["raw_text"],
            "normalized_text": row["normalized_text"],
            "numeric_value": row["numeric_value"],
            "unit": row["unit"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
        }
        if row["fact_type"] == "money":
            money.append(item)
        elif row["fact_type"] == "date":
            dates.append(item)
    return {
        "fact_count": len(rows),
        "fact_type_counts": dict(sorted(counts.items())),
        "money": money,
        "dates": dates,
    }


def _filename(source_uri: str) -> str:
    return unquote(Path(urlsplit(source_uri).path).name)


def build_profile(
    state_dir: Path,
    *,
    threshold: float,
    run_ocr: bool,
    language: str,
    dpi: int,
    parser_version: str | None = None,
) -> dict:
    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type=RELATION_TYPE)
    if not relations:
        raise RuntimeError("no supporting_document_of relations found; sync attachments first")

    latest_relation_by_source = {}
    for relation in relations:
        latest_relation_by_source[relation.source_id] = relation

    attachments = []
    source_by_artifact: dict[str, str] = {}
    for source_id, relation in sorted(
        latest_relation_by_source.items(), key=lambda item: item[1].source_uri
    ):
        artifact_id = watcher.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"attachment source has no successful artifact: {relation.source_uri}")
        metadata = _artifact_metadata(store, artifact_id)
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(
                f"attachment artifact is not PDF: {relation.source_uri} -> {metadata['media_type']}"
            )
        source_by_artifact[artifact_id] = relation.source_uri
        attachments.append(
            {
                "source_id": source_id,
                "source_uri": relation.source_uri,
                "filename": _filename(relation.source_uri),
                "parent_source_uri": relation.related_source_uri,
                "parent_evidence_artifact_id": relation.evidence_artifact_id,
                "link_text": relation.details.get("link_text"),
                "meeting_id": relation.details.get("meeting_id"),
                "item_id": relation.details.get("item_id"),
                "publish_id": relation.details.get("publish_id"),
                "artifact": metadata,
                "native": _page_profile(store, artifact_id, threshold=threshold),
            }
        )

    structured = StructuredIndex(state_dir)
    native_build = structured.rebuild(parser_version=parser_version)
    artifact_ids = [item["artifact"]["artifact_id"] for item in attachments]
    native_facts = _facts_for_artifacts(
        store,
        build_id=native_build.build_id,
        artifact_ids=artifact_ids,
        source_by_artifact=source_by_artifact,
    )

    ocr_results: dict[str, dict] = {}
    tesseract_version = _tesseract_version()
    if run_ocr:
        if tesseract_version is None:
            raise RuntimeError("Tesseract is unavailable; cannot run the requested OCR profile")
        extractor = ProgressiveExtractor(state_dir)
        backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
        for item in attachments:
            if item["native"]["low_quality_page_count"] == 0:
                continue
            artifact_id = item["artifact"]["artifact_id"]
            result = extractor.run_ocr(
                artifact_id,
                backend,
                threshold=threshold,
                force=False,
            )
            ocr_results[artifact_id] = result.to_dict()

    post_build = structured.rebuild(parser_version=parser_version)
    post_facts = _facts_for_artifacts(
        store,
        build_id=post_build.build_id,
        artifact_ids=artifact_ids,
        source_by_artifact=source_by_artifact,
    )

    for item in attachments:
        artifact_id = item["artifact"]["artifact_id"]
        item["ocr"] = ocr_results.get(artifact_id)
        item["post_ocr"] = _page_profile(store, artifact_id, threshold=threshold)
        item["native_money_fact_count"] = sum(
            fact["artifact_id"] == artifact_id for fact in native_facts["money"]
        )
        item["post_ocr_money_fact_count"] = sum(
            fact["artifact_id"] == artifact_id for fact in post_facts["money"]
        )

    native_page_count = sum(item["native"]["page_count"] for item in attachments)
    native_low = sum(item["native"]["low_quality_page_count"] for item in attachments)
    native_nonblank = sum(item["native"]["nonblank_page_count"] for item in attachments)
    post_low = sum(item["post_ocr"]["low_quality_page_count"] for item in attachments)
    post_nonblank = sum(item["post_ocr"]["nonblank_page_count"] for item in attachments)
    method_counts = Counter()
    for item in attachments:
        method_counts.update(item["post_ocr"]["preferred_method_counts"])

    ocr_attempted = sum(result["attempted"] for result in ocr_results.values())
    ocr_added = sum(result["added"] for result in ocr_results.values())
    ocr_failed = sum(result["failed"] for result in ocr_results.values())
    ocr_failures = [failure for result in ocr_results.values() for failure in result["failures"]]

    return {
        "schema": SCHEMA,
        "quality_threshold": threshold,
        "sample": {
            "attachment_count": len(attachments),
            "relation_count": len(relations),
            "selection_note": (
                "This profiles only attachment sources already synced into the bounded T7 production state; "
                "it is not a claim about all 2,327 discovered Akron attachments."
            ),
        },
        "native": {
            "page_count": native_page_count,
            "nonblank_page_count": native_nonblank,
            "low_quality_page_count": native_low,
            "documents_needing_ocr": sum(
                item["native"]["low_quality_page_count"] > 0 for item in attachments
            ),
            "structured_build": native_build.to_dict(),
            "facts": native_facts,
        },
        "ocr": {
            "requested": run_ocr,
            "backend": "pymupdf_tesseract_ocr" if run_ocr else None,
            "language": language if run_ocr else None,
            "dpi": dpi if run_ocr else None,
            "tesseract_version": tesseract_version,
            "documents_attempted": len(ocr_results),
            "pages_attempted": ocr_attempted,
            "extractions_added": ocr_added,
            "failed": ocr_failed,
            "failures": ocr_failures,
        },
        "post_ocr": {
            "page_count": native_page_count,
            "nonblank_page_count": post_nonblank,
            "low_quality_page_count": post_low,
            "preferred_method_counts": dict(sorted(method_counts.items())),
            "structured_build": post_build.to_dict(),
            "facts": post_facts,
            "money_facts_added_by_preferred_ocr": max(
                0, len(post_facts["money"]) - len(native_facts["money"])
            ),
        },
        "attachments": attachments,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--parser-version")
    args = parser.parse_args()
    if not 0.0 <= args.threshold <= 1.0:
        raise SystemExit("--threshold must be between 0 and 1")
    if args.dpi < 72:
        raise SystemExit("--dpi must be at least 72")

    profile = build_profile(
        Path(args.state_dir),
        threshold=args.threshold,
        run_ocr=args.ocr,
        language=args.language,
        dpi=args.dpi,
        parser_version=args.parser_version,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
