#!/usr/bin/env python3
"""Blind structural-transfer evaluation of frozen local-grouping v1 on R1.T19.

This is the first content-opening stage for frozen ranks 65-96. The evaluator
uses the unchanged T19 grouping method on all spatially recoverable current-v3
money observations in the selected PDFs. It emits geometry/topology only; no
contextual semantic audit is performed here.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from proofline.hashing import sha256_text, source_id_from_uri
from proofline.local_grouping import LOCAL_GROUPING_METHOD, nearest_neighbor_components
from proofline.local_layout import region_from_word_indices
from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.spatial_text import (
    extract_native_spatial_page,
    extract_ocr_spatial_page,
    parse_ocr_model_version,
)
from proofline.storage import ProoflineStore
from proofline.structured import extract_structured_facts
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-t19-local-grouping-holdout/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t19-frozen-attachment-sync/v1"
EXPECTED_SELECTED_SIGNATURE = "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"
EXPECTED_SOURCES = 32
PARSER_VERSION = "proofline-structured/v3"
PAGE_RE = re.compile(r"^page:(\d+)$")


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _tesseract_version() -> str | None:
    try:
        completed = subprocess.run(
            ["tesseract", "--version"], check=True, capture_output=True, text=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    lines = (completed.stdout or completed.stderr).splitlines()
    return lines[0].strip() if lines else None


def _artifact_metadata(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT artifact_id, sha256, media_type, byte_size, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"missing attachment artifact: {artifact_id}")
    return dict(row)


def _preferred_pages(store: ProoflineStore, artifact_id: str) -> list[dict]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT eu.evidence_id, eu.locator, best.method, best.extracted_text,
                   best.quality_score, best.software_version, best.model_version
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
    result = []
    for row in rows:
        match = PAGE_RE.fullmatch(str(row["locator"]))
        if match is None:
            raise RuntimeError(f"unexpected PDF page locator: {row['locator']!r}")
        result.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "locator": str(row["locator"]),
                "page_number": int(match.group(1)),
                "method": str(row["method"]),
                "text": row["extracted_text"] or "",
                "quality_score": float(row["quality_score"] or 0.0),
                "software_version": row["software_version"],
                "model_version": row["model_version"],
            }
        )
    return result


def _money_facts(text: str) -> list[dict]:
    facts = []
    for fact in extract_structured_facts(text, parser_version=PARSER_VERSION):
        if fact.fact_type != "money":
            continue
        facts.append(
            {
                "raw_text": fact.raw_text,
                "normalized_text": str(fact.normalized_text) if fact.normalized_text is not None else None,
                "char_start": fact.char_start,
                "char_end": fact.char_end,
            }
        )
    return facts


def _line_text_and_ranges(line) -> tuple[str, list[tuple[int, int, object]]]:
    text = ""
    ranges = []
    for word in line.words:
        if text:
            text += " "
        start = len(text)
        text += word.text
        ranges.append((start, len(text), word))
    return text, ranges


def _spatial_money_regions(page) -> tuple[list, list[dict]]:
    by_region = {}
    for line in page.lines():
        line_text, ranges = _line_text_and_ranges(line)
        for fact in extract_structured_facts(line_text, parser_version=PARSER_VERSION):
            if fact.fact_type != "money" or fact.normalized_text is None:
                continue
            if fact.char_start is None or fact.char_end is None:
                continue
            overlapping = [
                word
                for start, end, word in ranges
                if start < fact.char_end and end > fact.char_start
            ]
            if not overlapping:
                continue
            region = region_from_word_indices(page, [word.order_index for word in overlapping])
            record = by_region.setdefault(
                region.region_id,
                {
                    "region": region,
                    "observations": [],
                },
            )
            record["observations"].append(
                {
                    "raw_text": fact.raw_text,
                    "normalized_text": str(fact.normalized_text),
                    "block_index": line.block_index,
                    "line_index": line.line_index,
                    "line_text": line_text,
                    "word_order_indices": [word.order_index for word in overlapping],
                }
            )

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
                f"spatial money regions overlap word membership on {page.evidence_id}: {sorted(overlap)}"
            )
        covered.update(region.word_order_indices)

    serialized = [
        {
            "region": item["region"].to_dict(),
            "observations": item["observations"],
        }
        for item in ordered
    ]
    return regions, serialized


def _spatial_page(path: Path, page: dict, *, artifact_id: str):
    if page["method"] == "pymupdf_native_text":
        return extract_native_spatial_page(
            path,
            artifact_id=artifact_id,
            evidence_id=page["evidence_id"],
            page_number=page["page_number"],
        )
    if page["method"] == "pymupdf_tesseract_ocr":
        language, dpi = parse_ocr_model_version(page.get("model_version"))
        return extract_ocr_spatial_page(
            path,
            artifact_id=artifact_id,
            evidence_id=page["evidence_id"],
            page_number=page["page_number"],
            language=language,
            dpi=dpi,
        )
    return None


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
        raise ValueError("T19 holdout sync no longer matches frozen source identities")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != EXPECTED_SOURCES:
        raise ValueError("T19 holdout requires exactly 32 source identities")

    tesseract_version = _tesseract_version()
    if tesseract_version is None:
        raise RuntimeError("Tesseract is unavailable; T19 must preserve the existing OCR escalation path")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type="supporting_document_of")
    related_sources = {relation.source_uri for relation in relations}

    sources_by_artifact: dict[str, list[dict]] = defaultdict(list)
    metadata_by_artifact: dict[str, dict] = {}
    for selected in selected_sources:
        source_uri = str(selected["source_uri"])
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id) or store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"T19 selected source has no successful artifact: {source_uri}")
        if source_uri not in related_sources:
            raise RuntimeError(f"T19 selected source lost publisher-backed parent relation: {source_uri}")
        metadata = metadata_by_artifact.setdefault(artifact_id, _artifact_metadata(store, artifact_id))
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"T19 selected attachment is not PDF: {source_uri}")
        sources_by_artifact[artifact_id].append(
            {
                "source_uri": source_uri,
                "source_uri_sha256": selected["source_uri_sha256"],
                "source_name": selected.get("source_name"),
            }
        )

    for records in sources_by_artifact.values():
        records.sort(key=lambda item: item["source_uri_sha256"])

    extractor = ProgressiveExtractor(state_dir)
    backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
    native_profiles = {}
    ocr_results = {}
    for artifact_id in sorted(sources_by_artifact):
        pages = _preferred_pages(store, artifact_id)
        native_profiles[artifact_id] = pages
        if any(page["quality_score"] < threshold for page in pages):
            result = extractor.run_ocr(artifact_id, backend, threshold=threshold, force=False)
            ocr_results[artifact_id] = result.to_dict()

    page_results = []
    artifact_results = []
    aggregate = Counter()
    component_sizes = Counter()
    extraction_methods = Counter()

    for artifact_id in sorted(sources_by_artifact):
        metadata = metadata_by_artifact[artifact_id]
        path = state_dir / metadata["stored_path"]
        if not path.is_file():
            raise RuntimeError(f"stored attachment bytes are missing: {path}")
        pages = _preferred_pages(store, artifact_id)
        artifact_money_facts = 0
        artifact_grouped_pages = 0

        for page in pages:
            aggregate["page_count"] += 1
            extraction_methods[page["method"]] += 1
            page_facts = _money_facts(page["text"])
            if not page_facts:
                continue
            aggregate["money_bearing_page_count"] += 1
            aggregate["page_parser_money_fact_count"] += len(page_facts)
            artifact_money_facts += len(page_facts)

            result = {
                "artifact_id": artifact_id,
                "artifact_sha256": metadata["sha256"],
                "evidence_id": page["evidence_id"],
                "locator": page["locator"],
                "page_number": page["page_number"],
                "preferred_extraction": {
                    "method": page["method"],
                    "quality_score": page["quality_score"],
                    "software_version": page["software_version"],
                    "model_version": page["model_version"],
                    "text_sha256": sha256_text(page["text"]),
                },
                "page_parser_money_facts": page_facts,
                "page_parser_money_fact_count": len(page_facts),
                "grouping_status": None,
                "spatial_money_regions": [],
                "grouping": None,
            }

            if page["quality_score"] < threshold:
                aggregate["money_bearing_low_quality_page_count"] += 1
                result["grouping_status"] = "below_quality_floor_after_progressive_ocr"
                page_results.append(result)
                continue

            spatial = _spatial_page(path, page, artifact_id=artifact_id)
            if spatial is None:
                aggregate["unsupported_preferred_method_page_count"] += 1
                result["grouping_status"] = "unsupported_preferred_extraction_method"
                page_results.append(result)
                continue
            if spatial.source_text_sha256 != sha256_text(page["text"]):
                raise RuntimeError(
                    f"T19 spatial text drifted from preferred Silver for {page['evidence_id']}"
                )

            aggregate["spatialized_money_bearing_page_count"] += 1
            regions, region_records = _spatial_money_regions(spatial)
            aggregate["spatial_money_region_count"] += len(regions)
            result["spatial_contract"] = {
                "spatial_id": spatial.spatial_id,
                "spatial_method": spatial.spatial_method,
                "word_signature_sha256": spatial.word_signature_sha256,
                "word_count": len(spatial.words),
                "line_count": len(spatial.lines()),
            }
            result["spatial_money_regions"] = region_records
            result["spatial_money_region_count"] = len(regions)
            result["spatial_line_money_observation_count"] = sum(
                len(item["observations"]) for item in region_records
            )
            aggregate["spatial_line_money_observation_count"] += result["spatial_line_money_observation_count"]

            if not regions:
                aggregate["money_page_no_spatial_region_count"] += 1
                result["grouping_status"] = "no_spatial_money_region"
                page_results.append(result)
                continue

            grouping = nearest_neighbor_components(spatial, regions)
            if grouping.method != LOCAL_GROUPING_METHOD:
                raise RuntimeError("T19 grouping method drifted during holdout evaluation")
            serialized = grouping.to_dict()
            result["grouping_status"] = "grouped"
            result["grouping"] = serialized
            aggregate["grouped_page_count"] += 1
            aggregate["grouped_region_count"] += len(grouping.region_ids)
            aggregate["nearest_directed_edge_count"] += len(grouping.nearest_edges)
            aggregate["mutual_nearest_directed_edge_count"] += sum(
                edge.mutual_nearest for edge in grouping.nearest_edges
            )
            aggregate["component_count"] += len(grouping.components)
            for component in grouping.components:
                component_sizes[str(len(component.region_ids))] += 1
            artifact_grouped_pages += 1
            page_results.append(result)

        artifact_results.append(
            {
                "artifact_id": artifact_id,
                "artifact_sha256": metadata["sha256"],
                "source_uri_sha256s": [item["source_uri_sha256"] for item in sources_by_artifact[artifact_id]],
                "source_identity_count": len(sources_by_artifact[artifact_id]),
                "page_count": len(pages),
                "page_parser_money_fact_count": artifact_money_facts,
                "grouped_page_count": artifact_grouped_pages,
                "ocr": ocr_results.get(artifact_id),
            }
        )

    ocr_attempted = sum(item["attempted"] for item in ocr_results.values())
    ocr_added = sum(item["added"] for item in ocr_results.values())
    ocr_failed = sum(item["failed"] for item in ocr_results.values())

    aggregate.update(
        {
            "selected_source_identity_count": len(selected_sources),
            "unique_artifact_count": len(sources_by_artifact),
            "duplicate_artifact_group_count": sum(len(items) > 1 for items in sources_by_artifact.values()),
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
        }
    )

    return {
        "schema": SCHEMA,
        "stage": "blind_structural_transfer_machine_output_before_contextual_audit",
        "frozen_inputs": {
            "selection_signature_sha256": EXPECTED_SELECTED_SIGNATURE,
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
            "duplicate_artifact_group_count": aggregate["duplicate_artifact_group_count"],
        },
        "extraction": {
            "page_count": aggregate["page_count"],
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
            "preferred_method_counts": dict(sorted(extraction_methods.items())),
            "money_bearing_low_quality_page_count": aggregate["money_bearing_low_quality_page_count"],
        },
        "structural_result": {
            "money_bearing_page_count": aggregate["money_bearing_page_count"],
            "page_parser_money_fact_count": aggregate["page_parser_money_fact_count"],
            "spatialized_money_bearing_page_count": aggregate["spatialized_money_bearing_page_count"],
            "spatial_money_region_count": aggregate["spatial_money_region_count"],
            "spatial_line_money_observation_count": aggregate["spatial_line_money_observation_count"],
            "money_page_no_spatial_region_count": aggregate["money_page_no_spatial_region_count"],
            "unsupported_preferred_method_page_count": aggregate["unsupported_preferred_method_page_count"],
            "grouped_page_count": aggregate["grouped_page_count"],
            "grouped_region_count": aggregate["grouped_region_count"],
            "nearest_directed_edge_count": aggregate["nearest_directed_edge_count"],
            "mutual_nearest_directed_edge_count": aggregate["mutual_nearest_directed_edge_count"],
            "component_count": aggregate["component_count"],
            "component_size_counts": dict(sorted(component_sizes.items(), key=lambda item: int(item[0]))),
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
            "Nearest-neighbor components are geometric observations, not table rows, fields, transactions, or events.",
            "A component's size or distance does not imply anomaly, conflict, suspiciousness, wrongdoing, or financial meaning.",
            "No contextual interpretation was consulted to alter local-grouping-v1 in this run.",
            "Null, singleton, large-component, low-quality, and no-money outcomes remain part of the holdout result."
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
