#!/usr/bin/env python3
"""Profile bounded local-layout relationships on the frozen T17 spatial evidence.

R1.T18 consumes a freshly regenerated T17 spatial profile. It measures geometry
between already-preserved spatial regions without assigning table, field,
financial, transaction, event, anomaly, or lead semantics.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import median

from proofline.local_layout import (
    LOCAL_LAYOUT_METHOD,
    region_from_word_indices,
    relation_between_regions,
)
from proofline.spatial_text import SpatialPageResult, SpatialWord
from proofline.structured import extract_structured_facts

SCHEMA = "proofline-akron-t18-local-layout-profile/v1"
T17_PROFILE_SCHEMA = "proofline-akron-t17-spatial-text-profile/v1"
T17_SUMMARY_SCHEMA = "proofline-akron-t17-spatial-text-summary/v1"
PARSER_VERSION = "proofline-structured/v3"
EXPECTED_SELECTION_SIGNATURE = "b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966"
EXPECTED_MAP_SIGNATURE = "797f8986110664bf23019536a3c9721c7e283cd81b730e3eb867459b34848edf"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _page_from_dict(data: dict) -> SpatialPageResult:
    words = tuple(
        SpatialWord(
            order_index=int(word["order_index"]),
            text=str(word["text"]),
            bbox=tuple(float(part) for part in word["bbox"]),
            block_index=int(word["block_index"]),
            line_index=int(word["line_index"]),
            word_index=int(word["word_index"]),
        )
        for word in data.get("words") or []
    )
    return SpatialPageResult(
        spatial_id=str(data["spatial_id"]),
        evidence_id=str(data["evidence_id"]),
        artifact_id=str(data["artifact_id"]),
        page_number=int(data["page_number"]),
        page_bbox=tuple(float(part) for part in data["page_bbox"]),
        source_text_method=str(data["source_text_method"]),
        spatial_method=str(data["spatial_method"]),
        software_version=str(data["software_version"]),
        model_version=data.get("model_version"),
        source_text_sha256=str(data["source_text_sha256"]),
        source_text_quality=float(data["source_text_quality"]),
        word_signature_sha256=str(data["word_signature_sha256"]),
        words=words,
    )


def _validate_t17(profile: dict, summary: dict) -> None:
    if profile.get("schema") != T17_PROFILE_SCHEMA:
        raise ValueError("unexpected T17 spatial profile schema")
    if summary.get("schema") != T17_SUMMARY_SCHEMA:
        raise ValueError("unexpected frozen T17 summary schema")
    if profile.get("stage") != "post_hoc_common_spatial_text_capability_probe_on_opened_t13b_t14":
        raise ValueError("T18 input is not the frozen T17 stage")

    sample = profile.get("sample") or {}
    frozen_sample = summary.get("sample") or {}
    if sample.get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T18 T17 selection signature changed")
    if sample.get("source_artifact_mapping_signature_sha256") != EXPECTED_MAP_SIGNATURE:
        raise ValueError("T18 T17 Bronze map signature changed")
    for key, expected in (
        ("source_identity_count", 32),
        ("unique_artifact_count", 28),
        ("exact_source_to_bronze_match_count", 32),
        ("bronze_byte_identity_drift_count", 0),
    ):
        if sample.get(key) != expected or frozen_sample.get(key) != expected:
            raise ValueError(f"T18 frozen sample continuity changed for {key}")

    contract = profile.get("spatial_contract") or {}
    frozen_contract = summary.get("spatial_contract") or {}
    for key, expected in (
        ("target_spatial_page_count", 7),
        ("native_target_page_count", 1),
        ("ocr_target_page_count", 6),
        ("total_word_count", 929),
        ("total_line_count", 370),
    ):
        if contract.get(key) != expected or frozen_contract.get(key) != expected:
            raise ValueError(f"T18 frozen T17 spatial count changed for {key}")

    audit = profile.get("post_hoc_t14_characterization") or {}
    frozen_audit = summary.get("post_hoc_t14_characterization") or {}
    if audit.get("fee_schedule_complete_geometry_count") != 6:
        raise ValueError("T18 lost complete T17 fee geometry")
    if audit.get("fee_schedule_x_band_separable_count") != 0:
        raise ValueError("T18 motivation changed: T17 x-band result is no longer negative")
    if frozen_audit.get("fee_schedule_complete_geometry_count") != 6:
        raise ValueError("frozen T17 fee geometry summary changed")
    if frozen_audit.get("fee_schedule_x_band_separable_count") != 0:
        raise ValueError("frozen T17 x-band summary changed")

    assessment = audit.get("assessment") or {}
    if assessment.get("target_money_match_count") != 1:
        raise ValueError("T18 frozen assessment target money count changed")
    if assessment.get("cash_assessed_label_match_count") != 1:
        raise ValueError("T18 frozen assessment label count changed")
    if assessment.get("same_line_label_value_pair_exists") is not False:
        raise ValueError("T18 motivation changed: T17 line-identity result is no longer negative")

    decision = summary.get("stage_decision") or {}
    if decision.get("common_native_and_ocr_spatial_geometry_is_viable_evidence_infrastructure") is not True:
        raise ValueError("T18 lost T17 spatial-infrastructure decision")
    if decision.get("simple_global_x_band_separation_sufficient_for_fee_schedule_failure_population") is not False:
        raise ValueError("T18 lost T17 x-band rejection")
    if decision.get("pymupdf_line_identity_sufficient_for_cash_assessed_relationship") is not False:
        raise ValueError("T18 lost T17 line-identity rejection")


def _line_text_and_ranges(line) -> tuple[str, list[tuple[int, int, SpatialWord]]]:
    text = ""
    ranges: list[tuple[int, int, SpatialWord]] = []
    for word in line.words:
        if text:
            text += " "
        start = len(text)
        text += word.text
        ranges.append((start, len(text), word))
    return text, ranges


def _money_observations(page: SpatialPageResult) -> list[dict]:
    observations: list[dict] = []
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
            observations.append(
                {
                    "raw_text": fact.raw_text,
                    "normalized_text": str(fact.normalized_text),
                    "word_order_indices": [word.order_index for word in overlapping],
                    "block_index": line.block_index,
                    "line_index": line.line_index,
                    "line_text": line_text,
                }
            )
    observations.sort(
        key=lambda item: (
            item["block_index"],
            item["line_index"],
            item["word_order_indices"],
            item["raw_text"],
        )
    )
    return observations


def _normalize_word(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _phrase_regions(page: SpatialPageResult, phrase: tuple[str, ...]):
    targets = tuple(_normalize_word(part) for part in phrase)
    regions = []
    for line in page.lines():
        words = list(line.words)
        normalized = [_normalize_word(word.text) for word in words]
        for start in range(0, len(words) - len(targets) + 1):
            if tuple(normalized[start : start + len(targets)]) != targets:
                continue
            selected = words[start : start + len(targets)]
            regions.append(region_from_word_indices(page, [word.order_index for word in selected]))
    regions.sort(key=lambda region: (region.word_order_indices, region.region_id))
    return regions


def _distance_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None}
    ordered = sorted(float(value) for value in values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 6),
        "median": round(float(median(ordered)), 6),
        "max": round(ordered[-1], 6),
    }


def _target_regions(page: SpatialPageResult, artifact_result: dict) -> list[dict]:
    by_region: dict[str, dict] = {}
    for audit_class, field in (
        ("supported", "supported_matches"),
        ("contradicted", "contradicted_matches"),
    ):
        for token, observations in sorted((artifact_result.get(field) or {}).items()):
            for observation in observations or []:
                region = region_from_word_indices(page, observation["word_order_indices"])
                record = by_region.setdefault(
                    region.region_id,
                    {
                        "region": region,
                        "audit_classes": set(),
                        "tokens": set(),
                        "normalized_values": set(),
                        "raw_texts": set(),
                    },
                )
                record["audit_classes"].add(audit_class)
                record["tokens"].add(token)
                record["normalized_values"].add(str(observation["normalized_text"]))
                record["raw_texts"].add(str(observation["raw_text"]))

    results: list[dict] = []
    for region_id in sorted(by_region):
        record = by_region[region_id]
        classes = sorted(record["audit_classes"])
        results.append(
            {
                "region": record["region"],
                "audit_class": classes[0] if len(classes) == 1 else "mixed",
                "audit_classes": classes,
                "tokens": sorted(record["tokens"]),
                "normalized_values": sorted(record["normalized_values"]),
                "raw_texts": sorted(record["raw_texts"]),
            }
        )
    results.sort(key=lambda item: (item["region"].word_order_indices, item["region"].region_id))
    return results


def _fee_artifact_characterization(page: SpatialPageResult, artifact_result: dict) -> dict:
    targets = _target_regions(page, artifact_result)
    target_results: list[dict] = []
    same_class_count = 0
    comparable_count = 0

    for target in targets:
        peers: list[tuple[object, dict]] = []
        for peer in targets:
            if peer["region"].region_id == target["region"].region_id:
                continue
            relation = relation_between_regions(page, target["region"], peer["region"])
            peers.append((relation, peer))
        peers.sort(
            key=lambda item: (
                item[0].normalized_center_distance_page_diagonal,
                abs(item[0].reading_order_delta),
                item[1]["region"].word_order_indices,
                item[1]["region"].region_id,
            )
        )

        nearest = None
        nearest_same_class = None
        if peers:
            relation, peer = peers[0]
            nearest = {
                "peer_region_id": peer["region"].region_id,
                "peer_audit_class": peer["audit_class"],
                "peer_tokens": peer["tokens"],
                "relation": relation.to_dict(),
            }
            if target["audit_class"] != "mixed" and peer["audit_class"] != "mixed":
                comparable_count += 1
                nearest_same_class = target["audit_class"] == peer["audit_class"]
                if nearest_same_class:
                    same_class_count += 1

        target_results.append(
            {
                "region": target["region"].to_dict(),
                "audit_class": target["audit_class"],
                "audit_classes": target["audit_classes"],
                "tokens": target["tokens"],
                "normalized_values": target["normalized_values"],
                "raw_texts": target["raw_texts"],
                "nearest_target_peer": nearest,
                "nearest_target_peer_same_audit_class": nearest_same_class,
            }
        )

    distance_buckets: dict[str, list[float]] = defaultdict(list)
    pair_relations: list[dict] = []
    for left_index, left in enumerate(targets):
        for right in targets[left_index + 1 :]:
            relation = relation_between_regions(page, left["region"], right["region"])
            if left["audit_class"] == "mixed" or right["audit_class"] == "mixed":
                bucket = "mixed"
            elif left["audit_class"] == right["audit_class"]:
                bucket = f"within_{left['audit_class']}"
            else:
                bucket = "cross_class"
            distance_buckets[bucket].append(relation.normalized_center_distance_page_diagonal)
            pair_relations.append(
                {
                    "left_region_id": left["region"].region_id,
                    "right_region_id": right["region"].region_id,
                    "left_audit_class": left["audit_class"],
                    "right_audit_class": right["audit_class"],
                    "distance_bucket": bucket,
                    "relation": relation.to_dict(),
                }
            )

    return {
        "artifact_id": artifact_result["artifact_id"],
        "page_number": artifact_result["page_number"],
        "evidence_id": page.evidence_id,
        "spatial_id": page.spatial_id,
        "target_region_count": len(targets),
        "supported_target_region_count": sum(item["audit_class"] == "supported" for item in targets),
        "contradicted_target_region_count": sum(item["audit_class"] == "contradicted" for item in targets),
        "mixed_target_region_count": sum(item["audit_class"] == "mixed" for item in targets),
        "nearest_peer_comparable_count": comparable_count,
        "nearest_peer_same_audit_class_count": same_class_count,
        "nearest_peer_same_audit_class_rate": (
            round(same_class_count / comparable_count, 6) if comparable_count else None
        ),
        "pair_distance_summaries": {
            key: _distance_summary(distance_buckets.get(key, []))
            for key in ("within_supported", "within_contradicted", "cross_class", "mixed")
        },
        "target_regions": target_results,
        "pair_relations": pair_relations,
    }


def _fee_characterization(profile: dict, pages: dict[str, SpatialPageResult]) -> list[dict]:
    groups = (profile.get("post_hoc_t14_characterization") or {}).get("fee_schedule_groups") or []
    if len(groups) != 6:
        raise ValueError("T18 expects the six frozen T17 fee groups")
    results: list[dict] = []
    for group in groups:
        artifact_results = []
        for artifact_result in group.get("artifact_results") or []:
            spatial_id = artifact_result["spatial_id"]
            page = pages.get(spatial_id)
            if page is None:
                raise ValueError(f"T18 missing frozen spatial page: {spatial_id}")
            artifact_results.append(_fee_artifact_characterization(page, artifact_result))
        results.append(
            {
                "source_name": group["source_name"],
                "target_locator": group["target_locator"],
                "artifact_results": artifact_results,
                "target_region_count": sum(item["target_region_count"] for item in artifact_results),
                "nearest_peer_comparable_count": sum(
                    item["nearest_peer_comparable_count"] for item in artifact_results
                ),
                "nearest_peer_same_audit_class_count": sum(
                    item["nearest_peer_same_audit_class_count"] for item in artifact_results
                ),
            }
        )
    return results


def _assessment_characterization(profile: dict, pages: dict[str, SpatialPageResult]) -> dict:
    assessment = (profile.get("post_hoc_t14_characterization") or {}).get("assessment") or {}
    spatial_id = assessment.get("spatial_id")
    page = pages.get(spatial_id)
    if page is None:
        raise ValueError(f"T18 missing assessment spatial page: {spatial_id}")

    labels = _phrase_regions(page, ("cash", "assessed"))
    money = _money_observations(page)
    if len(labels) != 1:
        raise ValueError(f"T18 expected one frozen CASH ASSESSED region, found {len(labels)}")
    target_value = str(assessment["target_normalized_value"])

    candidates_by_region: dict[str, dict] = {}
    for observation in money:
        region = region_from_word_indices(page, observation["word_order_indices"])
        record = candidates_by_region.setdefault(
            region.region_id,
            {
                "region": region,
                "normalized_values": set(),
                "raw_texts": set(),
            },
        )
        record["normalized_values"].add(observation["normalized_text"])
        record["raw_texts"].add(str(observation["raw_text"]))

    label = labels[0]
    candidates: list[dict] = []
    for region_id in sorted(candidates_by_region):
        record = candidates_by_region[region_id]
        relation = relation_between_regions(page, label, record["region"])
        candidates.append(
            {
                "region": record["region"],
                "normalized_values": sorted(record["normalized_values"]),
                "raw_texts": sorted(record["raw_texts"]),
                "relation": relation,
            }
        )
    candidates.sort(
        key=lambda item: (
            item["relation"].normalized_center_distance_page_diagonal,
            abs(item["relation"].reading_order_delta),
            item["region"].word_order_indices,
            item["region"].region_id,
        )
    )

    target_candidates = [
        item for item in candidates if target_value in item["normalized_values"]
    ]
    if len(target_candidates) != 1:
        raise ValueError(f"T18 expected one frozen target money region, found {len(target_candidates)}")
    target = target_candidates[0]
    target_rank = candidates.index(target) + 1

    return {
        "artifact_id": page.artifact_id,
        "page_number": page.page_number,
        "evidence_id": page.evidence_id,
        "spatial_id": page.spatial_id,
        "label_region": label.to_dict(),
        "target_normalized_value": target_value,
        "money_candidate_region_count": len(candidates),
        "target_money_distance_rank": target_rank,
        "target_is_nearest_money_region": target_rank == 1,
        "target_relation": target["relation"].to_dict(),
        "money_candidates_by_distance": [
            {
                "rank": rank,
                "region": item["region"].to_dict(),
                "normalized_values": item["normalized_values"],
                "raw_texts": item["raw_texts"],
                "is_frozen_target": target_value in item["normalized_values"],
                "relation": item["relation"].to_dict(),
            }
            for rank, item in enumerate(candidates, start=1)
        ],
    }


def build_profile(profile: dict, summary: dict) -> dict:
    _validate_t17(profile, summary)
    pages = {
        page.spatial_id: page
        for page in (_page_from_dict(data) for data in profile.get("spatial_pages") or [])
    }
    if len(pages) != 7:
        raise ValueError(f"T18 expected seven unique T17 spatial pages, found {len(pages)}")

    fee_groups = _fee_characterization(profile, pages)
    assessment = _assessment_characterization(profile, pages)
    fee_comparable = sum(item["nearest_peer_comparable_count"] for item in fee_groups)
    fee_same = sum(item["nearest_peer_same_audit_class_count"] for item in fee_groups)

    sample = profile["sample"]
    return {
        "schema": SCHEMA,
        "stage": "post_hoc_bounded_local_layout_capability_probe_on_opened_t13b_t14",
        "sample": {
            "source_identity_count": sample["source_identity_count"],
            "unique_artifact_count": sample["unique_artifact_count"],
            "selection_signature_sha256": sample["selection_signature_sha256"],
            "source_artifact_mapping_signature_sha256": sample[
                "source_artifact_mapping_signature_sha256"
            ],
            "exact_source_to_bronze_match_count": sample["exact_source_to_bronze_match_count"],
            "bronze_byte_identity_drift_count": sample["bronze_byte_identity_drift_count"],
            "status": "already_opened_t13b_t14_development_data_not_new_holdout",
        },
        "local_layout_contract": {
            "method": LOCAL_LAYOUT_METHOD,
            "input_spatial_page_count": len(pages),
            "canonical_silver_changed": False,
            "sqlite_storage_changed": False,
            "search_changed": False,
            "structured_index_changed": False,
            "table_semantics_assigned": False,
            "field_semantics_assigned": False,
            "financial_semantics_changed": False,
            "event_identity_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "post_hoc_t14_characterization": {
            "ground_truth_status": (profile.get("post_hoc_t14_characterization") or {}).get(
                "ground_truth_status"
            ),
            "fee_schedule_group_count": len(fee_groups),
            "fee_target_region_count": sum(item["target_region_count"] for item in fee_groups),
            "fee_nearest_peer_comparable_count": fee_comparable,
            "fee_nearest_peer_same_audit_class_count": fee_same,
            "fee_nearest_peer_same_audit_class_rate": (
                round(fee_same / fee_comparable, 6) if fee_comparable else None
            ),
            "fee_schedule_groups": fee_groups,
            "assessment": assessment,
        },
        "stage_decision": {
            "detector_authorized": False,
            "financial_semantics_authorized": False,
            "event_identity_assigned": False,
            "lead_count": None,
            "next_boundary": None,
        },
        "non_claims": [
            "T18 is post-hoc characterization on already-opened T13b/T14 development evidence, not a new holdout or accuracy estimate.",
            "The supported/contradicted labels are inherited only from the frozen T14 contextual audit and are not emitted by a detector.",
            "Nearest-neighbor class agreement is a descriptive geometric measurement, not proof of table, field, or financial-role semantics.",
            "Assessment money-distance rank is local geometric evidence, not authorization of a generic key-value or financial detector.",
            "No table, row, column, field, financial role, transaction, event, anomaly, conflict, suspiciousness, wrongdoing, or lead conclusion is authorized.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spatial-profile", required=True)
    parser.add_argument("--t17-summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = build_profile(_load(args.spatial_profile), _load(args.t17_summary))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
