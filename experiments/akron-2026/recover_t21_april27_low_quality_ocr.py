#!/usr/bin/env python3
"""Recover raw Silver OCR for the frozen low-quality April 27 T21 artifacts.

The prior acquisition receipt froze a complete 20-document publisher-bounded
Bronze inventory. This stage selects only the four artifacts whose frozen
native profile reports at least one page below the 0.70 quality floor,
reacquires those exact publisher sources, requires exact Bronze reproduction,
and runs the existing bounded OCR path with force=False.

The output may contain raw extracted text for reproducibility, but this stage
does not contextually interpret supporting-document content and assigns no
event, hearing, outcome, detector, or lead authority.
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

SCHEMA = "proofline-akron-t21-april27-low-quality-ocr/v1"
STAGE = "raw_low_quality_supporting_document_ocr_before_contextual_reading"

LOW_SELECTION_SCHEMA = "proofline-akron-t21-april27-low-quality-ocr-selection/v1"
RECEIPT_SCHEMA = "proofline-akron-t21-april27-supporting-document-acquisition-receipt/v1"
RECEIPT_STAGE = "raw_bronze_inventory_receipt_before_contextual_document_reading"
FULL_SELECTION_SCHEMA = "proofline-akron-t21-april27-supporting-document-selection/v1"

EXPECTED_LOW_SELECTION_SIGNATURE = (
    "c9e84e94128510aed46d7ef03ed4e845ae9ea31bf888874814d29fb125a1d5f4"
)
EXPECTED_FULL_SELECTION_SIGNATURE = (
    "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
)
EXPECTED_ARTIFACT_COUNT = 4
EXPECTED_SOURCE_PAGE_COUNT = 48
EXPECTED_LOW_QUALITY_PAGE_COUNT = 41

EXPECTED_ARTIFACTS = {
    102589: {
        "source_uri_sha256": "3e2952c78d0c8c74a63ed39d41bdeae2bce476b5ac453a2399dce8defeeb8af9",
        "artifact_sha256": "44c74c2f8d01865a0242b3eed7d4fd6b22306cde781d6e78037e59774e981bdc",
        "page_count": 33,
        "native_low_quality_page_count": 33,
        "page_metadata_signature_sha256": "95598036c50606fdb1e1efedede029c2a7b26a7d27485b6a6ce09d0f42166b9b",
    },
    102590: {
        "source_uri_sha256": "eebf0cbd983d37de8c3b7c7980c0db771ae20c959bc650b828765df72ed513f9",
        "artifact_sha256": "c628216c674093d496d107b2588a42730ef30f1de2ec7657b3c6de313379093e",
        "page_count": 8,
        "native_low_quality_page_count": 3,
        "page_metadata_signature_sha256": "bb170e590722fac511ba5b78fac0ef6971669e5dd87cfc2f01b590d467e74738",
    },
    102593: {
        "source_uri_sha256": "068a08eb29582bd219d1903a2ce8a2052cb6534b88f8dd13ba49159c0825bddc",
        "artifact_sha256": "a3b406e939cfde7ad94c967ba7545e0f96481929e92d1d20dfdcbc9d1a005332",
        "page_count": 1,
        "native_low_quality_page_count": 1,
        "page_metadata_signature_sha256": "401cd6250390179b592f550518bc90035438d7ff21a0588e69a8619a973994f1",
    },
    102597: {
        "source_uri_sha256": "b83d8d13792c5074535a1823689a70ca756a23925e263e017b8ccb9102242dfb",
        "artifact_sha256": "6a0eec8ab93895d5e2dda11f300c23436510df178e697b3ef85d36c3479e7668",
        "page_count": 6,
        "native_low_quality_page_count": 4,
        "page_metadata_signature_sha256": "1386826286429e851891b5d9b6c05825a8c0f73334adb88bb5ad6726793a1cb5",
    },
}


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
        raise ValueError("unexpected low-quality OCR selection schema")
    if selection.get("selection_method") != "artifact.native_low_quality_page_count > 0":
        raise ValueError("low-quality OCR selection method drifted")
    rows = selection.get("selected_artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("low-quality OCR selection must contain selected_artifacts")
    normalized = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("selected artifact row must be an object")
        publish_id = row.get("publish_id")
        if not isinstance(publish_id, int) or publish_id <= 0:
            raise ValueError("selected artifact publish_id must be positive")
        if publish_id in seen:
            raise ValueError(f"duplicate selected artifact publish_id={publish_id}")
        seen.add(publish_id)
        normalized.append(
            {
                "publish_id": publish_id,
                "source_uri_sha256": row.get("source_uri_sha256"),
                "artifact_sha256": row.get("artifact_sha256"),
                "page_count": row.get("page_count"),
                "native_low_quality_page_count": row.get("native_low_quality_page_count"),
                "page_metadata_signature_sha256": row.get("page_metadata_signature_sha256"),
            }
        )
    normalized.sort(key=lambda row: row["publish_id"])
    if len(normalized) != EXPECTED_ARTIFACT_COUNT:
        raise ValueError("low-quality OCR selection must contain exactly four artifacts")
    if selection.get("selected_artifact_count") != len(normalized):
        raise ValueError("selected_artifact_count drifted")
    if sum(int(row["page_count"]) for row in normalized) != EXPECTED_SOURCE_PAGE_COUNT:
        raise ValueError("selected source-page accounting drifted")
    if sum(int(row["native_low_quality_page_count"]) for row in normalized) != EXPECTED_LOW_QUALITY_PAGE_COUNT:
        raise ValueError("selected low-quality page accounting drifted")
    if _sha256_json(normalized) != EXPECTED_LOW_SELECTION_SIGNATURE:
        raise ValueError("low-quality OCR selection signature drifted")
    if selection.get("selection_signature_sha256") != EXPECTED_LOW_SELECTION_SIGNATURE:
        raise ValueError("stored low-quality OCR selection signature drifted")
    return tuple(normalized)


def verify_frozen_inputs(*, low_selection: dict, receipt: dict, full_selection: dict) -> tuple[dict, ...]:
    rows = low_selection_rows(low_selection)
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected acquisition receipt schema")
    if receipt.get("stage") != RECEIPT_STAGE:
        raise ValueError("unexpected acquisition receipt stage")
    if full_selection.get("schema") != FULL_SELECTION_SCHEMA:
        raise ValueError("unexpected full supporting-document selection schema")
    if full_selection.get("selection_signature_sha256") != EXPECTED_FULL_SELECTION_SIGNATURE:
        raise ValueError("full supporting-document selection signature drifted")
    inventory = receipt.get("inventory") or {}
    receipt_rows = inventory.get("document_rows") or []
    expected = [
        {
            "publish_id": row["publish_id"],
            "source_uri_sha256": row["source_uri_sha256"],
            "artifact_sha256": row["artifact_sha256"],
            "page_count": row["page_count"],
            "native_low_quality_page_count": row["native_low_quality_page_count"],
            "page_metadata_signature_sha256": row["page_metadata_signature_sha256"],
        }
        for row in receipt_rows
        if row.get("native_low_quality_page_count", 0) > 0
    ]
    expected.sort(key=lambda row: row["publish_id"])
    if tuple(expected) != rows:
        raise ValueError("low-quality OCR selection no longer matches frozen receipt")
    if inventory.get("unique_bronze_artifact_count") != 20:
        raise ValueError("acquisition receipt unique artifact count drifted")
    if inventory.get("unique_artifact_page_count") != 88:
        raise ValueError("acquisition receipt page count drifted")
    if inventory.get("unique_artifact_native_low_quality_page_count") != 41:
        raise ValueError("acquisition receipt low-quality page count drifted")
    if inventory.get("quality_floor") != 0.7:
        raise ValueError("acquisition receipt quality floor drifted")
    boundary = receipt.get("authority_boundary") or {}
    if boundary.get("supporting_document_content_interpreted") is not False:
        raise ValueError("acquisition receipt must precede contextual reading")
    if boundary.get("outcome_assigned") is not False:
        raise ValueError("acquisition receipt must not assign outcome")
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
            raise ValueError(f"selected source missing from bounded manifest: {row['publish_id']}")
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
    return SourceManifest(name="akron-t21-april27-low-quality-ocr-artifacts", resources=tuple(resources)), selected_relations


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
        raise ValueError("T21 low-quality OCR threshold is frozen at 0.70")
    rows = verify_frozen_inputs(low_selection=low_selection, receipt=receipt, full_selection=full_selection)
    manifest, selected_relations = bounded_manifest(low_selection=low_selection, full_selection=full_selection, relations=relations, attachment_manifest=attachment_manifest)
    watcher = OnBaseAttachmentWatcher(state_dir)
    watch = watcher.run(manifest)
    results = watch.get("results") or []
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"selected OCR source unavailable: {watch['counts']}")
    if len(results) != EXPECTED_ARTIFACT_COUNT:
        raise RuntimeError("selected OCR acquisition must return exactly four results")
    result_by_hash = {_sha256_text(str(result.get("source_uri") or "")): result for result in results}
    store = ProoflineStore(state_dir / "proofline.db")
    acquisition = _acquisition_module()
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    artifacts = []
    aggregate_ocr = Counter()
    aggregate_methods = Counter()
    preferred_nonblank_page_count = 0
    preferred_quality_floor_page_count = 0
    preferred_ocr_page_count = 0
    for row in rows:
        expected = EXPECTED_ARTIFACTS[row["publish_id"]]
        result = result_by_hash.get(row["source_uri_sha256"])
        if result is None or not result.get("artifact_id"):
            raise RuntimeError(f"missing acquired artifact for publish_id={row['publish_id']}")
        artifact_id = str(result["artifact_id"])
        expected_artifact_id = f"artifact:{expected['artifact_sha256']}"
        if artifact_id != expected_artifact_id:
            raise RuntimeError(f"Bronze artifact drifted for publish_id={row['publish_id']}: expected={expected_artifact_id} actual={artifact_id}")
        pre_profile = acquisition._artifact_profile(store, artifact_id, threshold=threshold)
        for key in ("sha256", "page_count", "native_low_quality_page_count", "page_metadata_signature_sha256"):
            expected_key = "artifact_sha256" if key == "sha256" else key
            if pre_profile[key] != expected[expected_key]:
                raise RuntimeError(f"pre-OCR native profile drifted for publish_id={row['publish_id']} field={key}")
        ocr = ProgressiveExtractor(state_dir).run_ocr(artifact_id, backend, threshold=threshold, force=False)
        ocr_dict = ocr.to_dict()
        for key in ("candidates", "attempted", "added", "skipped", "failed"):
            aggregate_ocr[key] += int(ocr_dict[key])
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
            is_ocr = method == backend.name
            nonblank = bool(text.strip())
            meets_floor = quality is not None and float(quality) >= threshold
            aggregate_methods[method] += 1
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
                    "sha256": expected["artifact_sha256"],
                    "page_count": expected["page_count"],
                    "pre_ocr_native_low_quality_page_count": expected["native_low_quality_page_count"],
                    "pre_ocr_page_metadata_signature_sha256": expected["page_metadata_signature_sha256"],
                },
                "publisher_relation": {
                    "meeting_id": selected_relations[row["publish_id"]].get("meeting_id"),
                    "item_id": selected_relations[row["publish_id"]].get("item_id"),
                    "publish_id": row["publish_id"],
                },
                "ocr": ocr_dict,
                "silver_pages": pages,
            }
        )
    if aggregate_ocr["candidates"] != EXPECTED_LOW_QUALITY_PAGE_COUNT:
        raise RuntimeError("OCR candidate accounting no longer matches frozen 41-page frontier")
    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "frozen_inputs": {
            "low_quality_selection_signature_sha256": EXPECTED_LOW_SELECTION_SIGNATURE,
            "full_supporting_document_selection_signature_sha256": EXPECTED_FULL_SELECTION_SIGNATURE,
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
            "preferred_method_counts": dict(sorted(aggregate_methods.items())),
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
    print(
        json.dumps(
            {
                "selected_artifact_count": result["silver"]["artifact_count"],
                "silver_page_count": result["silver"]["page_count"],
                "ocr_candidates": result["ocr"]["candidates"],
                "ocr_attempted": result["ocr"]["attempted"],
                "ocr_added": result["ocr"]["added"],
                "ocr_failed": result["ocr"]["failed"],
                "supporting_document_content_interpreted": result["authority_boundary"]["supporting_document_content_interpreted"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
