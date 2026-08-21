#!/usr/bin/env python3
"""Validate a completed R1.T13b blind financial-representation artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SYNC_SCHEMA = "proofline-akron-t13b-frozen-attachment-sync/v1"
EVALUATION_SCHEMA = "proofline-akron-financial-representation-v2-oos-evaluation/v1"
SELECTION_SCHEMA = "proofline-akron-t13b-disjoint-source-set/v1"
EXPECTED_SOURCES = 32


def _load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path, *, frozen_path: Path, contract_path: Path) -> dict:
    frozen = _load(frozen_path)
    contract = _load(contract_path)
    discovery = _load(root / "discovery.json")
    sync = _load(root / "selection-sync.json")
    evaluation = _load(root / "representation-evaluation.json")
    rejections = _load(root / "rejections.json")

    if frozen.get("schema") != SELECTION_SCHEMA:
        raise ValueError("unexpected T13b corrected selection schema")
    correction = frozen.get("correction") or {}
    if correction.get("representation_applied_in_failed_run") is not False:
        raise ValueError("T13b lost failed-run no-representation provenance")

    expected_selected = frozen["selected"]["source_uri_sha256"]
    expected_excluded = frozen["excluded"]["source_uri_sha256"]
    if len(expected_selected) != EXPECTED_SOURCES or len(set(expected_selected)) != EXPECTED_SOURCES:
        raise ValueError("T13b selected set is not exactly 32 unique identities")
    if len(expected_excluded) != EXPECTED_SOURCES or len(set(expected_excluded)) != EXPECTED_SOURCES:
        raise ValueError("T13b development exclusion is not exactly 32 unique identities")
    if set(expected_selected) & set(expected_excluded):
        raise ValueError("T13b holdout overlaps development source identities")

    if sync.get("schema") != SYNC_SCHEMA:
        raise ValueError("unexpected T13b sync schema")
    if sync["selection"]["selected_source_hashes"] != expected_selected:
        raise ValueError("live T13b selection differs from corrected source identities")
    if sync["selection"]["excluded_source_hashes"] != expected_excluded:
        raise ValueError("live T13b development exclusion differs from corrected identities")
    if not str(sync["selection"].get("selection_basis") or "").startswith("sha256(source_uri) only"):
        raise ValueError("T13b selection was not identity-only")
    if sync["selection"].get("live_excluded_ranks") != list(range(1, 33)):
        raise ValueError("live T13b exclusion ranks do not reproduce 1-32")
    if sync["selection"].get("live_selected_ranks") != list(range(33, 65)):
        raise ValueError("live T13b selected ranks do not reproduce 33-64")

    counts = (sync.get("watch") or {}).get("counts") or {}
    if counts.get("new") != EXPECTED_SOURCES or counts.get("unavailable") != 0:
        raise ValueError(f"T13b exact attachment sync failed: {counts}")
    selected_sources = sync.get("selected_sources") or []
    if len(selected_sources) != EXPECTED_SOURCES:
        raise ValueError("T13b sync did not retain exactly 32 selected sources")
    if len({item["source_uri_sha256"] for item in selected_sources}) != EXPECTED_SOURCES:
        raise ValueError("T13b selected source identities are not unique")
    selected_uri_to_hash = {
        item["source_uri"]: item["source_uri_sha256"] for item in selected_sources
    }

    if evaluation.get("schema") != EVALUATION_SCHEMA:
        raise ValueError("unexpected T13b evaluation schema")
    if evaluation.get("execution_label") != "R1.T13b":
        raise ValueError("T13b evaluation lost its corrected execution label")
    if evaluation.get("stage") != "out_of_sample_representation_evaluation_only":
        raise ValueError("T13b crossed its representation-evaluation boundary")
    if evaluation.get("representation_assigned") is not True:
        raise ValueError("T13b did not apply frozen v2 representation")
    for key in ("detector_authorized", "event_identity_assigned", "independence_assessed"):
        if evaluation.get(key) is not False:
            raise ValueError(f"T13b improperly changed semantic boundary: {key}")
    if evaluation.get("lead_count") is not None:
        raise ValueError("T13b improperly emitted lead output")
    if evaluation["sample"]["attachment_count"] != EXPECTED_SOURCES:
        raise ValueError("T13b evaluated the wrong attachment source count")
    if evaluation["sample"]["selected_source_hashes"] != expected_selected:
        raise ValueError("T13b evaluated a different source set")
    if evaluation["sample"]["excluded_source_hashes"] != expected_excluded:
        raise ValueError("T13b lost its development exclusion boundary")

    attachment_artifact_ids = [item["artifact"]["artifact_id"] for item in evaluation["attachments"]]
    unique_artifact_count = len(set(attachment_artifact_ids))
    if evaluation["sample"]["unique_artifact_count"] != unique_artifact_count:
        raise ValueError("T13b unique Bronze artifact count is inconsistent")
    duplicate_groups = evaluation["sample"].get("duplicate_artifact_groups") or []
    if evaluation["sample"]["duplicate_artifact_group_count"] != len(duplicate_groups):
        raise ValueError("T13b duplicate Bronze group count is inconsistent")
    duplicate_excess = sum(group["source_count"] - 1 for group in duplicate_groups)
    if EXPECTED_SOURCES - unique_artifact_count != duplicate_excess:
        raise ValueError("T13b duplicate Bronze accounting is inconsistent")
    for group in duplicate_groups:
        if group["source_count"] != len(group["source_uris"]):
            raise ValueError("T13b duplicate group lost source identities")
        if len(group["source_uris"]) != len(group["source_uri_sha256s"]):
            raise ValueError("T13b duplicate group lost source hashes")
        for uri, digest in zip(group["source_uris"], group["source_uri_sha256s"]):
            if selected_uri_to_hash.get(uri) != digest:
                raise ValueError("T13b duplicate group contains non-selected provenance")

    if evaluation["structured_build"]["parser_version"] != "proofline-structured/v2":
        raise ValueError("T13b did not use structured parser v2")
    if evaluation["extraction"]["ocr_failed"] != 0:
        raise ValueError(f"T13b OCR failures: {evaluation['extraction']['ocr_failures']}")

    facts = evaluation.get("facts") or []
    if evaluation["money_fact_count"] != len(facts):
        raise ValueError("T13b money-fact count does not match emitted facts")
    for count_name in ("scope_counts", "context_type_counts", "amount_type_counts", "source_name_context_status_counts"):
        if sum(evaluation.get(count_name, {}).values()) != len(facts):
            raise ValueError(f"T13b {count_name} do not cover the fact population")

    allowed_scope = set(contract["allowed"]["scope"])
    allowed_context = set(contract["allowed"]["context_type"])
    allowed_amount = set(contract["allowed"]["amount_type"])
    context_rules = {rule["rule_id"]: rule["value"] for rule in contract["context_rules"]}
    amount_rules = {rule["rule_id"]: rule["value"] for rule in contract["amount_rules"]}
    defaults = contract["defaults"]
    empty_name_sha = hashlib.sha256(b"").hexdigest()

    low_quality_fact_count = 0
    fully_unknown = 0
    context_known_amount_unknown = 0
    amount_known = 0

    for fact in facts:
        if fact["scope"] not in allowed_scope:
            raise ValueError(f"T13b emitted unknown scope: {fact['scope']}")
        if fact["context_type"] not in allowed_context:
            raise ValueError(f"T13b emitted unknown context type: {fact['context_type']}")
        if fact["amount_type"] not in allowed_amount:
            raise ValueError(f"T13b emitted unknown amount type: {fact['amount_type']}")
        if float(fact["quality_score"] or 0.0) < 0.70:
            low_quality_fact_count += 1
        if len(fact.get("page_text_sha256") or "") != 64:
            raise ValueError("T13b fact lost preferred-page provenance")
        if len(fact.get("context_sha256") or "") != 64:
            raise ValueError("T13b fact lost local-context provenance")

        source_uris = fact.get("source_uris") or []
        source_hashes = fact.get("source_uri_sha256s") or []
        if not source_uris or len(source_uris) != len(source_hashes):
            raise ValueError("T13b fact lost publisher source provenance")
        for uri, digest in zip(source_uris, source_hashes):
            if selected_uri_to_hash.get(uri) != digest:
                raise ValueError("T13b fact contains non-selected source provenance")

        context_rule_id = fact.get("context_rule_id")
        if fact["context_type"] == defaults["context_type"]:
            if context_rule_id is not None:
                raise ValueError("unknown T13b context unexpectedly names a rule")
        elif context_rules.get(context_rule_id) != fact["context_type"]:
            raise ValueError("T13b context facet is not backed by frozen rule")

        amount_rule_id = fact.get("amount_rule_id")
        if fact["amount_type"] == defaults["amount_type"]:
            if amount_rule_id is not None:
                raise ValueError("unknown T13b amount unexpectedly names a rule")
        elif amount_rules.get(amount_rule_id) != fact["amount_type"]:
            raise ValueError("T13b amount facet is not backed by frozen rule")

        status = fact.get("representation_source_name_status")
        if status not in {"absent", "shared_nonblank", "divergent_omitted"}:
            raise ValueError(f"T13b emitted unknown source-name context status: {status}")
        if status in {"absent", "divergent_omitted"} and fact.get("representation_source_name_sha256") != empty_name_sha:
            raise ValueError("T13b used source-name context when it should have omitted it")

        if (
            fact["scope"] == defaults["scope"]
            and fact["context_type"] == defaults["context_type"]
            and fact["amount_type"] == defaults["amount_type"]
        ):
            fully_unknown += 1
        if fact["context_type"] != defaults["context_type"] and fact["amount_type"] == defaults["amount_type"]:
            context_known_amount_unknown += 1
        if fact["amount_type"] != defaults["amount_type"]:
            amount_known += 1
        for key in ("detector_authorized", "event_identity_assigned", "independence_assessed"):
            if fact.get(key) is not False:
                raise ValueError(f"T13b fact improperly changed semantic boundary: {key}")

    if low_quality_fact_count:
        raise ValueError(f"T13b contains {low_quality_fact_count} money facts below the 0.70 quality floor")
    if evaluation["fully_unknown_fact_count"] != fully_unknown:
        raise ValueError("T13b fully-unknown count is inconsistent")
    if evaluation["context_known_amount_unknown_fact_count"] != context_known_amount_unknown:
        raise ValueError("T13b partial-representation count is inconsistent")
    if evaluation["amount_type_known_fact_count"] != amount_known:
        raise ValueError("T13b known-amount-type count is inconsistent")

    return {
        "execution_label": "R1.T13b",
        "attachment_source_count": evaluation["sample"]["attachment_count"],
        "unique_artifact_count": evaluation["sample"]["unique_artifact_count"],
        "duplicate_artifact_group_count": evaluation["sample"]["duplicate_artifact_group_count"],
        "money_fact_count": evaluation["money_fact_count"],
        "fully_unknown_fact_count": evaluation["fully_unknown_fact_count"],
        "context_known_amount_unknown_fact_count": evaluation["context_known_amount_unknown_fact_count"],
        "amount_type_known_fact_count": evaluation["amount_type_known_fact_count"],
        "scope_counts": evaluation["scope_counts"],
        "context_type_counts": evaluation["context_type_counts"],
        "amount_type_counts": evaluation["amount_type_counts"],
        "source_name_context_status_counts": evaluation["source_name_context_status_counts"],
        "unique_artifact_page_count": evaluation["extraction"]["unique_artifact_page_count"],
        "post_ocr_low_quality_page_count": evaluation["extraction"]["post_ocr_low_quality_page_count"],
        "money_facts_below_quality_floor": low_quality_fact_count,
        "ocr_pages_attempted": evaluation["extraction"]["ocr_pages_attempted"],
        "ocr_extractions_added": evaluation["extraction"]["ocr_extractions_added"],
        "ocr_failed": evaluation["extraction"]["ocr_failed"],
        "global_discovery_rejection_count": len(rejections),
        "live_attachment_graph_size": discovery["attachments"]["resource_count"],
        "detector_authorized": evaluation["detector_authorized"],
        "event_identity_assigned": evaluation["event_identity_assigned"],
        "independence_assessed": evaluation["independence_assessed"],
        "lead_count": evaluation["lead_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--summary-out", required=True)
    args = parser.parse_args()

    summary = validate(
        Path(args.root),
        frozen_path=Path(args.selection),
        contract_path=Path(args.contract),
    )
    destination = Path(args.summary_out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
