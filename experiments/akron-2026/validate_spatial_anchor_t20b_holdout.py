#!/usr/bin/env python3
"""Outcome-neutral validator for the blind R1.T20b ranks 97-128 machine result."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

EVALUATION_SCHEMA = "proofline-akron-t20b-spatial-anchor-holdout/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t20-frozen-attachment-sync/v1"
EXPECTED_SELECTION_SIGNATURE = "2977671e9680305dfde595d13c77ca31197613eae0c1813f6d7a0b2218938bf3"
EXPECTED_ANCHOR_METHOD = "proofline-spatial-text-anchor/source-span-v2"
EXPECTED_GROUPING_METHOD = "proofline-local-grouping/nearest-components-v1"
EXPECTED_PARSER_VERSION = "proofline-structured/v3"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _punctuation_only_or_empty(text: str) -> bool:
    return all(unicodedata.category(char).startswith("P") for char in text)


def validate(evaluation: dict, selection_sync: dict) -> dict:
    if evaluation.get("schema") != EVALUATION_SCHEMA:
        raise ValueError("unexpected T20b holdout evaluation schema")
    if evaluation.get("stage") != "blind_t20b_holdout_machine_output_before_contextual_audit":
        raise ValueError("T20b lost its blind pre-contextual-audit stage marker")
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T20b selection-sync schema")

    selection = selection_sync.get("selection") or {}
    if selection.get("selected_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T20b selection no longer matches frozen ranks 97-128")
    if selection.get("original_selected_ranks") != [97, 128]:
        raise ValueError("T20b selected rank boundary changed")
    if len(selection_sync.get("selected_sources") or []) != 32:
        raise ValueError("T20b requires exactly 32 selected source identities")

    frozen = evaluation.get("frozen_inputs") or {}
    if frozen.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T20b evaluation selection signature changed")
    if frozen.get("anchor_method") != EXPECTED_ANCHOR_METHOD:
        raise ValueError("T20b evaluation changed source-span-v2")
    if frozen.get("grouping_method") != EXPECTED_GROUPING_METHOD:
        raise ValueError("T20b evaluation changed local-grouping-v1")
    if frozen.get("parser_version") != EXPECTED_PARSER_VERSION:
        raise ValueError("T20b evaluation changed parser v3")
    if frozen.get("quality_floor") != 0.7 or frozen.get("default_ocr_language") != "eng" or frozen.get("default_ocr_dpi") != 200:
        raise ValueError("T20b extraction settings changed")

    sample = evaluation.get("sample") or {}
    if sample.get("selected_source_identity_count") != 32:
        raise ValueError("T20b sample source count changed")
    unique_artifacts = sample.get("unique_artifact_count")
    if not isinstance(unique_artifacts, int) or not 1 <= unique_artifacts <= 32:
        raise ValueError("T20b unique artifact count is invalid")

    result = evaluation.get("result") or {}
    integer_fields = (
        "money_bearing_page_count",
        "page_parser_money_fact_count",
        "spatialized_money_bearing_page_count",
        "anchored_money_fact_count",
        "anchor_failure_count",
        "unattempted_money_fact_count",
        "low_quality_unattempted_fact_count",
        "unsupported_method_unattempted_fact_count",
        "cross_line_anchor_count",
        "same_line_anchor_count",
        "boundary_expanded_anchor_count",
        "spatial_money_region_count",
        "unsupported_preferred_method_page_count",
        "overlapping_region_page_count",
        "overlapping_region_word_count",
        "grouping_failure_page_count",
        "grouped_page_count",
        "component_count",
        "nearest_directed_edge_count",
        "mutual_nearest_directed_edge_count",
    )
    for key in integer_fields:
        value = result.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"T20b result has invalid count for {key}: {value!r}")

    if result["anchored_money_fact_count"] + result["anchor_failure_count"] + result["unattempted_money_fact_count"] != result["page_parser_money_fact_count"]:
        raise ValueError("T20b fact accounting does not partition parser money facts")
    if result["cross_line_anchor_count"] + result["same_line_anchor_count"] != result["anchored_money_fact_count"]:
        raise ValueError("T20b line-crossing accounting does not partition successful anchors")
    if result["low_quality_unattempted_fact_count"] + result["unsupported_method_unattempted_fact_count"] != result["unattempted_money_fact_count"]:
        raise ValueError("T20b unattempted-fact reasons do not reproduce unattempted count")
    if result["grouped_page_count"] > result["spatialized_money_bearing_page_count"]:
        raise ValueError("T20b grouped more pages than it spatialized")
    if result["mutual_nearest_directed_edge_count"] > result["nearest_directed_edge_count"]:
        raise ValueError("T20b mutual-nearest count exceeds nearest-edge count")

    component_size_counts = result.get("component_size_counts") or {}
    measured_components = 0
    for size, count in component_size_counts.items():
        try:
            numeric_size = int(size)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid T20b component-size key: {size!r}") from exc
        if numeric_size < 1 or not isinstance(count, int) or count < 0:
            raise ValueError(f"invalid T20b component-size count: {size!r}={count!r}")
        measured_components += count
    if measured_components != result["component_count"]:
        raise ValueError("T20b component-size counts do not reproduce component count")

    boundary_counts = result.get("boundary_punctuation_counts") or {}
    for chars, count in boundary_counts.items():
        if not isinstance(chars, str) or len(chars) != 1 or not _punctuation_only_or_empty(chars):
            raise ValueError(f"T20b boundary punctuation key is invalid: {chars!r}")
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"T20b boundary punctuation count is invalid: {chars!r}={count!r}")
    if sum(boundary_counts.values()) < result["boundary_expanded_anchor_count"]:
        raise ValueError("T20b boundary punctuation counts cannot cover expanded anchors")

    pages = evaluation.get("page_results") or []
    if len(pages) != result["money_bearing_page_count"]:
        raise ValueError("T20b page-results count does not equal money-bearing page count")

    totals = {
        "facts": 0,
        "anchors": 0,
        "failures": 0,
        "unattempted": 0,
        "cross_line": 0,
        "expanded": 0,
        "regions": 0,
        "components": 0,
    }
    topology = []

    for page in pages:
        fact_count = int(page.get("fact_count") or 0)
        anchor_count = int(page.get("anchor_count") or 0)
        failure_count = int(page.get("anchor_failure_count") or 0)
        unattempted = int(page.get("unattempted_fact_count") or 0)
        if anchor_count + failure_count + unattempted != fact_count:
            raise ValueError("T20b page fact accounting is inconsistent")

        totals["facts"] += fact_count
        totals["anchors"] += anchor_count
        totals["failures"] += failure_count
        totals["unattempted"] += unattempted
        totals["cross_line"] += int(page.get("cross_line_anchor_count") or 0)
        totals["expanded"] += int(page.get("boundary_expanded_anchor_count") or 0)
        totals["regions"] += int(page.get("region_count") or 0)
        totals["components"] += int(page.get("component_count") or 0)

        status = page.get("status")
        if status in {"below_quality_floor_after_progressive_ocr", "unsupported_preferred_extraction_method"}:
            if unattempted != fact_count or anchor_count or failure_count:
                raise ValueError("T20b unattempted page has inconsistent anchor accounting")
            continue

        spatial_id = page.get("spatial_id")
        evidence_id = page.get("evidence_id")
        observation_count = 0
        for item in page.get("regions") or []:
            region = item.get("region") or {}
            if region.get("spatial_id") != spatial_id or region.get("evidence_id") != evidence_id:
                raise ValueError("T20b region lineage does not match page")
            for observation in item.get("observations") or []:
                observation_count += 1
                anchor = observation.get("anchor") or {}
                if anchor.get("spatial_id") != spatial_id or anchor.get("evidence_id") != evidence_id:
                    raise ValueError("T20b anchor lineage does not match page")
                if anchor.get("method") != EXPECTED_ANCHOR_METHOD:
                    raise ValueError("T20b observation used unexpected anchor method")
                if anchor.get("source_text_sha256") != page.get("source_text_sha256"):
                    raise ValueError("T20b anchor source-text lineage does not match page")
                leading = str(anchor.get("leading_boundary_punctuation") or "")
                trailing = str(anchor.get("trailing_boundary_punctuation") or "")
                if not _punctuation_only_or_empty(leading) or not _punctuation_only_or_empty(trailing):
                    raise ValueError("T20b anchor boundary expansion contains non-punctuation")
                if anchor.get("expanded_to_word_boundary") is not bool(leading or trailing):
                    raise ValueError("T20b anchor expansion flag is inconsistent")
        if observation_count != anchor_count:
            raise ValueError("T20b page observations do not reproduce anchor count")

        grouping = page.get("grouping")
        if grouping is not None:
            if grouping.get("method") != EXPECTED_GROUPING_METHOD:
                raise ValueError("T20b page grouping changed frozen v1")
            if grouping.get("spatial_id") != spatial_id or grouping.get("evidence_id") != evidence_id:
                raise ValueError("T20b grouping lineage does not match page")
            topology.append(
                {
                    "evidence_id": evidence_id,
                    "components": [
                        sorted(component.get("region_ids") or [])
                        for component in grouping.get("components") or []
                    ],
                }
            )

        overlap = page.get("overlapping_word_order_indices") or []
        if status == "overlapping_regions_not_grouped" and (not overlap or grouping is not None):
            raise ValueError("T20b overlap outcome is internally inconsistent")
        if status == "grouped" and grouping is None:
            raise ValueError("T20b grouped status lacks grouping evidence")

    if totals["facts"] != result["page_parser_money_fact_count"]:
        raise ValueError("T20b page facts do not reproduce aggregate count")
    if totals["anchors"] != result["anchored_money_fact_count"]:
        raise ValueError("T20b page anchors do not reproduce aggregate count")
    if totals["failures"] != result["anchor_failure_count"]:
        raise ValueError("T20b page failures do not reproduce aggregate count")
    if totals["unattempted"] != result["unattempted_money_fact_count"]:
        raise ValueError("T20b page unattempted facts do not reproduce aggregate count")
    if totals["cross_line"] != result["cross_line_anchor_count"]:
        raise ValueError("T20b page cross-line anchors do not reproduce aggregate count")
    if totals["expanded"] != result["boundary_expanded_anchor_count"]:
        raise ValueError("T20b page boundary expansions do not reproduce aggregate count")
    if totals["regions"] != result["spatial_money_region_count"]:
        raise ValueError("T20b page regions do not reproduce aggregate count")
    if totals["components"] != result["component_count"]:
        raise ValueError("T20b page components do not reproduce aggregate count")

    boundary = evaluation.get("semantic_boundary") or {}
    if boundary.get("contextual_audit_performed") is not False:
        raise ValueError("T20b contextual audit occurred before raw machine freeze")
    for key in (
        "table_semantics_assigned",
        "field_semantics_assigned",
        "financial_semantics_authorized",
        "event_identity_assigned",
        "independence_assessed",
        "detector_authorized",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"T20b semantic boundary changed for {key}")
    if boundary.get("lead_count") is not None:
        raise ValueError("T20b emitted lead authority")

    return {
        "schema": "proofline-akron-t20b-spatial-anchor-holdout-summary/v1",
        "stage": evaluation["stage"],
        "outcome_neutral_validation": True,
        "selection_signature_sha256": EXPECTED_SELECTION_SIGNATURE,
        "anchor_method": EXPECTED_ANCHOR_METHOD,
        "grouping_method": EXPECTED_GROUPING_METHOD,
        "evaluation_sha256": _canonical_sha256(evaluation),
        "topology_signature_sha256": _canonical_sha256(topology),
        "sample": sample,
        "extraction": evaluation.get("extraction") or {},
        "result": result,
        "detector_authorized": False,
        "lead_count": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--summary-out", required=True)
    args = parser.parse_args()

    summary = validate(_load(args.evaluation), _load(args.selection_sync))
    destination = Path(args.summary_out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
