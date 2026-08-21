#!/usr/bin/env python3
"""Validate the raw R1.T19 local-grouping holdout machine output."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

EVALUATION_SCHEMA = "proofline-akron-t19-local-grouping-holdout/v1"
SYNC_SCHEMA = "proofline-akron-t19-frozen-attachment-sync/v1"
GROUPING_METHOD = "proofline-local-grouping/nearest-components-v1"
SELECTED_SIGNATURE = "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _topology_signature(grouped_pages: list[dict]) -> str:
    payload = []
    for page in grouped_pages:
        grouping = page["grouping"]
        payload.append(
            {
                "artifact_id": page["artifact_id"],
                "evidence_id": page["evidence_id"],
                "spatial_id": page["spatial_contract"]["spatial_id"],
                "grouping_id": grouping["grouping_id"],
                "region_ids": grouping["region_ids"],
                "edges": [
                    [edge["source_region_id"], edge["target_region_id"], edge["relation_id"], edge["mutual_nearest"]]
                    for edge in grouping["nearest_edges"]
                ],
                "components": [component["region_ids"] for component in grouping["components"]],
            }
        )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate(root: Path, *, evaluation_path: Path, sync_path: Path) -> dict:
    evaluation = _load(evaluation_path)
    sync = _load(sync_path)

    if sync.get("schema") != SYNC_SCHEMA:
        raise ValueError("unexpected T19 holdout sync schema")
    selection = sync.get("selection") or {}
    if selection.get("selected_signature_sha256") != SELECTED_SIGNATURE:
        raise ValueError("T19 sync selection signature drifted")
    if selection.get("holdout_opened_by_this_execution") is not True:
        raise ValueError("T19 sync did not explicitly record the first holdout opening")
    if len(sync.get("selected_sources") or []) != 32:
        raise ValueError("T19 sync must contain exactly 32 selected source identities")

    if evaluation.get("schema") != EVALUATION_SCHEMA:
        raise ValueError("unexpected T19 grouping evaluation schema")
    if evaluation.get("stage") != "blind_structural_transfer_machine_output_before_contextual_audit":
        raise ValueError("T19 machine-output stage boundary changed")
    frozen = evaluation.get("frozen_inputs") or {}
    if frozen.get("selection_signature_sha256") != SELECTED_SIGNATURE:
        raise ValueError("T19 evaluation selection signature drifted")
    if frozen.get("grouping_method") != GROUPING_METHOD:
        raise ValueError("T19 frozen grouping method drifted")
    if frozen.get("parser_version") != "proofline-structured/v3":
        raise ValueError("T19 parser version drifted")

    sample = evaluation.get("sample") or {}
    if sample.get("selected_source_identity_count") != 32:
        raise ValueError("T19 evaluation lost selected source identities")
    if not isinstance(sample.get("unique_artifact_count"), int) or sample["unique_artifact_count"] < 1:
        raise ValueError("T19 evaluation emitted no unique artifacts")

    boundary = evaluation.get("semantic_boundary") or {}
    required_false = (
        "contextual_audit_performed",
        "table_semantics_assigned",
        "field_semantics_assigned",
        "financial_semantics_authorized",
        "event_identity_assigned",
        "independence_assessed",
        "detector_authorized",
    )
    for key in required_false:
        if boundary.get(key) is not False:
            raise ValueError(f"T19 semantic boundary changed: {key}={boundary.get(key)!r}")
    if boundary.get("lead_count") is not None:
        raise ValueError("T19 machine output emitted leads")

    grouped_pages = []
    recomputed = Counter()
    size_counts = Counter()
    for page in evaluation.get("page_results") or []:
        grouping = page.get("grouping")
        status = page.get("grouping_status")
        if status != "grouped":
            if grouping is not None:
                raise ValueError("non-grouped T19 page unexpectedly contains grouping output")
            continue
        if not isinstance(grouping, dict):
            raise ValueError("grouped T19 page lost grouping payload")
        grouped_pages.append(page)

        if grouping.get("method") != GROUPING_METHOD:
            raise ValueError("holdout grouping payload uses a non-frozen method")
        spatial = page.get("spatial_contract") or {}
        if grouping.get("spatial_id") != spatial.get("spatial_id"):
            raise ValueError("T19 grouping lost spatial lineage")
        if grouping.get("evidence_id") != page.get("evidence_id"):
            raise ValueError("T19 grouping lost evidence lineage")

        regions = page.get("spatial_money_regions") or []
        observed_region_ids = [item["region"]["region_id"] for item in regions]
        grouping_region_ids = list(grouping.get("region_ids") or [])
        if len(observed_region_ids) != len(set(observed_region_ids)):
            raise ValueError("T19 spatial money region IDs are not unique")
        if set(observed_region_ids) != set(grouping_region_ids):
            raise ValueError("T19 grouping does not cover exactly the emitted spatial money regions")

        n = len(grouping_region_ids)
        edges = grouping.get("nearest_edges") or []
        components = grouping.get("components") or []
        if n < 1:
            raise ValueError("grouped T19 page has zero regions")
        if n == 1 and edges:
            raise ValueError("T19 singleton grouping must not emit a nearest edge")
        if n > 1 and len(edges) != n:
            raise ValueError("T19 non-singleton grouping must emit one nearest edge per region")

        source_ids = [edge.get("source_region_id") for edge in edges]
        if n > 1 and set(source_ids) != set(grouping_region_ids):
            raise ValueError("T19 nearest-edge sources do not cover every grouped region exactly once")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("T19 grouping emits multiple nearest edges from one source region")
        for edge in edges:
            if edge.get("target_region_id") not in grouping_region_ids:
                raise ValueError("T19 nearest edge targets a region outside the grouping")
            if edge.get("source_region_id") == edge.get("target_region_id"):
                raise ValueError("T19 nearest edge self-targets")
            if not str(edge.get("edge_id") or "").startswith("layout-nearest-edge:"):
                raise ValueError("T19 nearest edge lost deterministic identity")

        component_members = []
        for component in components:
            members = list(component.get("region_ids") or [])
            if not members:
                raise ValueError("T19 emitted an empty component")
            if component.get("spatial_id") != spatial.get("spatial_id"):
                raise ValueError("T19 component lost spatial lineage")
            if component.get("evidence_id") != page.get("evidence_id"):
                raise ValueError("T19 component lost evidence lineage")
            if not str(component.get("component_id") or "").startswith("layout-component:"):
                raise ValueError("T19 component lost deterministic identity")
            component_members.extend(members)
            size_counts[str(len(members))] += 1
        if len(component_members) != len(set(component_members)):
            raise ValueError("T19 components overlap region membership")
        if set(component_members) != set(grouping_region_ids):
            raise ValueError("T19 components do not partition grouped regions")

        recomputed["grouped_page_count"] += 1
        recomputed["grouped_region_count"] += n
        recomputed["nearest_directed_edge_count"] += len(edges)
        recomputed["mutual_nearest_directed_edge_count"] += sum(bool(edge.get("mutual_nearest")) for edge in edges)
        recomputed["component_count"] += len(components)

    structural = evaluation.get("structural_result") or {}
    for key in (
        "grouped_page_count",
        "grouped_region_count",
        "nearest_directed_edge_count",
        "mutual_nearest_directed_edge_count",
        "component_count",
    ):
        if structural.get(key) != recomputed[key]:
            raise ValueError(f"T19 aggregate mismatch for {key}: {structural.get(key)} != {recomputed[key]}")
    if structural.get("component_size_counts") != dict(sorted(size_counts.items(), key=lambda item: int(item[0]))):
        raise ValueError("T19 component-size aggregate is inconsistent")

    return {
        "schema": "proofline-akron-t19-local-grouping-holdout-summary/v1",
        "selection_signature_sha256": SELECTED_SIGNATURE,
        "grouping_method": GROUPING_METHOD,
        "evaluation_sha256": _sha256_file(evaluation_path),
        "topology_signature_sha256": _topology_signature(grouped_pages),
        "selected_source_identity_count": sample["selected_source_identity_count"],
        "unique_artifact_count": sample["unique_artifact_count"],
        "structural_result": structural,
        "contextual_audit_performed": False,
        "detector_authorized": False,
        "lead_count": None,
        "outcome_neutral_validation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--summary-out", required=True)
    args = parser.parse_args()

    summary = validate(
        Path(args.root),
        evaluation_path=Path(args.evaluation),
        sync_path=Path(args.selection_sync),
    )
    destination = Path(args.summary_out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
