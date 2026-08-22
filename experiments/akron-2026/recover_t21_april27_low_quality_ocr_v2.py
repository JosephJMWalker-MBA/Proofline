#!/usr/bin/env python3
"""Recover raw Silver OCR from the corrected T21 April 27 receipt v2.

This is the post-correction successor to the failed first OCR attempt. It uses
only the corrected v2 receipt and v2 low-quality selection, verifies the full
publisher selection again, reacquires exactly four sources, requires exact
Bronze/native-profile reproduction, and then runs the existing bounded OCR
path with force=False. No contextual interpretation or outcome authority is
assigned here.
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
from proofline.watcher import ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-april27-low-quality-ocr/v2"
STAGE = "raw_low_quality_supporting_document_ocr_after_receipt_correction_before_contextual_reading"
RECEIPT_SCHEMA = "proofline-akron-t21-april27-supporting-document-acquisition-receipt/v2"
LOW_SELECTION_SCHEMA = "proofline-akron-t21-april27-low-quality-ocr-selection/v2"
FULL_SELECTION_SCHEMA = "proofline-akron-t21-april27-supporting-document-selection/v1"
EXPECTED_FULL_SELECTION_SIGNATURE = "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
EXPECTED_LOW_SELECTION_SIGNATURE = "cd86100e5a6ff2d54159ae0437db95f79bdcfed24a054c1ed330792f3c07c357"
EXPECTED_PUBLISH_IDS = [102589, 102590, 102593, 102597]
EXPECTED_ARTIFACT_COUNT = 4
EXPECTED_SOURCE_PAGE_COUNT = 48
EXPECTED_LOW_QUALITY_PAGE_COUNT = 41


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
        raise RuntimeError(f"unable to load frozen T21 acquisition evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def low_selection_rows(selection: dict) -> tuple[dict, ...]:
    if selection.get("schema") != LOW_SELECTION_SCHEMA:
        raise ValueError("unexpected corrected low-quality OCR selection schema")
    if selection.get("selection_method") != "artifact.native_low_quality_page_count > 0":
        raise ValueError("corrected low-quality selection method drifted")
    rows = selection.get("selected_artifacts")
    if not isinstance(rows, list) or len(rows) != EXPECTED_ARTIFACT_COUNT:
        raise ValueError("corrected low-quality selection must contain four artifacts")
    normalized = []
    for row in rows:
        normalized.append(
            {
                "publish_id": int(row["publish_id"]),
                "source_uri_sha256": str(row["source_uri_sha256"]),
                "artifact_sha256": str(row["artifact_sha256"]),
                "page_count": int(row["page_count"]),
                "native_low_quality_page_count": int(row["native_low_quality_page_count"]),
                "page_metadata_signature_sha256": str(row["page_metadata_signature_sha256"]),
            }
        )
    normalized.sort(key=lambda row: row["publish_id"])
    if [row["publish_id"] for row in normalized] != EXPECTED_PUBLISH_IDS:
        raise ValueError("corrected low-quality publish IDs drifted")
    if sum(row["page_count"] for row in normalized) != EXPECTED_SOURCE_PAGE_COUNT:
        raise ValueError("corrected source-page accounting drifted")
    if sum(row["native_low_quality_page_count"] for row in normalized) != EXPECTED_LOW_QUALITY_PAGE_COUNT:
        raise ValueError("corrected low-quality page accounting drifted")
    if _sha256_json(normalized) != EXPECTED_LOW_SELECTION_SIGNATURE:
        raise ValueError("corrected low-quality row signature drifted")
    if selection.get("selection_signature_sha256") != EXPECTED_LOW_SELECTION_SIGNATURE:
        raise ValueError("stored corrected low-quality selection signature drifted")
    return tuple(normalized)


def verify_frozen_inputs(*, low_selection: dict, receipt: dict, full_selection: dict) -> tuple[dict, ...]:
    rows = low_selection_rows(low_selection)
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("corrected receipt v2 is required")
    if receipt.get("correction", {}).get("ocr_performed_before_correction") is not False:
        raise ValueError("receipt correction chronology drifted")
    if receipt.get("correction", {}).get("canonical_measurement_changed") is not False:
        raise ValueError("canonical measurement must remain unchanged")
    if receipt.get("selection", {}).get("canonical_acquisition_identity_match_count") != 20:
        raise ValueError("corrected receipt must prove 20 identity matches")
    if receipt.get("selection", {}).get("canonical_acquisition_identity_mismatch_count") != 0:
        raise ValueError("corrected receipt reports identity mismatch")
    if full_selection.get("schema") != FULL_SELECTION_SCHEMA:
        raise ValueError("unexpected full publisher selection schema")
    if full_selection.get("selection_signature_sha256") != EXPECTED_FULL_SELECTION_SIGNATURE:
        raise ValueError("full publisher selection signature drifted")
    frontier = receipt.get("ocr_frontier") or {}
    if frontier.get("selection_signature_sha256") != EXPECTED_LOW_SELECTION_SIGNATURE:
        raise ValueError("corrected receipt OCR frontier signature drifted")
    if frontier.get("selected_artifacts") != list(rows):
        raise ValueError("corrected receipt and low-quality selection disagree")
    if receipt.get("authority_boundary", {}).get("supporting_document_content_interpreted") is not False:
        raise ValueError("corrected receipt must precede contextual reading")
    return rows


def bounded_manifest(*, low_selection: dict, full_selection: dict, relations: list[dict], attachment_manifest: dict) -> tuple[SourceManifest, dict[int, dict]]:
    rows = low_selection_rows(low_selection)
    acquisition = _acquisition_module()
    verified = acquisition.verify_publisher_relations(full_selection, relations)
    full_manifest = acquisition.selected_manifest(full_selection, verified, attachment_manifest)
    relation_by_publish = {int(relation["publish_id"]): relation for relation in verified}
    resource_by_uri = {resource.source_uri: resource for resource in full_manifest.resources}
    resources = []
    selected_relations = {}
    for row in rows:
        relation = relation_by_publish.get(row["publish_id"])
        if relation is None:
            raise ValueError(f"missing publisher relation for publish_id={row['publish_id']}")
        source_uri = str(relation.get("source_uri") or "")
        if _sha256_text(source_uri) != row["source_uri_sha256"]:
            raise ValueError(f"source URI hash drifted for publish_id={row['publish_id']}")
        resource = resource_by_uri.get(source_uri)
        if resource is None:
            raise ValueError(f"selected source missing from full bounded manifest: {row['publish_id']}")
        resources.append(
            ManifestResource(
                source_uri=resource.source_uri,
                source_name=resource.source_name,
                native_identifier=resource.native_identifier,
                expected_media_type=resource.expected_media_type,
                sequence_group=resource.sequence_group,
                sequence_number=resource.sequence_number,
                fetch_strategy=resource.fetch_strategy,
            )
        )
        selected_relations[row["publish_id"]] = relation
    return SourceManifest(name="akron-t21-april27-corrected-low-quality-ocr", resources=tuple(resources)), selected_relations


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


def recover(*, state_dir: Path, low_selection: dict, receipt: dict, full_selection: dict, relations: list[dict], attachment_manifest: dict, threshold: float, language: str, dpi: int) -> dict:
    if threshold != 0.70:
        raise ValueError("T21 corrected OCR threshold is frozen at 0.70")
    rows = verify_frozen_inputs(low_selection=low_selection, receipt=receipt, full_selection=full_selection)
    manifest, selected_relations = bounded_manifest(low_selection=low_selection, full_selection=full_selection, relations=relations, attachment_manifest=attachment_manifest)

    watch = OnBaseAttachmentWatcher(state_dir).run(manifest)
    results = watch.get("results") or []
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"selected OCR source unavailable: {watch['counts']}")
    if len(results) != EXPECTED_ARTIFACT_COUNT:
        raise RuntimeError("corrected OCR acquisition must return exactly four results")

    result_by_hash = {_sha256_text(str(result.get("source_uri") or "")): result for result in results}
    store = ProoflineStore(state_dir / "proofline.db")
    acquisition = _acquisition_module()
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    artifacts = []
    aggregate_ocr = Counter()
    preferred_methods = Counter()
    preferred_ocr_page_count = 0
    preferred_nonblank_page_count = 0
    preferred_quality_floor_page_count = 0

    for row in rows:
        result = result_by_hash.get(row["source_uri_sha256"])
        if result is None or not result.get("artifact_id"):
            raise RuntimeError(f"missing reacquired artifact for publish_id={row['publish_id']}")
        artifact_id = str(result["artifact_id"])
        expected_artifact_id = f"artifact:{row['artifact_sha256']}"
        if artifact_id != expected_artifact_id:
            raise RuntimeError(f"Bronze artifact drifted for publish_id={row['publish_id']}")

        pre = acquisition._artifact_profile(store, artifact_id, threshold=threshold)
        if pre["sha256"] != row["artifact_sha256"]:
            raise RuntimeError(f"Bronze SHA drifted for publish_id={row['publish_id']}")
        if pre["page_count"] != row["page_count"]:
            raise RuntimeError(f"page count drifted for publish_id={row['publish_id']}")
        if pre["native_low_quality_page_count"] != row["native_low_quality_page_count"]:
            raise RuntimeError(f"native low-quality count drifted for publish_id={row['publish_id']}")
        if pre["page_metadata_signature_sha256"] != row["page_metadata_signature_sha256"]:
            raise RuntimeError(f"native page metadata drifted for publish_id={row['publish_id']}")

        ocr = ProgressiveExtractor(state_dir).run_ocr(artifact_id, backend, threshold=threshold, force=False).to_dict()
        for key in ("candidates", "attempted", "added", "skipped", "failed"):
            aggregate_ocr[key] += int(ocr[key])

        pages = []
        for page_number, unit in enumerate(_page_units(store, artifact_id), start=1):
            preferred = preferred_extraction(store, unit["evidence_id"])
            if preferred is None:
                pages.append({"page_number": page_number, "evidence_id": unit["evidence_id"], "locator": unit["locator"], "preferred_extraction": None})
                continue
            text = str(preferred.get("extracted_text") or "")
            quality = preferred.get("quality_score")
            method = str(preferred.get("method") or "")
            warnings = json.loads(preferred.get("warnings_json") or "[]")
            nonblank = bool(text.strip())
            meets_floor = quality is not None and float(quality) >= threshold
            is_ocr = method == backend.name
            preferred_methods[method] += 1
            preferred_nonblank_page_count += int(nonblank)
            preferred_quality_floor_page_count += int(meets_floor)
            preferred_ocr_page_count += int(is_ocr)
            pages.append(
                {
                    "page_number": page_number,
                    "evidence_id": unit["evidence_id"],
                    "locator": unit["locator"],
                    "preferred_extraction": {
                        "extraction_id": preferred["extraction_id"],
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

        artifacts.append(
            {
                "publish_id": row["publish_id"],
                "source_uri_sha256": row["source_uri_sha256"],
                "bronze": {
                    "artifact_id": artifact_id,
                    "sha256": row["artifact_sha256"],
                    "page_count": row["page_count"],
                    "pre_ocr_native_low_quality_page_count": row["native_low_quality_page_count"],
                    "pre_ocr_page_metadata_signature_sha256": row["page_metadata_signature_sha256"],
                },
                "publisher_relation": {
                    "meeting_id": selected_relations[row["publish_id"]].get("meeting_id"),
                    "item_id": selected_relations[row["publish_id"]].get("item_id"),
                    "publish_id": row["publish_id"],
                },
                "ocr": ocr,
                "silver_pages": pages,
            }
        )

    if aggregate_ocr["candidates"] != EXPECTED_LOW_QUALITY_PAGE_COUNT:
        raise RuntimeError("OCR candidate accounting no longer matches corrected 41-page frontier")

    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "correction_lineage": {
            "superseded_v1_receipt_not_used": True,
            "corrected_receipt_raw_acquisition_json_sha256": receipt["canonical_run"]["raw_acquisition_json_sha256"],
            "corrected_low_quality_selection_signature_sha256": EXPECTED_LOW_SELECTION_SIGNATURE,
        },
        "frozen_inputs": {
            "selected_artifact_count": EXPECTED_ARTIFACT_COUNT,
            "selected_source_page_count": EXPECTED_SOURCE_PAGE_COUNT,
            "pre_ocr_native_low_quality_page_count": EXPECTED_LOW_QUALITY_PAGE_COUNT,
            "quality_floor": threshold,
            "ocr_language": language,
            "ocr_dpi": dpi,
        },
        "reacquisition": {
            "requested_source_count": EXPECTED_ARTIFACT_COUNT,
            "watch_result_count": len(results),
            "watch_counts": watch.get("counts") or {},
            "exact_bronze_reproduction_required": True,
        },
        "ocr": dict(sorted(aggregate_ocr.items())),
        "silver": {
            "artifact_count": len(artifacts),
            "page_count": sum(len(item["silver_pages"]) for item in artifacts),
            "preferred_ocr_page_count": preferred_ocr_page_count,
            "preferred_nonblank_page_count": preferred_nonblank_page_count,
            "preferred_quality_floor_page_count": preferred_quality_floor_page_count,
            "preferred_method_counts": dict(sorted(preferred_methods.items())),
            "artifacts": artifacts,
        },
        "authority_boundary": {
            "supporting_document_content_interpreted": False,
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
    parser.add_argument("--low-selection", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--full-selection", type=Path, required=True)
    parser.add_argument("--relations", type=Path, required=True)
    parser.add_argument("--attachment-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = recover(
        state_dir=args.state_dir,
        low_selection=_load(args.low_selection),
        receipt=_load(args.receipt),
        full_selection=_load(args.full_selection),
        relations=_load(args.relations),
        attachment_manifest=_load(args.attachment_manifest),
        threshold=args.threshold,
        language=args.language,
        dpi=args.dpi,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "selected_artifact_count": result["silver"]["artifact_count"],
        "silver_page_count": result["silver"]["page_count"],
        "ocr_candidates": result["ocr"]["candidates"],
        "ocr_attempted": result["ocr"]["attempted"],
        "ocr_added": result["ocr"]["added"],
        "ocr_failed": result["ocr"]["failed"],
        "supporting_document_content_interpreted": result["authority_boundary"]["supporting_document_content_interpreted"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
