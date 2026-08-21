#!/usr/bin/env python3
"""Recover raw Silver OCR for the single unique T21 publisher-backed packet.

The completed T21 byte-evolution receipt established that 24 distinct publisher
source identities resolve to one content-addressed Bronze PDF. This stage
reacquires one deterministic representative source, requires the exact frozen
Bronze artifact, runs the existing bounded OCR path once, and emits raw Silver
evidence only. It does not interpret packet content or assign event, outcome,
detector, or lead authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from proofline.ocr import PyMuPDFTesseractBackend
from proofline.onbase_attachments import OnBaseAttachmentWatcher
from proofline.progressive import ProgressiveExtractor
from proofline.review import preferred_extraction
from proofline.storage import ProoflineStore
from proofline.watcher import ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-record-family-packet-ocr/v1"
STAGE = "raw_packet_ocr_silver_before_contextual_interpretation"

RECEIPT_SCHEMA = "proofline-akron-t21-record-family-evolution-summary/v1"
RECEIPT_STAGE = (
    "post_packet_sync_raw_byte_evolution_receipt_before_ocr_or_contextual_interpretation"
)
SELECTION_SCHEMA = "proofline-akron-t21-record-family-packet-selection/v1"

EXPECTED_SELECTION_SIGNATURE = (
    "b46265ee254267230fa62dfc6dbc4a537fa608bd5052844fd19ffedb2a320921"
)
EXPECTED_ARTIFACT_SHA256 = (
    "87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
)
EXPECTED_ARTIFACT_ID = f"artifact:{EXPECTED_ARTIFACT_SHA256}"
EXPECTED_PAGE_COUNT = 3
EXPECTED_PACKET_SOURCE_COUNT = 24

EXPECTED_REPRESENTATIVE = {
    "meeting_id": 668,
    "item_id": 46485,
    "publish_id": 100240,
    "source_uri_sha256": (
        "a107c2c3331a4f6f6511b7031dcbef193b92d638692580e904d87b0068f454cc"
    ),
}


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evolution_module():
    path = Path(__file__).with_name("measure_t21_record_family_evolution.py")
    spec = importlib.util.spec_from_file_location("t21_record_family_evolution", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load frozen T21 evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_receipt(receipt: dict, selection: dict) -> None:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected T21 record-family evolution receipt schema")
    if receipt.get("stage") != RECEIPT_STAGE:
        raise ValueError("T21 record-family receipt is not the pre-OCR frozen stage")
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError("unexpected T21 packet selection schema")
    if selection.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T21 packet selection signature drifted")
    if selection.get("selected_packet_count") != EXPECTED_PACKET_SOURCE_COUNT:
        raise ValueError("T21 packet selection must contain exactly 24 source identities")

    receipt_selection = receipt.get("selection") or {}
    counts = receipt.get("counts") or {}
    artifact = receipt.get("unique_bronze_packet") or {}
    boundary = receipt.get("interpretation_boundary") or {}

    if receipt_selection.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("receipt selection signature drifted")
    if counts.get("packet_source_count") != EXPECTED_PACKET_SOURCE_COUNT:
        raise ValueError("receipt packet source count drifted")
    if counts.get("unique_bronze_artifact_count") != 1:
        raise ValueError("receipt no longer establishes exactly one Bronze artifact")
    if counts.get("consecutive_bronze_change_count") != 0:
        raise ValueError("receipt no longer establishes byte-invariant packet chronology")
    if artifact.get("artifact_id") != EXPECTED_ARTIFACT_ID:
        raise ValueError("receipt Bronze artifact ID drifted")
    if artifact.get("sha256") != EXPECTED_ARTIFACT_SHA256:
        raise ValueError("receipt Bronze artifact SHA-256 drifted")
    if artifact.get("page_count") != EXPECTED_PAGE_COUNT:
        raise ValueError("receipt Bronze page count drifted")
    if boundary.get("ocr_performed_in_this_stage") is not False:
        raise ValueError("receipt must precede OCR")
    if boundary.get("base_packet_content_interpreted") is not False:
        raise ValueError("receipt must precede packet interpretation")


def representative_manifest(
    selection: dict,
    relations: list[dict],
    attachment_manifest: dict,
) -> tuple[SourceManifest, dict]:
    module = _evolution_module()
    selected = module._selection_rows(selection)
    if not selected or selected[0] != EXPECTED_REPRESENTATIVE:
        raise ValueError("deterministic representative identity drifted")

    verified = module.verify_publisher_relations(selection, relations)
    bounded = module.selected_manifest(selection, verified, attachment_manifest)

    relation_by_identity = {
        (
            int(relation["meeting_id"]),
            int(relation["item_id"]),
            int(relation["publish_id"]),
        ): relation
        for relation in verified
    }
    identity = (
        EXPECTED_REPRESENTATIVE["meeting_id"],
        EXPECTED_REPRESENTATIVE["item_id"],
        EXPECTED_REPRESENTATIVE["publish_id"],
    )
    relation = relation_by_identity.get(identity)
    if relation is None:
        raise ValueError("representative publisher relation is missing")

    source_uri = str(relation.get("source_uri") or "")
    source_hash = hashlib.sha256(source_uri.encode("utf-8")).hexdigest()
    if source_hash != EXPECTED_REPRESENTATIVE["source_uri_sha256"]:
        raise ValueError("representative source URI hash drifted")

    resource_by_uri = {resource.source_uri: resource for resource in bounded.resources}
    resource = resource_by_uri.get(source_uri)
    if resource is None:
        raise ValueError("representative source is missing from bounded manifest")

    return (
        SourceManifest(
            name="akron-t21-single-unique-record-family-packet",
            resources=(
                ManifestResource(
                    source_uri=resource.source_uri,
                    source_name=resource.source_name,
                    native_identifier=resource.native_identifier,
                    expected_media_type=resource.expected_media_type,
                    sequence_group=resource.sequence_group,
                    sequence_number=resource.sequence_number,
                    fetch_strategy=resource.fetch_strategy,
                ),
            ),
        ),
        relation,
    )


def _artifact_metadata(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT artifact_id, sha256, byte_size, media_type, stored_path "
            "FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"unknown OCR packet artifact: {artifact_id}")
    return dict(row)


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


def recover(
    *,
    state_dir: Path,
    selection: dict,
    receipt: dict,
    relations: list[dict],
    attachment_manifest: dict,
    threshold: float,
    language: str,
    dpi: int,
) -> dict:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    verify_receipt(receipt, selection)
    manifest, relation = representative_manifest(selection, relations, attachment_manifest)

    watcher = OnBaseAttachmentWatcher(state_dir)
    watch = watcher.run(manifest)
    results = watch.get("results") or []
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"representative packet acquisition unavailable: {watch['counts']}")
    if len(results) != 1 or not results[0].get("artifact_id"):
        raise RuntimeError("representative packet acquisition must yield exactly one artifact")
    artifact_id = str(results[0]["artifact_id"])
    if artifact_id != EXPECTED_ARTIFACT_ID:
        raise RuntimeError(
            "representative source no longer reproduces frozen Bronze artifact: "
            f"{artifact_id}"
        )

    store = ProoflineStore(state_dir / "proofline.db")
    artifact = _artifact_metadata(store, artifact_id)
    if artifact["sha256"] != EXPECTED_ARTIFACT_SHA256:
        raise RuntimeError("stored Bronze SHA-256 differs from frozen receipt")
    if artifact["media_type"] != "application/pdf":
        raise RuntimeError("frozen packet artifact is no longer a PDF")

    pages_before = _page_units(store, artifact_id)
    if len(pages_before) != EXPECTED_PAGE_COUNT:
        raise RuntimeError("reacquired Bronze packet does not have the frozen three pages")

    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    ocr = ProgressiveExtractor(state_dir).run_ocr(
        artifact_id,
        backend,
        threshold=threshold,
        force=False,
    )

    pages: list[dict] = []
    preferred_ocr_page_count = 0
    nonblank_page_count = 0
    quality_floor_page_count = 0
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
        is_ocr = method == backend.name
        meets_floor = quality is not None and float(quality) >= threshold
        preferred_ocr_page_count += int(is_ocr)
        nonblank_page_count += int(bool(text.strip()))
        quality_floor_page_count += int(meets_floor)

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
                    "nonblank": bool(text.strip()),
                    "meets_quality_floor": meets_floor,
                    "text": text,
                },
            }
        )

    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "frozen_inputs": {
            "selection_signature_sha256": EXPECTED_SELECTION_SIGNATURE,
            "record_family_evolution_receipt_artifact_id": receipt["canonical_run"][
                "artifact_id"
            ],
            "record_family_evolution_receipt_artifact_digest": receipt["canonical_run"][
                "artifact_digest"
            ],
            "bronze_artifact_id": EXPECTED_ARTIFACT_ID,
            "bronze_sha256": EXPECTED_ARTIFACT_SHA256,
            "bronze_page_count": EXPECTED_PAGE_COUNT,
            "quality_floor": threshold,
            "ocr_language": language,
            "ocr_dpi": dpi,
        },
        "representative_source": {
            **EXPECTED_REPRESENTATIVE,
            "source_uri": manifest.resources[0].source_uri,
            "publisher_relation": {
                "relation_type": "supporting_document_of",
                "parent_source_uri": relation.get("parent_source_uri"),
                "parent_artifact_id": relation.get("parent_artifact_id"),
                "parent_artifact_sha256": relation.get("parent_artifact_sha256"),
                "link_text": relation.get("link_text"),
            },
            "watch": {
                "state": results[0].get("state"),
                "checked_at": results[0].get("checked_at"),
                "source_id": results[0].get("source_id"),
            },
        },
        "bronze": {
            "artifact_id": artifact_id,
            "sha256": artifact["sha256"],
            "byte_size": int(artifact["byte_size"]),
            "media_type": artifact["media_type"],
            "page_count": len(pages_before),
        },
        "ocr": ocr.to_dict(),
        "silver": {
            "page_count": len(pages),
            "preferred_ocr_page_count": preferred_ocr_page_count,
            "nonblank_page_count": nonblank_page_count,
            "quality_floor_page_count": quality_floor_page_count,
            "pages": pages,
        },
        "lineage_reuse": {
            "publisher_source_identity_count": EXPECTED_PACKET_SOURCE_COUNT,
            "unique_bronze_artifact_count": 1,
            "silver_extracted_once_for_content_addressed_artifact": True,
            "source_relation_created": False,
            "source_family_modified": False,
        },
        "authority_boundary": {
            "packet_content_interpreted": False,
            "event_identity_assigned": False,
            "meeting_occurrence_asserted": False,
            "outcome_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
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
        selection=_load(args.selection),
        receipt=_load(args.receipt),
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
                "bronze_artifact_id": result["bronze"]["artifact_id"],
                "ocr_candidates": result["ocr"]["candidates"],
                "ocr_attempted": result["ocr"]["attempted"],
                "ocr_added": result["ocr"]["added"],
                "ocr_failed": result["ocr"]["failed"],
                "silver_nonblank_page_count": result["silver"]["nonblank_page_count"],
                "silver_quality_floor_page_count": result["silver"][
                    "quality_floor_page_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
