#!/usr/bin/env python3
"""Profile spatial word geometry on the already-opened T13b/T14 target pages.

R1.T17 is a post-hoc development probe. It preserves one common word-geometry
contract across native and OCR extraction without changing canonical Silver,
search, StructuredIndex, or financial semantics.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from proofline.hashing import evidence_id_from_locator, source_id_from_uri
from proofline.spatial_text import (
    SpatialLine,
    SpatialPageResult,
    extract_native_spatial_page,
    extract_ocr_spatial_page,
)
from proofline.storage import ProoflineStore
from proofline.structured import extract_structured_facts
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-t17-spatial-text-profile/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t13b-frozen-attachment-sync/v1"
AUDIT_SCHEMA = "proofline-akron-t14-known-amount-type-audit/v1"
T16_SCHEMA = "proofline-akron-t16-native-pdf-structure-summary/v1"
MAP_SCHEMA = "proofline-akron-t13b-source-artifact-map/v1"
PARSER_VERSION = "proofline-structured/v3"
EXPECTED_SELECTION_SIGNATURE = "b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966"
EXPECTED_MAP_SIGNATURE = "797f8986110664bf23019536a3c9721c7e283cd81b730e3eb867459b34848edf"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _artifact_metadata(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT artifact_id, sha256, media_type, byte_size, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"missing artifact metadata: {artifact_id}")
    return dict(row)


def _require_page_evidence(store: ProoflineStore, artifact_id: str, page_number: int) -> str:
    locator = f"page:{page_number}"
    evidence_id = evidence_id_from_locator(artifact_id, "page", locator)
    with store.connection() as connection:
        row = connection.execute(
            "SELECT evidence_id, artifact_id, unit_type, locator FROM evidence_units WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"missing canonical page evidence for {artifact_id} {locator}")
    if row["artifact_id"] != artifact_id or row["unit_type"] != "page" or row["locator"] != locator:
        raise RuntimeError(f"page evidence identity mismatch: {dict(row)}")
    return evidence_id


def _token_value(token: str) -> str:
    facts = [
        fact
        for fact in extract_structured_facts(token, parser_version=PARSER_VERSION)
        if fact.fact_type == "money" and fact.normalized_text is not None
    ]
    if len(facts) != 1:
        raise ValueError(f"money token does not resolve to exactly one v3 value: {token!r} -> {facts}")
    return str(facts[0].normalized_text)


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _line_text_and_ranges(line: SpatialLine) -> tuple[str, list[tuple[int, int, object]]]:
    text = ""
    ranges: list[tuple[int, int, object]] = []
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
        facts = extract_structured_facts(line_text, parser_version=PARSER_VERSION)
        for fact in facts:
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
            box = _union_bbox([word.bbox for word in overlapping])
            observations.append(
                {
                    "raw_text": fact.raw_text,
                    "normalized_text": fact.normalized_text,
                    "bbox": list(box),
                    "x_center": round((box[0] + box[2]) / 2.0, 3),
                    "y_center": round((box[1] + box[3]) / 2.0, 3),
                    "block_index": line.block_index,
                    "line_index": line.line_index,
                    "line_text": line_text,
                    "word_order_indices": [word.order_index for word in overlapping],
                }
            )
    observations.sort(
        key=lambda item: (
            item["block_index"],
            item["line_index"],
            item["bbox"][1],
            item["bbox"][0],
            item["raw_text"],
        )
    )
    return observations


def _normalize_word(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _phrase_matches(page: SpatialPageResult, phrase: tuple[str, ...]) -> list[dict]:
    targets = tuple(_normalize_word(part) for part in phrase)
    matches: list[dict] = []
    for line in page.lines():
        words = list(line.words)
        normalized = [_normalize_word(word.text) for word in words]
        for start in range(0, len(words) - len(targets) + 1):
            if tuple(normalized[start : start + len(targets)]) != targets:
                continue
            selected = words[start : start + len(targets)]
            box = _union_bbox([word.bbox for word in selected])
            matches.append(
                {
                    "phrase": " ".join(phrase),
                    "bbox": list(box),
                    "x_center": round((box[0] + box[2]) / 2.0, 3),
                    "y_center": round((box[1] + box[3]) / 2.0, 3),
                    "block_index": line.block_index,
                    "line_index": line.line_index,
                    "word_order_indices": [word.order_index for word in selected],
                    "line_text": line.text,
                }
            )
    return matches


def _distance(a: dict, b: dict) -> float:
    return round(math.hypot(float(a["x_center"]) - float(b["x_center"]), float(a["y_center"]) - float(b["y_center"])), 3)


def _validate_inputs(selection_sync: dict, audit: dict, t16: dict, source_map: dict) -> None:
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T13b selection-sync schema")
    if audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("unexpected T14 audit schema")
    if t16.get("schema") != T16_SCHEMA:
        raise ValueError("unexpected T16 summary schema")
    if source_map.get("schema") != MAP_SCHEMA:
        raise ValueError("unexpected T13b source-artifact map schema")
    if selection_sync.get("selection", {}).get("selected_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T17 no longer uses the frozen T13b selected population")
    if source_map.get("mapping_signature_sha256") != EXPECTED_MAP_SIGNATURE:
        raise ValueError("T17 source-artifact map signature changed")
    if source_map.get("source_count") != 32 or source_map.get("unique_artifact_count") != 28:
        raise ValueError("T17 frozen Bronze population changed")
    if t16.get("sample", {}).get("selection_signature_sha256") != EXPECTED_SELECTION_SIGNATURE:
        raise ValueError("T17 T16 provenance boundary changed")
    decision = t16.get("stage_decision") or {}
    if decision.get("native_table_detection_sufficient_for_t14_failure_population") is not False:
        raise ValueError("T17 motivation no longer preserves the T16 negative result")


def _verify_bronze_continuity(
    state_dir: Path,
    *,
    selection_sync: dict,
    source_map: dict,
) -> tuple[list[dict], dict[str, list[dict]]]:
    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    frozen = source_map["source_artifacts"]
    records: list[dict] = []
    by_name: dict[str, list[dict]] = defaultdict(list)
    for selected in selection_sync.get("selected_sources") or []:
        source_uri = selected["source_uri"]
        source_hash = selected["source_uri_sha256"]
        artifact_id = watcher.latest_successful_artifact(source_id_from_uri(source_uri))
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id_from_uri(source_uri))
        if artifact_id is None:
            raise RuntimeError(f"T17 selected source has no successful Bronze artifact: {source_uri}")
        expected = frozen.get(source_hash)
        if expected != artifact_id:
            raise RuntimeError(
                f"T17 Bronze byte identity drift for {source_hash}: expected {expected}, got {artifact_id}"
            )
        record = {
            "source_uri": source_uri,
            "source_uri_sha256": source_hash,
            "source_name": selected.get("source_name"),
            "artifact_id": artifact_id,
        }
        records.append(record)
        if isinstance(record["source_name"], str):
            by_name[record["source_name"]].append(record)
    if len(records) != 32:
        raise RuntimeError(f"T17 expected 32 exact source mappings, got {len(records)}")
    return records, by_name


def _extract_target_page(
    state_dir: Path,
    *,
    artifact_id: str,
    page_number: int,
    method: str,
    language: str,
    dpi: int,
) -> SpatialPageResult:
    store = ProoflineStore(state_dir / "proofline.db")
    metadata = _artifact_metadata(store, artifact_id)
    if metadata.get("media_type") != "application/pdf":
        raise RuntimeError(f"T17 target artifact is not PDF: {artifact_id}")
    path = state_dir / metadata["stored_path"]
    evidence_id = _require_page_evidence(store, artifact_id, page_number)
    if method == "ocr":
        return extract_ocr_spatial_page(
            path,
            artifact_id=artifact_id,
            evidence_id=evidence_id,
            page_number=page_number,
            language=language,
            dpi=dpi,
        )
    if method == "native":
        return extract_native_spatial_page(
            path,
            artifact_id=artifact_id,
            evidence_id=evidence_id,
            page_number=page_number,
        )
    raise ValueError(f"unsupported target extraction method: {method}")


def _fee_characterization(
    state_dir: Path,
    *,
    audit: dict,
    t16: dict,
    source_records_by_name: dict[str, list[dict]],
    language: str,
    dpi: int,
    spatial_pages: dict[tuple[str, int, str], SpatialPageResult],
) -> list[dict]:
    groups = (audit.get("fee_schedule_audit") or {}).get("groups") or []
    locators = (
        t16.get("post_hoc_t14_characterization", {})
        .get("fee_schedule_target_extraction", {})
        .get("target_page_locators_in_group_order")
        or []
    )
    if len(groups) != 6 or len(locators) != 6:
        raise ValueError("T17 expects the six frozen T14 fee groups and T16 target locators")

    bad = audit.get("new_numeric_integrity_observation") or {}
    bad_source = bad.get("source_name")
    bad_token = bad.get("frozen_v2_raw_text")

    results: list[dict] = []
    for group, locator in zip(groups, locators, strict=True):
        source_name = group["source_name"]
        if not isinstance(locator, str) or not locator.startswith("page:"):
            raise ValueError(f"invalid frozen fee target locator: {locator!r}")
        page_number = int(locator.split(":", 1)[1])
        supported_tokens = list(group.get("supported_filing_fee_tokens") or [])
        contradicted_tokens = list(group.get("contradicted_threshold_or_range_tokens_mislabeled_filing_fee") or [])
        removed_tokens: list[str] = []
        if source_name == bad_source and bad_token in contradicted_tokens:
            contradicted_tokens.remove(bad_token)
            removed_tokens.append(str(bad_token))

        supported_values = {token: _token_value(token) for token in supported_tokens}
        contradicted_values = {token: _token_value(token) for token in contradicted_tokens}
        records = source_records_by_name.get(source_name) or []
        artifact_ids = sorted({record["artifact_id"] for record in records})
        if not artifact_ids:
            raise RuntimeError(f"T17 lost frozen fee source mapping: {source_name}")

        artifact_results: list[dict] = []
        for artifact_id in artifact_ids:
            key = (artifact_id, page_number, "ocr")
            page = spatial_pages.get(key)
            if page is None:
                page = _extract_target_page(
                    state_dir,
                    artifact_id=artifact_id,
                    page_number=page_number,
                    method="ocr",
                    language=language,
                    dpi=dpi,
                )
                spatial_pages[key] = page
            observations = _money_observations(page)

            supported_matches = {
                token: [item for item in observations if item["normalized_text"] == value]
                for token, value in supported_values.items()
            }
            contradicted_matches = {
                token: [item for item in observations if item["normalized_text"] == value]
                for token, value in contradicted_values.items()
            }
            supported_centers = [
                float(item["x_center"])
                for matches in supported_matches.values()
                for item in matches
            ]
            contradicted_centers = [
                float(item["x_center"])
                for matches in contradicted_matches.values()
                for item in matches
            ]
            complete = all(supported_matches.values()) and all(contradicted_matches.values())
            orientation = None
            gap = None
            if complete and supported_centers and contradicted_centers:
                if min(supported_centers) > max(contradicted_centers):
                    orientation = "supported_fees_right_of_thresholds"
                    gap = round(min(supported_centers) - max(contradicted_centers), 3)
                elif max(supported_centers) < min(contradicted_centers):
                    orientation = "supported_fees_left_of_thresholds"
                    gap = round(min(contradicted_centers) - max(supported_centers), 3)

            artifact_results.append(
                {
                    "artifact_id": artifact_id,
                    "page_number": page_number,
                    "evidence_id": page.evidence_id,
                    "spatial_id": page.spatial_id,
                    "source_text_method": page.source_text_method,
                    "spatial_method": page.spatial_method,
                    "source_text_quality": page.source_text_quality,
                    "word_count": len(page.words),
                    "line_count": len(page.lines()),
                    "money_observation_count": len(observations),
                    "supported_matches": supported_matches,
                    "contradicted_matches": contradicted_matches,
                    "complete_expected_value_coverage": complete,
                    "x_band_orientation": orientation,
                    "x_band_gap_points": gap,
                    "x_band_separable": orientation is not None,
                }
            )

        results.append(
            {
                "source_name": source_name,
                "target_locator": locator,
                "matching_source_identity_count": len(records),
                "matching_unique_artifact_count": len(artifact_ids),
                "supported_tokens_after_t15": supported_tokens,
                "contradicted_tokens_after_t15": contradicted_tokens,
                "tokens_removed_as_t15_numeric_integrity_issue": removed_tokens,
                "artifact_results": artifact_results,
                "any_complete_expected_value_coverage": any(
                    item["complete_expected_value_coverage"] for item in artifact_results
                ),
                "any_x_band_separable": any(item["x_band_separable"] for item in artifact_results),
            }
        )
    return results


def _assessment_characterization(
    state_dir: Path,
    *,
    audit: dict,
    t16: dict,
    language: str,
    dpi: int,
    spatial_pages: dict[tuple[str, int, str], SpatialPageResult],
) -> dict:
    assessment_audit = audit.get("assessment_audit") or {}
    t16_assessment = (t16.get("post_hoc_t14_characterization") or {}).get("assessment_counterexample") or {}
    artifact_id = t16_assessment.get("artifact_id")
    locator = t16_assessment.get("locator")
    if not isinstance(artifact_id, str) or not isinstance(locator, str) or not locator.startswith("page:"):
        raise ValueError("T17 lost the frozen T16 assessment target")
    page_number = int(locator.split(":", 1)[1])
    key = (artifact_id, page_number, "native")
    page = spatial_pages.get(key)
    if page is None:
        page = _extract_target_page(
            state_dir,
            artifact_id=artifact_id,
            page_number=page_number,
            method="native",
            language=language,
            dpi=dpi,
        )
        spatial_pages[key] = page

    target_value = _token_value(str(assessment_audit["raw_text"]))
    money = [item for item in _money_observations(page) if item["normalized_text"] == target_value]
    labels = _phrase_matches(page, ("cash", "assessed"))
    pairs: list[dict] = []
    for label in labels:
        for amount in money:
            same_line = (
                label["block_index"] == amount["block_index"]
                and label["line_index"] == amount["line_index"]
            )
            horizontal_gap = round(float(amount["bbox"][0]) - float(label["bbox"][2]), 3)
            pairs.append(
                {
                    "label": label,
                    "amount": amount,
                    "same_line": same_line,
                    "label_left_of_amount": horizontal_gap >= 0,
                    "horizontal_gap_points": horizontal_gap,
                    "center_distance_points": _distance(label, amount),
                }
            )
    pairs.sort(
        key=lambda item: (
            not item["same_line"],
            item["center_distance_points"],
            abs(item["horizontal_gap_points"]),
        )
    )
    return {
        "artifact_id": artifact_id,
        "locator": locator,
        "evidence_id": page.evidence_id,
        "spatial_id": page.spatial_id,
        "source_text_method": page.source_text_method,
        "spatial_method": page.spatial_method,
        "source_text_quality": page.source_text_quality,
        "target_raw_text": assessment_audit["raw_text"],
        "target_normalized_value": target_value,
        "target_money_match_count": len(money),
        "cash_assessed_label_match_count": len(labels),
        "label_value_pairs": pairs,
        "same_line_label_value_pair_exists": any(item["same_line"] for item in pairs),
        "same_line_label_left_of_value_pair_exists": any(
            item["same_line"] and item["label_left_of_amount"] for item in pairs
        ),
    }


def build_profile(
    state_dir: Path,
    *,
    selection_sync: dict,
    audit: dict,
    t16: dict,
    source_map: dict,
    language: str,
    dpi: int,
) -> dict:
    _validate_inputs(selection_sync, audit, t16, source_map)
    source_records, source_records_by_name = _verify_bronze_continuity(
        state_dir,
        selection_sync=selection_sync,
        source_map=source_map,
    )
    spatial_pages: dict[tuple[str, int, str], SpatialPageResult] = {}
    fee_groups = _fee_characterization(
        state_dir,
        audit=audit,
        t16=t16,
        source_records_by_name=source_records_by_name,
        language=language,
        dpi=dpi,
        spatial_pages=spatial_pages,
    )
    assessment = _assessment_characterization(
        state_dir,
        audit=audit,
        t16=t16,
        language=language,
        dpi=dpi,
        spatial_pages=spatial_pages,
    )

    pages = [spatial_pages[key] for key in sorted(spatial_pages)]
    native_pages = [page for page in pages if page.source_text_method == "pymupdf_native_text"]
    ocr_pages = [page for page in pages if page.source_text_method == "pymupdf_tesseract_ocr"]

    return {
        "schema": SCHEMA,
        "stage": "post_hoc_common_spatial_text_capability_probe_on_opened_t13b_t14",
        "sample": {
            "source_identity_count": len(source_records),
            "unique_artifact_count": len(set(source_map["source_artifacts"].values())),
            "selection_signature_sha256": EXPECTED_SELECTION_SIGNATURE,
            "source_artifact_mapping_signature_sha256": EXPECTED_MAP_SIGNATURE,
            "exact_source_to_bronze_match_count": len(source_records),
            "bronze_byte_identity_drift_count": 0,
            "status": "already_opened_t13b_t14_development_data_not_new_holdout",
        },
        "spatial_contract": {
            "canonical_silver_changed": False,
            "sqlite_storage_changed": False,
            "search_changed": False,
            "structured_index_changed": False,
            "financial_semantics_changed": False,
            "event_identity_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
            "target_spatial_page_count": len(pages),
            "native_target_page_count": len(native_pages),
            "ocr_target_page_count": len(ocr_pages),
            "total_word_count": sum(len(page.words) for page in pages),
            "total_line_count": sum(len(page.lines()) for page in pages),
            "ocr_language": language,
            "ocr_dpi": dpi,
        },
        "post_hoc_t14_characterization": {
            "ground_truth_status": audit.get("ground_truth_status"),
            "fee_schedule_group_count": len(fee_groups),
            "fee_schedule_complete_geometry_count": sum(
                item["any_complete_expected_value_coverage"] for item in fee_groups
            ),
            "fee_schedule_x_band_separable_count": sum(
                item["any_x_band_separable"] for item in fee_groups
            ),
            "fee_schedule_groups": fee_groups,
            "assessment": assessment,
        },
        "spatial_pages": [page.to_dict() for page in pages],
        "non_claims": [
            "T17 reuses already-opened T13b/T14 development evidence and is not out-of-sample validation.",
            "Word geometry is extraction evidence, not trusted table, field, financial, transaction, event, anomaly, conflict, wrongdoing, or lead semantics.",
            "The fee x-band and assessment label/value measurements are post-hoc capability characterizations, not preregistered accuracy estimates.",
            "No spatial rows are written to canonical Proofline storage in T17.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--t16-summary", required=True)
    parser.add_argument("--source-artifact-map", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    profile = build_profile(
        Path(args.state_dir),
        selection_sync=_load(args.selection_sync),
        audit=_load(args.audit),
        t16=_load(args.t16_summary),
        source_map=_load(args.source_artifact_map),
        language=args.language,
        dpi=args.dpi,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
