from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

PLAN_SCHEMA = "proofline-akron-t21-section38-positive-search-plan/v1"
DISCOVERY_SCHEMA = "proofline-akron-t21-section38-discovery-observation/v1"
INVENTORY_SCHEMA = "proofline-akron-t21-disposition-surface-inventory-receipt/v1"
CLASSIFICATION_SCHEMA = "proofline-section38-document-classification/v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _contains(text: str, phrase: str) -> bool:
    return normalize_text(phrase).casefold() in normalize_text(text).casefold()


def validate_direct_url(url: str, plan: dict) -> None:
    parsed = urlparse(url)
    publisher = plan["publisher_source"]
    if parsed.scheme != "https":
        raise ValueError("Section 38 direct source must use HTTPS")
    if parsed.hostname != publisher["accepted_document_host"]:
        raise ValueError("Section 38 direct source left the frozen Council host")
    if not parsed.path.startswith(publisher["accepted_document_path_prefix"]):
        raise ValueError("Section 38 direct source left the frozen Council document path")


def validate_inputs(plan: dict, inventory: dict, discovery: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected Section 38 search-plan schema")
    if discovery.get("schema") != DISCOVERY_SCHEMA:
        raise ValueError("unexpected Section 38 discovery-observation schema")
    if inventory.get("schema") != INVENTORY_SCHEMA:
        raise ValueError("unexpected disposition-surface inventory receipt schema")
    if inventory.get("selected_next_surface_id") != "charter_section38_legal_notices":
        raise ValueError("frozen inventory no longer selects the Section 38 surface")
    if str(inventory.get("outcome", {}).get("status", "")).lower() != "unknown":
        raise ValueError("Section 38 positive search is only authorized while upstream outcome is Unknown")
    selected = [
        row for row in inventory.get("surfaces", [])
        if row.get("id") == "charter_section38_legal_notices"
    ]
    if len(selected) != 1:
        raise ValueError("Section 38 inventory surface must resolve uniquely")
    surface = selected[0]
    if surface.get("completeness") != "positive_only_not_full_passed_archive":
        raise ValueError("Section 38 surface completeness semantics drifted")
    if surface.get("negative_result_is_terminal") is not False:
        raise ValueError("Section 38 absence cannot become terminal")
    if discovery.get("pre_observation_plan_commit") != "7b5c5a514fed0786f83029bc6bd2977d2840485e":
        raise ValueError("discovery observation no longer points to the frozen pre-observation plan commit")
    if discovery.get("observation_boundary", {}).get("post_observation_query_expansion_performed") is not False:
        raise ValueError("post-observation query expansion is forbidden")

    planned = [(row["id"], row["query"]) for row in plan["external_discovery"]["queries"]]
    observed_ids = [row["id"] for row in discovery["queries"]]
    if observed_ids != [row[0] for row in planned]:
        raise ValueError("discovery query population drifted from frozen plan")
    if plan["external_discovery"].get("post_observation_query_expansion_allowed") is not False:
        raise ValueError("plan must forbid post-observation query expansion")
    if discovery.get("observation_boundary", {}).get("search_engine_nonfinding_is_disposition_evidence") is not False:
        raise ValueError("search-engine nonfindings cannot carry disposition authority")
    for url in discovery.get("unique_candidate_urls", []):
        validate_direct_url(url, plan)
    validate_direct_url(plan["positive_control"]["url"], plan)


def identity_hits(text: str, plan: dict) -> list[str]:
    target = plan["target_identity"]
    hits: list[str] = []
    if _contains(text, target["exact_address"]):
        hits.append("exact_address")
    if _contains(text, target["planning_case"]):
        hits.append("planning_case")
    if all(_contains(text, token) for token in target["distinctive_use_tokens"]) and _contains(text, target["location_token"]):
        hits.append("distinctive_use_tokens_and_location")
    if _contains(text, target["petitioner"]) and _contains(text, target["location_token"]):
        hits.append("petitioner_and_location")
    return hits


def section38_marker_hits(text: str, plan: dict) -> list[str]:
    return [
        marker for marker in plan["terminal_positive_contract"]["required_section38_markers"]
        if _contains(text, marker)
    ]


def classify_document(text: str, plan: dict) -> dict:
    identities = identity_hits(text, plan)
    markers = section38_marker_hits(text, plan)
    required_markers = plan["terminal_positive_contract"]["required_section38_markers"]
    all_markers = len(markers) == len(required_markers)
    enough_identity = len(identities) >= int(
        plan["terminal_positive_contract"]["minimum_target_identity_rules_satisfied"]
    )
    terminal_positive = all_markers and enough_identity

    if terminal_positive:
        label = "target_section38_passage_summary"
    elif identities:
        label = "target_identity_nonterminal_document"
    elif all_markers:
        label = "section38_non_target_document"
    else:
        label = "non_target_nonterminal_document"

    result = {
        "schema": CLASSIFICATION_SCHEMA,
        "identity_hits": identities,
        "section38_marker_hits": markers,
        "all_required_section38_markers_present": all_markers,
        "minimum_target_identity_satisfied": enough_identity,
        "terminal_positive": terminal_positive,
        "classification": label,
        "authorized_terminal_status": (
            plan["terminal_positive_contract"]["authorized_terminal_status_if_all_contract_requirements_hold"]
            if terminal_positive else None
        ),
        "approval_or_effective_date_inferred": False,
    }
    result["classification_signature_sha256"] = sha256_json(result)
    return result


def validate_positive_control_text(text: str, plan: dict) -> None:
    missing = [
        phrase for phrase in plan["positive_control"]["required_text"]
        if not _contains(text, phrase)
    ]
    if missing:
        raise ValueError(f"known Section 38 positive control lost required text: {missing}")
    classification = classify_document(text, plan)
    if not classification["all_required_section38_markers_present"]:
        raise ValueError("known Section 38 positive control no longer exercises all terminal markers")
    if classification["identity_hits"]:
        raise ValueError("known Section 38 positive control unexpectedly matches Eastwood target identity")
    if classification["terminal_positive"]:
        raise ValueError("non-target positive control cannot assign Eastwood disposition")
