#!/usr/bin/env python3
"""Blind validation of frozen source-span-v2 on the R1.T20 ranks 97-128 holdout.

This is the first content-opening stage for the frozen T20 validation block. It
uses unchanged parser v3, spatial extraction, source-span-v2, and local-grouping-v1.
It emits machine geometry/topology evidence only; no contextual semantic audit is
performed here and no positive outcome is required.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_local_grouping_holdout import (
    PARSER_VERSION,
    _artifact_metadata,
    _money_facts,
    _preferred_pages,
    _spatial_page,
    _tesseract_version,
)
from proofline.hashing import sha256_text, source_id_from_uri
from proofline.local_grouping import LOCAL_GROUPING_METHOD, nearest_neighbor_components
from proofline.local_layout import region_from_word_indices
from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.spatial_anchor import SPATIAL_TEXT_ANCHOR_METHOD, anchor_source_span
from proofline.storage import ProoflineStore
from proofline.watch_storage import WatcherStore
from sync_t20_attachment_holdout import (
    EXPECTED_SELECTED,
    EXPECTED_SELECTED_SIGNATURE,
    OUTPUT_SCHEMA as SELECTION_SYNC_SCHEMA,
)

SCHEMA = "proofline-akron-t20b-spatial-anchor-holdout/v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate(
    state_dir: Path,
    *,
    selection_sync: dict,
    threshold: float,
    language: str,
    dpi: int,
) -> dict:
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T20 frozen attachment sync schema")
    selection = selection_sync.get("selection") or {}
    if selection.get("selected_signature_sha256") != EXPECTED_SELECTED_SIGNATURE:
        raise ValueError("T20b holdout sync no longer matches frozen ranks 97-128 identities")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != EXPECTED_SELECTED:
        raise ValueError("T20b holdout requires exactly 32 source identities")

    tesseract_version = _tesseract_version()
    if tesseract_version is None:
        raise RuntimeError("Tesseract is unavailable; T20b must preserve the frozen OCR path")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type="supporting_document_of")
    related_sources = {relation.source_uri for relation in relations}

    sources_by_artifact: dict[str, list[dict]] = defaultdict(list)
    metadata_by_artifact: dict[str, dict] = {}
    for selected in selected_sources:
        source_uri = str(selected["source_uri"])
        source_hash = str(selected["source_uri_sha256"])
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id) or store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"T20b selected source has no successful artifact: {source_hash}")
        if source_uri not in related_sources:
            raise RuntimeError(f"T20b selected source lost publisher-backed parent relation: {source_hash}")
        metadata = metadata_by_artifact.setdefault(artifact_id, _artifact_metadata(store, artifact_id))
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"T20b selected attachment is not PDF: {source_hash}")
        sources_by_artifact[artifact_id].append({"source_uri_sha256": source_hash})

    for records in sources_by_artifact.values():
        records.sort(key=lambda item: item["source_uri_sha256"])

    extractor = ProgressiveExtractor(state_dir)
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    ocr_results = {}
    for artifact_id in sorted(sources_by_artifact):
        pages = _preferred_pages(store, artifact_id)
        if any(page["quality_score"] < threshold for page in pages):
            ocr_results[artifact_id] = extractor.run_ocr(
                artifact_id, backend, threshold=threshold, force=False
            ).to_dict()

    aggregate = Counter()
    component_sizes = Counter()
    anchor_failures = Counter()
    unattempted_reasons = Counter()
    boundary_punctuation = Counter()
    page_results = []
    artifact_results = []

    for artifact_id in sorted(sources_by_artifact):
        metadata = metadata_by_artifact[artifact_id]
        path = state_dir / metadata["stored_path"]
        if not path.is_file():
            raise RuntimeError(f"stored T20b attachment bytes are missing: {path}")

        artifact_money_facts = 0
        artifact_anchor_count = 0
        artifact_grouped_pages = 0
        pages = _preferred_pages(store, artifact_id)

        for page in pages:
            aggregate["page_count"] += 1
            facts = _money_facts(page["text"])
            if not facts:
                continue
            fact_count = len(facts)
            artifact_money_facts += fact_count
            aggregate["money_bearing_page_count"] += 1
            aggregate["page_parser_money_fact_count"] += fact_count

            base_result = {
                "artifact_id": artifact_id,
                "artifact_sha256": metadata["sha256"],
                "evidence_id": page["evidence_id"],
                "page_number": page["page_number"],
                "locator": page["locator"],
                "preferred_method": page["method"],
                "quality_score": page["quality_score"],
                "source_text_sha256": sha256_text(page["text"]),
                "fact_count": fact_count,
                "anchor_count": 0,
                "anchor_failure_count": 0,
                "unattempted_fact_count": 0,
                "cross_line_anchor_count": 0,
                "boundary_expanded_anchor_count": 0,
                "region_count": 0,
                "component_count": 0,
                "status": None,
                "anchor_failures": [],
                "regions": [],
                "grouping": None,
            }

            if page["quality_score"] < threshold:
                aggregate["money_bearing_low_quality_page_count"] += 1
                aggregate["unattempted_money_fact_count"] += fact_count
                aggregate["low_quality_unattempted_fact_count"] += fact_count
                unattempted_reasons["below_quality_floor_after_progressive_ocr"] += fact_count
                base_result["unattempted_fact_count"] = fact_count
                base_result["status"] = "below_quality_floor_after_progressive_ocr"
                page_results.append(base_result)
                continue

            spatial = _spatial_page(path, page, artifact_id=artifact_id)
            if spatial is None:
                aggregate["unsupported_preferred_method_page_count"] += 1
                aggregate["unattempted_money_fact_count"] += fact_count
                aggregate["unsupported_method_unattempted_fact_count"] += fact_count
                unattempted_reasons["unsupported_preferred_extraction_method"] += fact_count
                base_result["unattempted_fact_count"] = fact_count
                base_result["status"] = "unsupported_preferred_extraction_method"
                page_results.append(base_result)
                continue
            if spatial.source_text_sha256 != sha256_text(page["text"]):
                raise RuntimeError(f"T20b spatial text drifted from preferred Silver for {page['evidence_id']}")

            aggregate["spatialized_money_bearing_page_count"] += 1
            by_region: dict[str, dict] = {}
            page_anchor_count = 0
            page_cross_line_count = 0
            page_expanded_count = 0
            page_failures = []

            for fact in facts:
                if fact["char_start"] is None or fact["char_end"] is None:
                    reason = "missing_source_span"
                    anchor_failures[reason] += 1
                    page_failures.append({"reason": reason, "raw_text": fact["raw_text"]})
                    continue
                try:
                    anchor = anchor_source_span(
                        spatial,
                        page["text"],
                        char_start=int(fact["char_start"]),
                        char_end=int(fact["char_end"]),
                    )
                except ValueError as exc:
                    reason = str(exc)
                    anchor_failures[reason] += 1
                    page_failures.append({"reason": reason, "raw_text": fact["raw_text"]})
                    continue

                region = region_from_word_indices(spatial, anchor.word_order_indices)
                record = by_region.setdefault(
                    region.region_id,
                    {"region": region, "observations": []},
                )
                record["observations"].append(
                    {
                        "raw_text": fact["raw_text"],
                        "normalized_text": fact["normalized_text"],
                        "char_start": fact["char_start"],
                        "char_end": fact["char_end"],
                        "anchor": anchor.to_dict(),
                    }
                )
                page_anchor_count += 1
                page_cross_line_count += int(anchor.crosses_line_identity)
                if anchor.expanded_to_word_boundary:
                    page_expanded_count += 1
                    boundary_punctuation.update(
                        anchor.leading_boundary_punctuation + anchor.trailing_boundary_punctuation
                    )

            ordered = sorted(
                by_region.values(),
                key=lambda item: (item["region"].word_order_indices, item["region"].region_id),
            )
            regions = [item["region"] for item in ordered]

            covered: set[int] = set()
            overlap_words: set[int] = set()
            for region in regions:
                overlap_words.update(covered.intersection(region.word_order_indices))
                covered.update(region.word_order_indices)

            grouping = None
            status = "anchored_no_region" if not regions else "anchored"
            if overlap_words:
                aggregate["overlapping_region_page_count"] += 1
                aggregate["overlapping_region_word_count"] += len(overlap_words)
                status = "overlapping_regions_not_grouped"
            elif regions:
                try:
                    grouping = nearest_neighbor_components(spatial, regions)
                except ValueError as exc:
                    aggregate["grouping_failure_page_count"] += 1
                    status = "grouping_constraint_failure"
                    base_result["grouping_failure_reason"] = str(exc)
                else:
                    status = "grouped"
                    aggregate["grouped_page_count"] += 1
                    artifact_grouped_pages += 1
                    aggregate["component_count"] += len(grouping.components)
                    aggregate["nearest_directed_edge_count"] += len(grouping.nearest_edges)
                    aggregate["mutual_nearest_directed_edge_count"] += sum(
                        edge.mutual_nearest for edge in grouping.nearest_edges
                    )
                    for component in grouping.components:
                        component_sizes[len(component.region_ids)] += 1

            failure_count = len(page_failures)
            aggregate["anchored_money_fact_count"] += page_anchor_count
            aggregate["anchor_failure_count"] += failure_count
            aggregate["cross_line_anchor_count"] += page_cross_line_count
            aggregate["same_line_anchor_count"] += page_anchor_count - page_cross_line_count
            aggregate["boundary_expanded_anchor_count"] += page_expanded_count
            aggregate["spatial_money_region_count"] += len(regions)
            artifact_anchor_count += page_anchor_count

            base_result.update(
                {
                    "spatial_id": spatial.spatial_id,
                    "spatial_method": spatial.spatial_method,
                    "word_signature_sha256": spatial.word_signature_sha256,
                    "anchor_count": page_anchor_count,
                    "anchor_failure_count": failure_count,
                    "cross_line_anchor_count": page_cross_line_count,
                    "boundary_expanded_anchor_count": page_expanded_count,
                    "region_count": len(regions),
                    "component_count": len(grouping.components) if grouping else 0,
                    "overlapping_word_order_indices": sorted(overlap_words),
                    "status": status,
                    "anchor_failures": page_failures,
                    "regions": [
                        {
                            "region": item["region"].to_dict(),
                            "observations": item["observations"],
                        }
                        for item in ordered
                    ],
                    "grouping": grouping.to_dict() if grouping else None,
                }
            )
            page_results.append(base_result)

        artifact_results.append(
            {
                "artifact_id": artifact_id,
                "artifact_sha256": metadata["sha256"],
                "source_uri_sha256s": [item["source_uri_sha256"] for item in sources_by_artifact[artifact_id]],
                "source_identity_count": len(sources_by_artifact[artifact_id]),
                "page_count": len(pages),
                "page_parser_money_fact_count": artifact_money_facts,
                "anchored_money_fact_count": artifact_anchor_count,
                "grouped_page_count": artifact_grouped_pages,
                "ocr": ocr_results.get(artifact_id),
            }
        )

    ocr_attempted = sum(item["attempted"] for item in ocr_results.values())
    ocr_added = sum(item["added"] for item in ocr_results.values())
    ocr_failed = sum(item["failed"] for item in ocr_results.values())

    return {
        "schema": SCHEMA,
        "stage": "blind_t20b_holdout_machine_output_before_contextual_audit",
        "frozen_inputs": {
            "selection_signature_sha256": EXPECTED_SELECTED_SIGNATURE,
            "anchor_method": SPATIAL_TEXT_ANCHOR_METHOD,
            "grouping_method": LOCAL_GROUPING_METHOD,
            "parser_version": PARSER_VERSION,
            "quality_floor": threshold,
            "default_ocr_language": language,
            "default_ocr_dpi": dpi,
        },
        "runtime": {"tesseract_version": tesseract_version},
        "sample": {
            "selected_source_identity_count": len(selected_sources),
            "unique_artifact_count": len(sources_by_artifact),
            "duplicate_artifact_group_count": sum(len(items) > 1 for items in sources_by_artifact.values()),
        },
        "extraction": {
            "page_count": aggregate["page_count"],
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
            "money_bearing_low_quality_page_count": aggregate["money_bearing_low_quality_page_count"],
        },
        "result": {
            "money_bearing_page_count": aggregate["money_bearing_page_count"],
            "page_parser_money_fact_count": aggregate["page_parser_money_fact_count"],
            "spatialized_money_bearing_page_count": aggregate["spatialized_money_bearing_page_count"],
            "anchored_money_fact_count": aggregate["anchored_money_fact_count"],
            "anchor_failure_count": aggregate["anchor_failure_count"],
            "unattempted_money_fact_count": aggregate["unattempted_money_fact_count"],
            "low_quality_unattempted_fact_count": aggregate["low_quality_unattempted_fact_count"],
            "unsupported_method_unattempted_fact_count": aggregate["unsupported_method_unattempted_fact_count"],
            "cross_line_anchor_count": aggregate["cross_line_anchor_count"],
            "same_line_anchor_count": aggregate["same_line_anchor_count"],
            "boundary_expanded_anchor_count": aggregate["boundary_expanded_anchor_count"],
            "boundary_punctuation_counts": dict(sorted(boundary_punctuation.items())),
            "spatial_money_region_count": aggregate["spatial_money_region_count"],
            "unsupported_preferred_method_page_count": aggregate["unsupported_preferred_method_page_count"],
            "overlapping_region_page_count": aggregate["overlapping_region_page_count"],
            "overlapping_region_word_count": aggregate["overlapping_region_word_count"],
            "grouping_failure_page_count": aggregate["grouping_failure_page_count"],
            "grouped_page_count": aggregate["grouped_page_count"],
            "component_count": aggregate["component_count"],
            "component_size_counts": dict(sorted(component_sizes.items())),
            "nearest_directed_edge_count": aggregate["nearest_directed_edge_count"],
            "mutual_nearest_directed_edge_count": aggregate["mutual_nearest_directed_edge_count"],
            "anchor_failure_reasons": dict(sorted(anchor_failures.items())),
            "unattempted_fact_reasons": dict(sorted(unattempted_reasons.items())),
        },
        "artifact_results": artifact_results,
        "page_results": page_results,
        "semantic_boundary": {
            "contextual_audit_performed": False,
            "table_semantics_assigned": False,
            "field_semantics_assigned": False,
            "financial_semantics_authorized": False,
            "event_identity_assigned": False,
            "independence_assessed": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "Source-span anchors are geometry lineage for existing parser spans, not financial or field semantics.",
            "Nearest-neighbor components are geometric observations, not rows, transactions, events, anomalies, conflicts, suspiciousness, wrongdoing, or leads.",
            "No minimum anchor, money, grouped-page, component, or positive-transfer outcome is required by this validation.",
            "The frozen source-span-v2 representation must not be tuned after this holdout opening and then reported as this blind result."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        raise ValueError("quality threshold must be in [0, 1]")
    if args.dpi < 72:
        raise ValueError("OCR dpi must be at least 72")

    result = evaluate(
        Path(args.state_dir),
        selection_sync=_load(args.selection_sync),
        threshold=args.threshold,
        language=args.language,
        dpi=args.dpi,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["result"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
