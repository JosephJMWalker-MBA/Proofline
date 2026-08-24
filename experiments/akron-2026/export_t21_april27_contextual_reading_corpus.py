#!/usr/bin/env python3
"""Export the frozen April 27 T21 supporting-document family for contextual audit.

This is a post-receipt reading-corpus stage. It does not select documents by
meaning. It re-proves the frozen 20-document publisher population, reacquires
the exact Bronze bytes, uses the already-established native/OCR quality path,
and emits preferred page text plus provenance for human journalistic audit.

The exporter assigns no event, hearing, outcome, detector, or lead authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from proofline.ocr import PyMuPDFTesseractBackend
from proofline.onbase_attachments import OnBaseAttachmentWatcher
from proofline.progressive import ProgressiveExtractor
from proofline.review import preferred_extraction
from proofline.storage import ProoflineStore

SCHEMA = "proofline-akron-t21-april27-contextual-reading-corpus/v1"
STAGE = "exact_family_pre_human_contextual_audit"
POPULATION_SCHEMA = "proofline-akron-t21-april27-contextual-reading-population/v1"
EXPECTED_POPULATION_SIGNATURE = "8238c57440a8d4257f697ef465a7a47b041c0fb2f5b77d01c244c8b23f71d72d"
EXPECTED_SELECTION_SIGNATURE = "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
EXPECTED_DOCUMENT_COUNT = 20
EXPECTED_PAGE_COUNT = 88
EXPECTED_OCR_ATTEMPTED = 41
EXPECTED_NATIVE_SKIPPED = 47


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _acquisition_module():
    path = Path(__file__).with_name("acquire_t21_april27_supporting_documents.py")
    spec = importlib.util.spec_from_file_location("t21_april27_acquisition", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load T21 acquisition module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def population_rows(population: dict) -> tuple[dict, ...]:
    if population.get("schema") != POPULATION_SCHEMA:
        raise ValueError("unexpected contextual reading population schema")
    if population.get("stage") != "post_ocr_receipt_pre_full_family_contextual_reading":
        raise ValueError("unexpected contextual reading population stage")
    rows = population.get("documents")
    if not isinstance(rows, list) or len(rows) != EXPECTED_DOCUMENT_COUNT:
        raise ValueError("contextual reading population must contain 20 documents")
    normalized = []
    for row in rows:
        normalized.append(
            {
                "artifact_sha256": row["artifact_sha256"],
                "byte_size": row["byte_size"],
                "item_id": row["item_id"],
                "link_text_sha256": row["link_text_sha256"],
                "meeting_id": row["meeting_id"],
                "native_low_quality_page_count": row["native_low_quality_page_count"],
                "native_nonblank_page_count": row["native_nonblank_page_count"],
                "page_count": row["page_count"],
                "page_metadata_signature_sha256": row["page_metadata_signature_sha256"],
                "publish_id": row["publish_id"],
                "source_uri_sha256": row["source_uri_sha256"],
            }
        )
    normalized.sort(key=lambda row: row["publish_id"])
    if _sha256_json(normalized) != EXPECTED_POPULATION_SIGNATURE:
        raise ValueError("contextual reading population signature drifted")
    if population.get("population_signature_sha256") != EXPECTED_POPULATION_SIGNATURE:
        raise ValueError("stored contextual reading population signature drifted")
    if sum(row["page_count"] for row in normalized) != EXPECTED_PAGE_COUNT:
        raise ValueError("contextual reading page count drifted")
    return tuple(normalized)


def verify_inputs(*, population: dict, selection: dict, relations: list[dict], attachment_manifest: dict):
    rows = population_rows(population)
    acquisition = _acquisition_module()
    if selection.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("supporting-document selection signature drifted")
    verified_relations = acquisition.verify_publisher_relations(selection, relations)
    manifest = acquisition.selected_manifest(selection, verified_relations, attachment_manifest)
    if len(manifest.resources) != EXPECTED_DOCUMENT_COUNT:
        raise ValueError("bounded manifest no longer contains 20 sources")
    return rows, verified_relations, manifest


def _page_units(store: ProoflineStore, artifact_id: str) -> list[dict]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT evidence_id, locator
            FROM evidence_units
            WHERE artifact_id = ? AND unit_type = 'page'
            ORDER BY CAST(SUBSTR(locator, 6) AS INTEGER), locator
            """,
            (artifact_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def export(
    *,
    state_dir: Path,
    population: dict,
    selection: dict,
    relations: list[dict],
    attachment_manifest: dict,
    threshold: float,
    language: str,
    dpi: int,
) -> dict:
    if threshold != 0.70:
        raise ValueError("contextual reading threshold is frozen at 0.70")
    rows, verified_relations, manifest = verify_inputs(
        population=population,
        selection=selection,
        relations=relations,
        attachment_manifest=attachment_manifest,
    )
    relation_by_publish = {int(row["publish_id"]): row for row in verified_relations}

    watcher = OnBaseAttachmentWatcher(state_dir)
    watch = watcher.run(manifest)
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"contextual reading source unavailable: {watch['counts']}")
    results = watch.get("results") or []
    if len(results) != EXPECTED_DOCUMENT_COUNT:
        raise RuntimeError("contextual reading reacquisition must return 20 results")
    result_by_source_hash = {
        _sha256_text(str(result.get("source_uri") or "")): result
        for result in results
    }

    store = ProoflineStore(state_dir / "proofline.db")
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    aggregate_ocr = Counter()
    aggregate_methods = Counter()
    documents = []
    preferred_nonblank = 0
    preferred_floor = 0
    acquisition = _acquisition_module()

    for row in rows:
        result = result_by_source_hash.get(row["source_uri_sha256"])
        if result is None or not result.get("artifact_id"):
            raise RuntimeError(f"missing reacquired artifact for publish_id={row['publish_id']}")
        artifact_id = str(result["artifact_id"])
        expected_artifact_id = f"artifact:{row['artifact_sha256']}"
        if artifact_id != expected_artifact_id:
            raise RuntimeError(
                f"Bronze drift for publish_id={row['publish_id']}: "
                f"expected={expected_artifact_id} actual={artifact_id}"
            )

        pre = acquisition._artifact_profile(store, artifact_id, threshold=threshold)
        for key in (
            "sha256",
            "byte_size",
            "page_count",
            "native_nonblank_page_count",
            "native_low_quality_page_count",
            "page_metadata_signature_sha256",
        ):
            expected_key = "artifact_sha256" if key == "sha256" else key
            if pre[key] != row[expected_key]:
                raise RuntimeError(
                    f"pre-reading Bronze/native profile drift for "
                    f"publish_id={row['publish_id']} field={key}"
                )

        ocr = ProgressiveExtractor(state_dir).run_ocr(
            artifact_id, backend, threshold=threshold, force=False
        ).to_dict()
        for key in ("candidates", "attempted", "added", "skipped", "failed"):
            aggregate_ocr[key] += int(ocr[key])

        pages = []
        for page_number, unit in enumerate(_page_units(store, artifact_id), start=1):
            preferred = preferred_extraction(store, unit["evidence_id"])
            if preferred is None:
                pages.append(
                    {
                        "page_number": page_number,
                        "evidence_id": unit["evidence_id"],
                        "locator": unit["locator"],
                        "preferred_extraction": None,
                    }
                )
                continue
            text = str(preferred.get("extracted_text") or "")
            quality = preferred.get("quality_score")
            method = str(preferred.get("method") or "")
            warnings = json.loads(preferred.get("warnings_json") or "[]")
            nonblank = bool(text.strip())
            meets_floor = quality is not None and float(quality) >= threshold
            preferred_nonblank += int(nonblank)
            preferred_floor += int(meets_floor)
            aggregate_methods[method] += 1
            pages.append(
                {
                    "page_number": page_number,
                    "evidence_id": unit["evidence_id"],
                    "locator": unit["locator"],
                    "preferred_extraction": {
                        "method": method,
                        "quality_score": quality,
                        "software_version": preferred.get("software_version"),
                        "model_version": preferred.get("model_version"),
                        "warnings": warnings,
                        "text_sha256": _sha256_text(text),
                        "character_count": len(text),
                        "line_count": len(text.splitlines()),
                        "nonblank": nonblank,
                        "meets_quality_floor": meets_floor,
                        "text": text,
                    },
                }
            )

        relation = relation_by_publish[row["publish_id"]]
        documents.append(
            {
                "publish_id": row["publish_id"],
                "meeting_id": row["meeting_id"],
                "item_id": row["item_id"],
                "source_uri_sha256": row["source_uri_sha256"],
                "link_text_sha256": row["link_text_sha256"],
                "publisher_link_text": relation.get("link_text"),
                "bronze": {
                    "artifact_id": artifact_id,
                    "sha256": row["artifact_sha256"],
                    "byte_size": row["byte_size"],
                    "page_count": row["page_count"],
                },
                "pre_reading_native": {
                    "nonblank_page_count": row["native_nonblank_page_count"],
                    "low_quality_page_count": row["native_low_quality_page_count"],
                    "page_metadata_signature_sha256": row["page_metadata_signature_sha256"],
                },
                "ocr": ocr,
                "pages": pages,
            }
        )

    if aggregate_ocr["candidates"] != EXPECTED_PAGE_COUNT:
        raise RuntimeError("reading corpus must present exactly 88 page units")
    if aggregate_ocr["attempted"] != EXPECTED_OCR_ATTEMPTED:
        raise RuntimeError("reading corpus OCR attempts drifted from frozen 41-page frontier")
    if aggregate_ocr["skipped"] != EXPECTED_NATIVE_SKIPPED:
        raise RuntimeError("reading corpus native skips drifted from expected 47 pages")

    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "population_signature_sha256": EXPECTED_POPULATION_SIGNATURE,
        "selection_signature_sha256": EXPECTED_SELECTION_SIGNATURE,
        "reacquisition": {
            "requested_source_count": EXPECTED_DOCUMENT_COUNT,
            "watch_result_count": len(results),
            "watch_counts": watch.get("counts") or {},
            "exact_bronze_reproduction_required": True,
        },
        "ocr": dict(sorted(aggregate_ocr.items())),
        "preferred": {
            "page_count": sum(len(item["pages"]) for item in documents),
            "nonblank_page_count": preferred_nonblank,
            "quality_floor_page_count": preferred_floor,
            "method_counts": dict(sorted(aggregate_methods.items())),
        },
        "documents": documents,
        "authority_boundary": {
            "machine_contextual_interpretation_performed": False,
            "event_identity_assigned": False,
            "meeting_occurrence_asserted": False,
            "hearing_occurrence_asserted": False,
            "outcome_assigned": False,
            "source_relation_created": False,
            "source_family_modified": False,
            "detector_authorized": False,
            "lead_count": None,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--relations", type=Path, required=True)
    parser.add_argument("--attachment-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = export(
        state_dir=args.state_dir,
        population=_load(args.population),
        selection=_load(args.selection),
        relations=_load(args.relations),
        attachment_manifest=_load(args.attachment_manifest),
        threshold=args.threshold,
        language=args.language,
        dpi=args.dpi,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "document_count": len(result["documents"]),
                "page_count": result["preferred"]["page_count"],
                "ocr_attempted": result["ocr"]["attempted"],
                "ocr_skipped": result["ocr"]["skipped"],
                "preferred_nonblank_page_count": result["preferred"]["nonblank_page_count"],
                "preferred_quality_floor_page_count": result["preferred"]["quality_floor_page_count"],
                "machine_contextual_interpretation_performed": result["authority_boundary"]["machine_contextual_interpretation_performed"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
