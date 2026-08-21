#!/usr/bin/env python3
"""Post-hoc T19b development replay for source-span spatial anchoring.

Ranks 65-96 are already opened evidence. This script may measure whether the T20
anchor repairs the observed coverage gap, but its result is development evidence
only and cannot validate the repair. It requires exact source->artifact byte identity
with the original blind T19b run before evaluating anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_local_grouping_holdout import (
    EXPECTED_SELECTED_SIGNATURE,
    EXPECTED_SOURCES,
    PARSER_VERSION,
    SELECTION_SYNC_SCHEMA,
    _artifact_metadata,
    _money_facts,
    _preferred_pages,
    _spatial_page,
    _tesseract_version,
)
from proofline.hashing import source_id_from_uri
from proofline.local_grouping import LOCAL_GROUPING_METHOD, nearest_neighbor_components
from proofline.local_layout import region_from_word_indices
from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.spatial_anchor import SPATIAL_TEXT_ANCHOR_METHOD, anchor_source_span
from proofline.storage import ProoflineStore
from proofline.watch_storage import WatcherStore


SCHEMA = "proofline-akron-t20-spatial-anchor-t19b-development/v1"
EXPECTED_T19B_SOURCE_ARTIFACT_MAP_SIGNATURE = (
    "8e4bedc043544c701d2c2e6fee5dcb1fcda92d2322fbd98a5bba7b01f0a5c14d"
)


def _source_artifact_map_signature(pairs: list[tuple[str, str]]) -> str:
    payload = "".join(f"{source_hash} {artifact_sha256}\n" for source_hash, artifact_sha256 in sorted(pairs))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate(
    state_dir: Path,
    *,
    selection_sync: dict,
    threshold: float,
    language: str,
    dpi: int,
) -> dict:
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T19 frozen attachment sync schema")
    selection = selection_sync.get("selection") or {}
    if selection.get("selected_signature_sha256") != EXPECTED_SELECTED_SIGNATURE:
        raise ValueError("T19b development replay no longer matches frozen ranks 65-96 identities")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != EXPECTED_SOURCES:
        raise ValueError("T19b development replay requires exactly 32 source identities")

    tesseract_version = _tesseract_version()
    if tesseract_version is None:
        raise RuntimeError("Tesseract is unavailable; replay must preserve the T19b extraction path")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type="supporting_document_of")
    related_sources = {relation.source_uri for relation in relations}

    sources_by_artifact: dict[str, list[dict]] = defaultdict(list)
    metadata_by_artifact: dict[str, dict] = {}
    map_pairs: list[tuple[str, str]] = []
    for selected in selected_sources:
        source_uri = str(selected["source_uri"])
        source_hash = str(selected["source_uri_sha256"])
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id) or store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"T19b replay source has no successful artifact: {source_hash}")
        if source_uri not in related_sources:
            raise RuntimeError(f"T19b replay source lost publisher-backed relation: {source_hash}")
        metadata = metadata_by_artifact.setdefault(artifact_id, _artifact_metadata(store, artifact_id))
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"T19b replay source is not PDF: {source_hash}")
        sources_by_artifact[artifact_id].append({"source_uri_sha256": source_hash})
        map_pairs.append((source_hash, str(metadata["sha256"])))

    map_signature = _source_artifact_map_signature(map_pairs)
    if map_signature != EXPECTED_T19B_SOURCE_ARTIFACT_MAP_SIGNATURE:
        raise RuntimeError(
            "T19b publisher bytes no longer reproduce the blind source-artifact map: "
            f"{map_signature}"
        )

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
    page_results = []
    anchor_failures = Counter()

    for artifact_id in sorted(sources_by_artifact):
        metadata = metadata_by_artifact[artifact_id]
        path = state_dir / metadata["stored_path"]
        if not path.is_file():
            raise RuntimeError(f"stored replay attachment bytes are missing: {path}")

        for page in _preferred_pages(store, artifact_id):
            aggregate["page_count"] += 1
            facts = _money_facts(page["text"])
            if not facts:
                continue
            aggregate["money_bearing_page_count"] += 1
            aggregate["page_parser_money_fact_count"] += len(facts)

            spatial = _spatial_page(path, page, artifact_id=artifact_id)
            if spatial is None:
                aggregate["unsupported_preferred_method_page_count"] += 1
                page_results.append(
                    {
                        "artifact_id": artifact_id,
                        "page_number": page["page_number"],
                        "fact_count": len(facts),
                        "anchor_count": 0,
                        "status": "unsupported_preferred_method",
                    }
                )
                continue

            by_region: dict[str, dict] = {}
            page_anchor_count = 0
            page_cross_line_count = 0
            page_failures = []
            for fact in facts:
                if fact["char_start"] is None or fact["char_end"] is None:
                    reason = "missing_source_span"
                    anchor_failures[reason] += 1
                    page_failures.append(reason)
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
                    page_failures.append(reason)
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

            ordered = sorted(
                by_region.values(),
                key=lambda item: (item["region"].word_order_indices, item["region"].region_id),
            )
            regions = [item["region"] for item in ordered]
            covered: set[int] = set()
            for region in regions:
                overlap = covered.intersection(region.word_order_indices)
                if overlap:
                    raise RuntimeError(
                        "T20 anchored money regions overlap word membership: "
                        f"{artifact_id} page {page['page_number']} {sorted(overlap)}"
                    )
                covered.update(region.word_order_indices)

            grouping = nearest_neighbor_components(spatial, regions) if regions else None
            aggregate["anchored_money_fact_count"] += page_anchor_count
            aggregate["cross_line_anchor_count"] += page_cross_line_count
            aggregate["same_line_anchor_count"] += page_anchor_count - page_cross_line_count
            aggregate["spatial_money_region_count"] += len(regions)
            if grouping is not None:
                aggregate["grouped_page_count"] += 1
                aggregate["component_count"] += len(grouping.components)
                aggregate["nearest_directed_edge_count"] += len(grouping.nearest_edges)
                aggregate["mutual_nearest_directed_edge_count"] += sum(
                    edge.mutual_nearest for edge in grouping.nearest_edges
                )
                for component in grouping.components:
                    component_sizes[len(component.region_ids)] += 1

            page_results.append(
                {
                    "artifact_id": artifact_id,
                    "page_number": page["page_number"],
                    "evidence_id": page["evidence_id"],
                    "spatial_id": spatial.spatial_id,
                    "preferred_method": page["method"],
                    "fact_count": len(facts),
                    "anchor_count": page_anchor_count,
                    "cross_line_anchor_count": page_cross_line_count,
                    "region_count": len(regions),
                    "component_count": len(grouping.components) if grouping else 0,
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

    ocr_attempted = sum(item["attempted"] for item in ocr_results.values())
    ocr_added = sum(item["added"] for item in ocr_results.values())
    ocr_failed = sum(item["failed"] for item in ocr_results.values())

    return {
        "schema": SCHEMA,
        "stage": "post_hoc_t19b_development_replay_not_validation",
        "frozen_blind_reference": {
            "run_id": 32497051480,
            "artifact_id": 9452336639,
            "artifact_digest": "sha256:4033ea05fbd122504e0dadf005f200ae32e30f646d086cfdfb2399b0bbb36320",
            "selection_signature_sha256": EXPECTED_SELECTED_SIGNATURE,
            "source_artifact_map_signature_sha256": map_signature,
        },
        "representation": {
            "anchor_method": SPATIAL_TEXT_ANCHOR_METHOD,
            "grouping_method": LOCAL_GROUPING_METHOD,
            "parser_version": PARSER_VERSION,
        },
        "extraction": {
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
            "tesseract_version": tesseract_version,
        },
        "result": {
            "page_count": aggregate["page_count"],
            "money_bearing_page_count": aggregate["money_bearing_page_count"],
            "page_parser_money_fact_count": aggregate["page_parser_money_fact_count"],
            "anchored_money_fact_count": aggregate["anchored_money_fact_count"],
            "anchor_failure_count": sum(anchor_failures.values()),
            "cross_line_anchor_count": aggregate["cross_line_anchor_count"],
            "same_line_anchor_count": aggregate["same_line_anchor_count"],
            "spatial_money_region_count": aggregate["spatial_money_region_count"],
            "grouped_page_count": aggregate["grouped_page_count"],
            "component_count": aggregate["component_count"],
            "component_size_counts": dict(sorted(component_sizes.items())),
            "nearest_directed_edge_count": aggregate["nearest_directed_edge_count"],
            "mutual_nearest_directed_edge_count": aggregate["mutual_nearest_directed_edge_count"],
            "unsupported_preferred_method_page_count": aggregate["unsupported_preferred_method_page_count"],
            "anchor_failure_reasons": dict(sorted(anchor_failures.items())),
        },
        "page_results": page_results,
        "semantic_boundary": {
            "table_semantics_assigned": False,
            "field_semantics_assigned": False,
            "financial_semantics_authorized": False,
            "event_identity_assigned": False,
            "independence_assessed": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "This replay uses opened T19b evidence and is not out-of-sample validation.",
            "Anchored proximity components are geometry, not financial or event semantics.",
            "A positive T19b replay cannot authorize the repair without untouched validation.",
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

    result = evaluate(
        Path(args.state_dir),
        selection_sync=json.loads(Path(args.selection_sync).read_text(encoding="utf-8")),
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
