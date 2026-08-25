from __future__ import annotations

import hashlib
import json
from typing import Any

INVENTORY_SCHEMA = "proofline-disposition-surface-inventory/v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def validate_upstream(public_access: dict, chronology: dict) -> None:
    if public_access.get("schema") != "proofline-akron-t21-public-access-source-contract-receipt/v1":
        raise ValueError("unexpected Public Access source-contract schema")
    if chronology.get("schema") != "proofline-akron-t21-evidence-chronology-receipt/v1":
        raise ValueError("unexpected chronology schema")
    if str(chronology.get("outcome", {}).get("status", "")).lower() != "unknown":
        raise ValueError("surface inventory is only authorized while chronology outcome remains Unknown")
    queries = {row["name"] for row in public_access["custom_queries"]["queries"]}
    if queries != {"Committee Meeting Minutes", "Council Meeting Minutes", "Passed Legislation", "Street Cards"}:
        raise ValueError("Public Access custom-query registry drifted")


def build_inventory(public_access: dict, chronology: dict, council_contract: dict) -> dict:
    validate_upstream(public_access, chronology)
    required = {
        "legal_notices_section38_declared": True,
        "legal_notices_full_passed_list_points_to_agenda": True,
        "legislation_minutes_passed_archive_declared": True,
        "legislation_minutes_municipal_code_declared": True,
    }
    for key, expected in required.items():
        if council_contract.get(key) is not expected:
            raise ValueError(f"Council publication contract missing required declaration: {key}")

    surfaces = [
        {
            "id": "agenda_passed_list",
            "publisher_surface": "OnBase Agenda Online / Ordinances & Resolutions Passed at Previous Meeting",
            "authority": "official_council_passed_legislation_listing",
            "completeness": "council_page_declares_agenda_as_full_passed_list_per_meeting",
            "target_stage_status": "tested",
            "governed_by": ["r1_t21_terminal_record_candidate_scan_summary.json"],
            "target_result": "zero_exact_title_numbered_vote_candidates_in_bounded_scan",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "public_access_passed_legislation",
            "publisher_surface": "Public Access / Passed Legislation",
            "authority": "official_council_passed_legislation_archive",
            "completeness": "publisher_designated_archive_but_target_search_semantics_are_query_bounded",
            "target_stage_status": "tested",
            "governed_by": [
                "r1_t21_public_access_eastwood_search_summary.json",
                "r1_t21_passed_legislation_recall_expansion_summary.json",
            ],
            "target_result": "no_strong_target_identity_candidate_under_frozen_queries",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "council_minutes",
            "publisher_surface": "Public Access / Council Meeting Minutes",
            "authority": "official_council_minutes",
            "completeness": "date_bounded_minutes_corpus_not_terminally_exhaustive",
            "target_stage_status": "tested",
            "governed_by": ["r1_t21_council_minutes_content_audit_summary.json"],
            "target_result": "target_local_procedural_evidence_zero_terminal_candidates",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "committee_minutes",
            "publisher_surface": "Public Access / Committee Meeting Minutes",
            "authority": "official_committee_minutes",
            "completeness": "date_and_committee_bounded_minutes_corpus_not_terminally_exhaustive",
            "target_stage_status": "tested",
            "governed_by": ["r1_t21_committee_minutes_content_audit_summary.json"],
            "target_result": "target_local_procedural_evidence_zero_terminal_candidates",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "charter_section38_legal_notices",
            "publisher_surface": "Akron City Council / Legal Notices and Clerk-authored Section 38 publication summaries",
            "authority": "official_clerk_publication_positive_disposition_evidence",
            "completeness": "positive_only_not_full_passed_archive",
            "target_stage_status": "untested",
            "governed_by": [],
            "target_result": "not_searched_in_this_stage",
            "negative_result_is_terminal": False,
            "next_priority": True,
        },
        {
            "id": "municipal_code_pending_amendments",
            "publisher_surface": "Akron City Council / Municipal Code and pending supplement list",
            "authority": "official_council_codification_pointer",
            "completeness": "not_full_passed_legislation_ledger",
            "target_stage_status": "not_selected",
            "governed_by": [],
            "target_result": "not_searched_in_this_stage",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "street_cards",
            "publisher_surface": "Public Access / Street Cards",
            "authority": "official_property_record_query",
            "completeness": "not_a_legislative_disposition_surface",
            "target_stage_status": "out_of_scope_for_disposition",
            "governed_by": ["r1_t21_public_access_source_contract_summary.json"],
            "target_result": "not_applicable",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
        {
            "id": "clerk_public_records_request",
            "publisher_surface": "Akron City Council Clerk / public-record request path",
            "authority": "official_clerk_record_custody_request_path",
            "completeness": "request_scoped_not_publicly_enumerable_in_this_inventory",
            "target_stage_status": "fallback_untested",
            "governed_by": [],
            "target_result": "no_request_submitted_in_this_stage",
            "negative_result_is_terminal": False,
            "next_priority": False,
        },
    ]
    inventory = {
        "schema": INVENTORY_SCHEMA,
        "surfaces": surfaces,
        "counts": {
            "surface_count": len(surfaces),
            "tested_count": sum(row["target_stage_status"] == "tested" for row in surfaces),
            "untested_positive_only_count": sum(row["target_stage_status"] == "untested" for row in surfaces),
            "next_priority_count": sum(bool(row["next_priority"]) for row in surfaces),
        },
        "selected_next_surface_id": "charter_section38_legal_notices",
        "authority_boundary": {
            "inventory_only": True,
            "target_search_submitted": False,
            "negative_notice_result_would_be_terminal": False,
            "passed_legislation_vocabulary_expanded": False,
            "absence_treated_as_disposition": False,
            "terminal_outcome_assigned": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "This stage inventories source authority and completeness only. It does not search the selected positive-only notice surface for the Eastwood target or assign disposition.",
        },
    }
    inventory["surface_population_signature_sha256"] = sha256_json(surfaces)
    return inventory
