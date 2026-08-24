#!/usr/bin/env python3
"""Replay T21 April 27 OCR with corrected ProgressiveExtractor accounting.

The v2 live attempt proved the corrected receipt, the four publisher identities,
and the exact Bronze/native profiles, then executed OCR but failed a wrapper
postcondition because ProgressiveExtractionResult.candidates counts *all* page
units presented to the gate. It is not the number of pages actually escalated.

For the frozen four-artifact population:
- 48 page units are presented to the progressive OCR gate;
- 41 are below the frozen 0.70 native-quality floor and are attempted;
- 7 already meet the floor and are skipped.

This v3 evaluator changes only that accounting contract. The source population,
Bronze hashes, OCR backend, threshold, language, DPI, force=False behavior, and
authority boundary are unchanged. No OCR text from the failed v2 run was read.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

from proofline.ocr import PyMuPDFTesseractBackend
from proofline.onbase_attachments import OnBaseAttachmentWatcher
from proofline.progressive import ProgressiveExtractor
from proofline.review import preferred_extraction
from proofline.storage import ProoflineStore

SCHEMA = "proofline-akron-t21-april27-low-quality-ocr/v3"
STAGE = "raw_low_quality_supporting_document_ocr_accounting_corrected_before_contextual_reading"
EXPECTED_PAGE_UNITS_PRESENTED = 48
EXPECTED_OCR_ATTEMPTED = 41
EXPECTED_OCR_SKIPPED = 7


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _v2_module():
    path = Path(__file__).with_name("recover_t21_april27_low_quality_ocr_v2.py")
    spec = importlib.util.spec_from_file_location("t21_low_ocr_v2_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load frozen v2 evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recover(
    *,
    state_dir: Path,
    low_selection: dict,
    receipt: dict,
    full_selection: dict,
    relations: list[dict],
    attachment_manifest: dict,
    threshold: float,
    language: str,
    dpi: int,
) -> dict:
    if threshold != 0.70:
        raise ValueError("T21 OCR threshold remains frozen at 0.70")

    v2 = _v2_module()
    rows = v2.verify_frozen_inputs(
        low_selection=low_selection,
        receipt=receipt,
        full_selection=full_selection,
    )
    manifest, selected_relations = v2.bounded_manifest(
        low_selection=low_selection,
        full_selection=full_selection,
        relations=relations,
        attachment_manifest=attachment_manifest,
    )

    watch = OnBaseAttachmentWatcher(state_dir).run(manifest)
    results = watch.get("results") or []
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"selected OCR source unavailable: {watch['counts']}")
    if len(results) != v2.EXPECTED_ARTIFACT_COUNT:
        raise RuntimeError("OCR replay must reacquire exactly four source identities")

    result_by_hash = {
        v2._sha256_text(str(result.get("source_uri") or "")): result
        for result in results
    }
    store = ProoflineStore(state_dir / "proofline.db")
    acquisition = v2._acquisition_module()
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)

    aggregate_ocr = Counter()
    preferred_methods = Counter()
    preferred_ocr_page_count = 0
    preferred_nonblank_page_count = 0
    preferred_quality_floor_page_count = 0
    artifacts = []

    for row in rows:
        result = result_by_hash.get(row["source_uri_sha256"])
        if result is None or not result.get("artifact_id"):
            raise RuntimeError(
                f"missing reacquired artifact for publish_id={row['publish_id']}"
            )
        artifact_id = str(result["artifact_id"])
        expected_artifact_id = f"artifact:{row['artifact_sha256']}"
        if artifact_id != expected_artifact_id:
            raise RuntimeError(
                f"Bronze artifact drifted for publish_id={row['publish_id']}"
            )

        pre = acquisition._artifact_profile(store, artifact_id, threshold=threshold)
        if pre["sha256"] != row["artifact_sha256"]:
            raise RuntimeError(f"Bronze SHA drifted for publish_id={row['publish_id']}")
        if pre["page_count"] != row["page_count"]:
            raise RuntimeError(f"page count drifted for publish_id={row['publish_id']}")
        if (
            pre["native_low_quality_page_count"]
            != row["native_low_quality_page_count"]
        ):
            raise RuntimeError(
                f"native low-quality count drifted for publish_id={row['publish_id']}"
            )
        if (
            pre["page_metadata_signature_sha256"]
            != row["page_metadata_signature_sha256"]
        ):
            raise RuntimeError(
                f"native page metadata drifted for publish_id={row['publish_id']}"
            )

        ocr = ProgressiveExtractor(state_dir).run_ocr(
            artifact_id,
            backend,
            threshold=threshold,
            force=False,
        ).to_dict()
        for key in ("candidates", "attempted", "added", "skipped", "failed"):
            aggregate_ocr[key] += int(ocr[key])

        pages = []
        for page_number, unit in enumerate(v2._page_units(store, artifact_id), start=1):
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
                        "text_sha256": v2._sha256_text(text),
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
                    "pre_ocr_native_low_quality_page_count": row[
                        "native_low_quality_page_count"
                    ],
                    "pre_ocr_page_metadata_signature_sha256": row[
                        "page_metadata_signature_sha256"
                    ],
                },
                "publisher_relation": {
                    "meeting_id": selected_relations[row["publish_id"]].get(
                        "meeting_id"
                    ),
                    "item_id": selected_relations[row["publish_id"]].get("item_id"),
                    "publish_id": row["publish_id"],
                },
                "ocr": ocr,
                "silver_pages": pages,
            }
        )

    if aggregate_ocr["candidates"] != EXPECTED_PAGE_UNITS_PRESENTED:
        raise RuntimeError(
            "progressive OCR page-unit accounting drifted from frozen 48-page population"
        )
    if aggregate_ocr["attempted"] != EXPECTED_OCR_ATTEMPTED:
        raise RuntimeError(
            "progressive OCR attempted-page accounting drifted from frozen 41-page frontier"
        )
    if aggregate_ocr["skipped"] != EXPECTED_OCR_SKIPPED:
        raise RuntimeError(
            "progressive OCR skipped-page accounting drifted from expected seven usable native pages"
        )
    if aggregate_ocr["attempted"] + aggregate_ocr["skipped"] != aggregate_ocr[
        "candidates"
    ]:
        raise RuntimeError("progressive OCR accounting does not partition page units")

    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "accounting_correction": {
            "failed_v2_run_id": 32600657882,
            "failed_v2_job_id": 97098314570,
            "failed_v2_ocr_text_read": False,
            "underlying_ocr_method_changed": False,
            "population_changed": False,
            "progressive_candidates_definition": "all page units presented to gate",
            "quality_gated_ocr_work_definition": "attempted page units",
        },
        "correction_lineage": {
            "superseded_v1_receipt_not_used": True,
            "corrected_receipt_raw_acquisition_json_sha256": receipt[
                "canonical_run"
            ]["raw_acquisition_json_sha256"],
            "corrected_low_quality_selection_signature_sha256": v2.EXPECTED_LOW_SELECTION_SIGNATURE,
        },
        "frozen_inputs": {
            "selected_artifact_count": v2.EXPECTED_ARTIFACT_COUNT,
            "selected_source_page_count": v2.EXPECTED_SOURCE_PAGE_COUNT,
            "pre_ocr_native_low_quality_page_count": v2.EXPECTED_LOW_QUALITY_PAGE_COUNT,
            "quality_floor": threshold,
            "ocr_language": language,
            "ocr_dpi": dpi,
        },
        "reacquisition": {
            "requested_source_count": v2.EXPECTED_ARTIFACT_COUNT,
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
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "page_units_presented": result["ocr"]["candidates"],
                "ocr_attempted": result["ocr"]["attempted"],
                "ocr_skipped": result["ocr"]["skipped"],
                "ocr_added": result["ocr"]["added"],
                "ocr_failed": result["ocr"]["failed"],
                "supporting_document_content_interpreted": result[
                    "authority_boundary"
                ]["supporting_document_content_interpreted"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
