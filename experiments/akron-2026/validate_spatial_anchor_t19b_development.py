#!/usr/bin/env python3
"""Outcome-neutral validator for the T20 source-span-v2 T19b development replay."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path


EVALUATION_SCHEMA = "proofline-akron-t20-spatial-anchor-t19b-development/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t19-frozen-attachment-sync/v1"
EXPECTED_SELECTION_SIGNATURE = "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"
EXPECTED_MAP_SIGNATURE = "8e4bedc043544c701d2c2e6fee5dcb1fcda92d2322fbd98a5bba7b01f0a5c14d"
EXPECTED_ANCHOR_METHOD = "proofline-spatial-text-anchor/source-span-v2"
EXPECTED_GROUPING_METHOD = "proofline-local-grouping/nearest-components-v1"
EXPECTED_PARSER_VERSION = "proofline-structured/v3"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _punctuation_only_or_empty(text: str) -> bool:
    return all(unicodedata.category(char).startswith("P") for char in text)


def validate(evaluation: dict, selection_sync: dict) -> dict:
    if evaluation.get("schema") != EVALUATION_SCHEMA:
        raise ValueError("unexpected T20 T19b development replay schema")
    if evaluation.get("stage") != "post_hoc_t19b_development_replay_not_validation":
        raise ValueError("T20 v2 replay lost its post-hoc non-validation boundary")
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T19b selection-sync schema")

    selection = selection_sync.get("selection") or {}
    if selection.get("selected_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T20 v2 replay selection no longer matches frozen ranks 65-96")
    if len(selection_sync.get("selected_sources") or []) != 32:
        raise ValueError("T20 v2 replay must contain exactly 32 opened T19b source identities")

    blind = evaluation.get("frozen_blind_reference") or {}
    if blind.get("run_id") != 32497051480 or blind.get("artifact_id") != 9452336639:
        raise ValueError("T20 v2 replay lost the frozen T19b blind-run reference")
    if blind.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T20 v2 replay blind selection signature changed")
    if blind.get("source_artifact_map_signature_sha256") != EXPECTED_MAP_SIGNATURE:
        raise ValueError("T20 v2 replay does not reproduce exact T19b source->artifact bytes")

    representation = evaluation.get("representation") or {}
    if representation.get("anchor_method") != EXPECTED_ANCHOR_METHOD:
        raise ValueError("unexpected T20 source-span-v2 method")
    if representation.get("grouping_method") != EXPECTED_GROUPING_METHOD:
        raise ValueError("T20 v2 replay changed frozen grouping v1")
    if representation.get("parser_version") != EXPECTED_PARSER_VERSION:
        raise ValueError("T20 v2 replay parser version changed")

    result = evaluation.get("result") or {}
    integer_fields = (
        "page_count",
        "money_bearing_page_count",
        "page_parser_money_fact_count",
        "anchored_money_fact_count",
        "anchor_failure_count",
        "cross_line_anchor_count",
        "same_line_anchor_count",
        "spatial_money_region_count",
        "grouped_page_count",
        "component_count",
        "nearest_directed_edge_count",
        "mutual_nearest_directed_edge_count",
        "unsupported_preferred_method_page_count",
    )
    for key in integer_fields:
        value = result.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"T20 v2 replay has invalid count for {key}: {value!r}")

    if result["anchored_money_fact_count"] + result["anchor_failure_count"] != result["page_parser_money_fact_count"]:
        raise ValueError("T20 v2 anchor accounting does not partition page-parser facts")
    if result["cross_line_anchor_count"] + result["same_line_anchor_count"] != result["anchored_money_fact_count"]:
        raise ValueError("T20 v2 line-crossing accounting does not partition successful anchors")
    if result["grouped_page_count"] > result["money_bearing_page_count"]:
        raise ValueError("T20 v2 grouped more pages than contain parser money facts")
    if result["mutual_nearest_directed_edge_count"] > result["nearest_directed_edge_count"]:
        raise ValueError("T20 v2 mutual-nearest edge count exceeds nearest-edge count")

    component_size_counts = result.get("component_size_counts") or {}
    if sum(int(count) for count in component_size_counts.values()) != result["component_count"]:
        raise ValueError("T20 v2 component-size counts do not reproduce component count")
    for size, count in component_size_counts.items():
        if int(size) < 1 or not isinstance(count, int) or count < 0:
            raise ValueError(f"invalid T20 v2 component-size count: {size!r}={count!r}")

    pages = evaluation.get("page_results") or []
    if len(pages) != result["money_bearing_page_count"]:
        raise ValueError("T20 v2 page-results count does not equal money-bearing page count")

    totals = {
        "facts": 0,
        "anchors": 0,
        "cross_line": 0,
        "regions": 0,
        "components": 0,
        "expanded": 0,
    }
    boundary_punctuation: dict[str, int] = {}

    for page in pages:
        fact_count = int(page.get("fact_count") or 0)
        anchor_count = int(page.get("anchor_count") or 0)
        failures = page.get("anchor_failures") or []
        if anchor_count + len(failures) != fact_count:
            raise ValueError("T20 v2 page anchor accounting is inconsistent")

        totals["facts"] += fact_count
        totals["anchors"] += anchor_count
        totals["cross_line"] += int(page.get("cross_line_anchor_count") or 0)
        totals["regions"] += int(page.get("region_count") or 0)
        totals["components"] += int(page.get("component_count") or 0)

        spatial_id = page.get("spatial_id")
        evidence_id = page.get("evidence_id")
        for item in page.get("regions") or []:
            region = item.get("region") or {}
            if region.get("spatial_id") != spatial_id or region.get("evidence_id") != evidence_id:
                raise ValueError("T20 v2 region lineage does not match page")
            for observation in item.get("observations") or []:
                anchor = observation.get("anchor") or {}
                if anchor.get("spatial_id") != spatial_id or anchor.get("evidence_id") != evidence_id:
                    raise ValueError("T20 v2 anchor lineage does not match page")
                if anchor.get("method") != EXPECTED_ANCHOR_METHOD:
                    raise ValueError("T20 v2 observation used unexpected anchor method")

                leading = str(anchor.get("leading_boundary_punctuation") or "")
                trailing = str(anchor.get("trailing_boundary_punctuation") or "")
                expanded = anchor.get("expanded_to_word_boundary")
                if not _punctuation_only_or_empty(leading) or not _punctuation_only_or_empty(trailing):
                    raise ValueError("T20 v2 anchor boundary expansion contains non-punctuation")
                if expanded is not bool(leading or trailing):
                    raise ValueError("T20 v2 anchor expansion flag is inconsistent")
                if expanded:
                    totals["expanded"] += 1
                    for char in leading + trailing:
                        boundary_punctuation[char] = boundary_punctuation.get(char, 0) + 1

        grouping = page.get("grouping")
        if grouping is not None:
            if grouping.get("method") != EXPECTED_GROUPING_METHOD:
                raise ValueError("T20 v2 page grouping changed frozen v1")
            if grouping.get("spatial_id") != spatial_id or grouping.get("evidence_id") != evidence_id:
                raise ValueError("T20 v2 grouping lineage does not match page")

    if totals["facts"] != result["page_parser_money_fact_count"]:
        raise ValueError("T20 v2 page facts do not reproduce aggregate count")
    if totals["anchors"] != result["anchored_money_fact_count"]:
        raise ValueError("T20 v2 page anchors do not reproduce aggregate count")
    if totals["cross_line"] != result["cross_line_anchor_count"]:
        raise ValueError("T20 v2 cross-line anchors do not reproduce aggregate count")
    if totals["regions"] != result["spatial_money_region_count"]:
        raise ValueError("T20 v2 page regions do not reproduce aggregate count")
    if totals["components"] != result["component_count"]:
        raise ValueError("T20 v2 page components do not reproduce aggregate count")

    semantic = evaluation.get("semantic_boundary") or {}
    for key in (
        "table_semantics_assigned",
        "field_semantics_assigned",
        "financial_semantics_authorized",
        "event_identity_assigned",
        "independence_assessed",
        "detector_authorized",
    ):
        if semantic.get(key) is not False:
            raise ValueError(f"T20 v2 semantic boundary changed for {key}")
    if semantic.get("lead_count") is not None:
        raise ValueError("T20 v2 replay emitted lead authority")

    return {
        "schema": "proofline-akron-t20-spatial-anchor-v2-t19b-development-summary/v1",
        "stage": evaluation["stage"],
        "outcome_neutral_validation": True,
        "selection_signature_sha256": EXPECTED_SELECTION_SIGNATURE,
        "source_artifact_map_signature_sha256": EXPECTED_MAP_SIGNATURE,
        "anchor_method": EXPECTED_ANCHOR_METHOD,
        "grouping_method": EXPECTED_GROUPING_METHOD,
        "boundary_expanded_anchor_count": totals["expanded"],
        "boundary_punctuation_counts": dict(sorted(boundary_punctuation.items())),
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
