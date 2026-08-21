#!/usr/bin/env python3
"""Profile native PDF table geometry on the already-opened T13b source set.

R1.T16 is a post-hoc development probe. It does not alter canonical Silver, rerun
financial semantics as validation, or create detector/event/lead output.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from proofline.hashing import source_id_from_uri, stable_id
from proofline.pdf_structure import PdfTableStructure, probe_pdf_tables
from proofline.storage import ProoflineStore
from proofline.structured import extract_structured_facts
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-native-pdf-table-structure-profile/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t13b-frozen-attachment-sync/v1"
AUDIT_SCHEMA = "proofline-akron-t14-known-amount-type-audit/v1"
PARSER_VERSION = "proofline-structured/v3"


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


def _money_values(text: str) -> tuple[str, ...]:
    return tuple(
        fact.normalized_text
        for fact in extract_structured_facts(text, parser_version=PARSER_VERSION)
        if fact.fact_type == "money" and fact.normalized_text is not None
    )


def _token_value(token: str) -> str:
    values = _money_values(token)
    if len(values) != 1:
        raise ValueError(f"audit money token does not resolve to exactly one v3 value: {token!r} -> {values}")
    return values[0]


def _table_record(table: PdfTableStructure, *, artifact_id: str, method: str) -> dict:
    structure_id = stable_id(
        "pdf-table-structure",
        artifact_id,
        f"page:{table.page_number}",
        f"table:{table.table_index}",
        method,
    )
    cells = []
    for cell in table.cells:
        cells.append(
            {
                **cell.to_dict(),
                "money_values_v3": list(_money_values(cell.text)),
            }
        )
    return {
        "structure_id": structure_id,
        "page_number": table.page_number,
        "page_locator": f"page:{table.page_number}",
        "table_index": table.table_index,
        "bbox": list(table.bbox),
        "row_count": table.row_count,
        "column_count": table.column_count,
        "header_names": list(table.header_names),
        "header_external": table.header_external,
        "cells": cells,
    }


def _cell_matches(table: dict, value: str) -> list[dict]:
    return [cell for cell in table["cells"] if value in cell["money_values_v3"]]


def _fee_schedule_characterization(
    audit: dict,
    *,
    source_records_by_name: dict[str, list[dict]],
    artifact_profiles: dict[str, dict],
) -> list[dict]:
    numeric_observation = audit.get("new_numeric_integrity_observation") or {}
    removed_source_name = numeric_observation.get("source_name")
    removed_raw_text = numeric_observation.get("frozen_v2_raw_text")

    results = []
    for group in (audit.get("fee_schedule_audit") or {}).get("groups") or []:
        source_name = group["source_name"]
        supported_tokens = list(group.get("supported_filing_fee_tokens") or [])
        contradicted_tokens = list(group.get("contradicted_threshold_or_range_tokens_mislabeled_filing_fee") or [])

        removed_tokens = []
        if source_name == removed_source_name and removed_raw_text in contradicted_tokens:
            contradicted_tokens.remove(removed_raw_text)
            removed_tokens.append(removed_raw_text)

        supported = [(token, _token_value(token)) for token in supported_tokens]
        contradicted = [(token, _token_value(token)) for token in contradicted_tokens]
        source_records = source_records_by_name.get(source_name, [])
        artifact_ids = sorted({record["artifact_id"] for record in source_records})

        candidates = []
        for artifact_id in artifact_ids:
            profile = artifact_profiles[artifact_id]
            for table in profile["tables"]:
                supported_hits = {
                    token: _cell_matches(table, value)
                    for token, value in supported
                }
                contradicted_hits = {
                    token: _cell_matches(table, value)
                    for token, value in contradicted
                }
                found_supported = [token for token, hits in supported_hits.items() if hits]
                found_contradicted = [token for token, hits in contradicted_hits.items() if hits]
                supported_columns = sorted(
                    {
                        int(cell["column_index"])
                        for hits in supported_hits.values()
                        for cell in hits
                    }
                )
                contradicted_columns = sorted(
                    {
                        int(cell["column_index"])
                        for hits in contradicted_hits.values()
                        for cell in hits
                    }
                )
                expected_count = len(supported) + len(contradicted)
                found_count = len(found_supported) + len(found_contradicted)
                complete = found_count == expected_count
                distinct_columns = bool(supported_columns and contradicted_columns) and not (
                    set(supported_columns) & set(contradicted_columns)
                )
                candidates.append(
                    {
                        "artifact_id": artifact_id,
                        "structure_id": table["structure_id"],
                        "page_number": table["page_number"],
                        "table_index": table["table_index"],
                        "header_names": table["header_names"],
                        "expected_token_count": expected_count,
                        "found_token_count": found_count,
                        "found_supported_tokens": found_supported,
                        "found_contradicted_tokens": found_contradicted,
                        "missing_supported_tokens": [token for token, _ in supported if token not in found_supported],
                        "missing_contradicted_tokens": [token for token, _ in contradicted if token not in found_contradicted],
                        "supported_columns": supported_columns,
                        "contradicted_columns": contradicted_columns,
                        "complete_token_coverage": complete,
                        "column_sets_disjoint": distinct_columns,
                        "structurally_separable": complete and distinct_columns,
                    }
                )

        candidates.sort(
            key=lambda item: (
                -int(item["structurally_separable"]),
                -item["found_token_count"],
                item["artifact_id"],
                item["page_number"],
                item["table_index"],
            )
        )
        best = candidates[0] if candidates else None
        results.append(
            {
                "source_name": source_name,
                "matching_source_identity_count": len(source_records),
                "matching_unique_artifact_count": len(artifact_ids),
                "supported_tokens_after_t15": supported_tokens,
                "contradicted_tokens_after_t15": contradicted_tokens,
                "tokens_removed_as_t15_numeric_integrity_issue": removed_tokens,
                "candidate_table_count": len(candidates),
                "best_candidate": best,
                "structurally_separable": bool(best and best["structurally_separable"]),
            }
        )
    return results


def _assessment_characterization(audit: dict, artifact_profiles: dict[str, dict]) -> dict:
    assessment = audit.get("assessment_audit") or {}
    target_raw = assessment.get("raw_text")
    locator = assessment.get("locator") or ""
    if not isinstance(target_raw, str) or not target_raw:
        return {"target_raw_text": target_raw, "matches": [], "structurally_supports_cash_assessed": False}
    target_value = _token_value(target_raw)
    expected_page = None
    if isinstance(locator, str) and locator.startswith("page:"):
        expected_page = int(locator.split(":", 1)[1])

    matches = []
    for artifact_id, profile in sorted(artifact_profiles.items()):
        for table in profile["tables"]:
            if expected_page is not None and table["page_number"] != expected_page:
                continue
            for cell in _cell_matches(table, target_value):
                row_index = int(cell["row_index"])
                row_cells = [
                    item for item in table["cells"] if int(item["row_index"]) == row_index
                ]
                row_cells.sort(key=lambda item: int(item["column_index"]))
                row_text = " | ".join(item["text"] for item in row_cells)
                normalized_row = " ".join(row_text.casefold().split())
                matches.append(
                    {
                        "artifact_id": artifact_id,
                        "structure_id": table["structure_id"],
                        "page_number": table["page_number"],
                        "table_index": table["table_index"],
                        "row_index": row_index,
                        "column_index": cell["column_index"],
                        "cell_text": cell["text"],
                        "row_text": row_text,
                        "header_names": table["header_names"],
                        "same_row_contains_cash_assessed": "cash assessed" in normalized_row,
                    }
                )
    return {
        "target_raw_text": target_raw,
        "target_normalized_value": target_value,
        "expected_page": expected_page,
        "match_count": len(matches),
        "matches": matches,
        "structurally_supports_cash_assessed": any(
            item["same_row_contains_cash_assessed"] for item in matches
        ),
    }


def build_profile(state_dir: Path, *, selection_sync: dict, audit: dict) -> dict:
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T13b selection-sync schema")
    if audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("unexpected T14 audit schema")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != 32:
        raise ValueError("T16 must reuse exactly the 32 already-opened T13b source identities")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    sources_by_artifact: dict[str, list[dict]] = defaultdict(list)
    source_records_by_name: dict[str, list[dict]] = defaultdict(list)

    for selected in selected_sources:
        source_uri = selected["source_uri"]
        artifact_id = watcher.latest_successful_artifact(source_id_from_uri(source_uri))
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id_from_uri(source_uri))
        if artifact_id is None:
            raise RuntimeError(f"T16 selected source has no successful Bronze artifact: {source_uri}")
        record = {
            "source_uri": source_uri,
            "source_uri_sha256": selected["source_uri_sha256"],
            "source_name": selected.get("source_name"),
            "artifact_id": artifact_id,
        }
        sources_by_artifact[artifact_id].append(record)
        if isinstance(record["source_name"], str):
            source_records_by_name[record["source_name"]].append(record)

    artifact_profiles = {}
    for artifact_id in sorted(sources_by_artifact):
        metadata = _artifact_metadata(store, artifact_id)
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"T16 selected artifact is not PDF: {artifact_id} -> {metadata['media_type']}")
        artifact_path = state_dir / metadata["stored_path"]
        probe = probe_pdf_tables(artifact_path)
        tables = [
            _table_record(table, artifact_id=artifact_id, method=probe.method)
            for table in probe.tables
        ]
        artifact_profiles[artifact_id] = {
            "artifact": metadata,
            "sources": sorted(sources_by_artifact[artifact_id], key=lambda item: item["source_uri"]),
            "page_count": probe.page_count,
            "method": probe.method,
            "software_version": probe.software_version,
            "table_count": len(tables),
            "failure_count": len(probe.failures),
            "failures": [failure.to_dict() for failure in probe.failures],
            "tables": tables,
        }

    fee_groups = _fee_schedule_characterization(
        audit,
        source_records_by_name=source_records_by_name,
        artifact_profiles=artifact_profiles,
    )
    assessment = _assessment_characterization(audit, artifact_profiles)

    total_pages = sum(profile["page_count"] for profile in artifact_profiles.values())
    total_tables = sum(profile["table_count"] for profile in artifact_profiles.values())
    total_failures = sum(profile["failure_count"] for profile in artifact_profiles.values())
    pages_with_tables = {
        (artifact_id, table["page_number"])
        for artifact_id, profile in artifact_profiles.items()
        for table in profile["tables"]
    }
    total_cells = sum(
        len(table["cells"])
        for profile in artifact_profiles.values()
        for table in profile["tables"]
    )

    return {
        "schema": SCHEMA,
        "stage": "post_hoc_native_structure_capability_probe_on_opened_t13b",
        "canonical_silver_changed": False,
        "structured_index_changed": False,
        "financial_semantics_changed": False,
        "detector_authorized": False,
        "event_identity_assigned": False,
        "lead_count": None,
        "sample": {
            "source_identity_count": len(selected_sources),
            "unique_artifact_count": len(artifact_profiles),
            "selection_signature_sha256": selection_sync["selection"]["selected_signature_sha256"],
            "selection_status": "already_opened_t13b_development_data_not_new_holdout",
        },
        "native_structure": {
            "unique_artifact_page_count": total_pages,
            "pages_with_detected_tables": len(pages_with_tables),
            "detected_table_count": total_tables,
            "detected_cell_count": total_cells,
            "page_detection_failure_count": total_failures,
            "artifacts_with_any_table": sum(profile["table_count"] > 0 for profile in artifact_profiles.values()),
            "artifacts_with_no_table": sum(profile["table_count"] == 0 for profile in artifact_profiles.values()),
        },
        "post_hoc_t14_characterization": {
            "ground_truth_status": audit.get("ground_truth_status"),
            "fee_schedule_group_count": len(fee_groups),
            "fee_schedule_structurally_separable_count": sum(
                item["structurally_separable"] for item in fee_groups
            ),
            "fee_schedule_groups": fee_groups,
            "assessment": assessment,
        },
        "artifacts": [artifact_profiles[key] for key in sorted(artifact_profiles)],
        "non_claims": [
            "T16 uses already-opened T13b/T14 development evidence and is not out-of-sample validation.",
            "PyMuPDF table detection is layout evidence, not trusted semantic labeling.",
            "A detected table does not establish transaction identity, event independence, anomaly, conflict, wrongdoing, or lead status.",
            "A null native-table result is meaningful and may indicate scanned/OCR layout requires a different structural method.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    profile = build_profile(
        Path(args.state_dir),
        selection_sync=_load(args.selection_sync),
        audit=_load(args.audit),
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
