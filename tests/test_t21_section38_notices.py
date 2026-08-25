from __future__ import annotations

from copy import deepcopy

import pytest

from proofline.section38_notices import classify_document, validate_inputs


def plan() -> dict:
    return {
        "schema": "proofline-akron-t21-section38-positive-search-plan/v1",
        "publisher_source": {
            "accepted_document_host": "www.akroncitycouncil.org",
            "accepted_document_path_prefix": "/sites/default/files/docs/",
            "accepted_content_type": "application/pdf",
        },
        "positive_control": {
            "url": "https://www.akroncitycouncil.org/sites/default/files/docs/Summary%20of%20O-40-2026.pdf"
        },
        "external_discovery": {
            "post_observation_query_expansion_allowed": False,
            "queries": [
                {"id": "exact_address", "query": "q1"},
                {"id": "distinctive_use_phrase", "query": "q2"},
                {"id": "planning_case", "query": "q3"},
                {"id": "petitioner_and_location", "query": "q4"},
            ],
        },
        "target_identity": {
            "exact_address": "1928 Eastwood Avenue",
            "planning_case": "PC-2025-80-CU",
            "petitioner": "David Walker",
            "distinctive_use_tokens": ["defense", "education", "training", "facility"],
            "location_token": "Eastwood",
        },
        "terminal_positive_contract": {
            "required_section38_markers": [
                "passed by Akron City Council",
                "Clerk of Council",
                "This summary is being published pursuant to Section 38 of the City Charter",
            ],
            "minimum_target_identity_rules_satisfied": 1,
            "authorized_terminal_status_if_all_contract_requirements_hold": "passed_by_council",
        },
    }


def inventory() -> dict:
    return {
        "schema": "proofline-akron-t21-disposition-surface-inventory-receipt/v1",
        "selected_next_surface_id": "charter_section38_legal_notices",
        "surfaces": [
            {
                "id": "charter_section38_legal_notices",
                "completeness": "positive_only_not_full_passed_archive",
                "negative_result_is_terminal": False,
            }
        ],
        "outcome": {"status": "unknown"},
    }


def discovery() -> dict:
    return {
        "schema": "proofline-akron-t21-section38-discovery-observation/v1",
        "pre_observation_plan_commit": "7b5c5a514fed0786f83029bc6bd2977d2840485e",
        "queries": [
            {"id": "exact_address"},
            {"id": "distinctive_use_phrase"},
            {"id": "planning_case"},
            {"id": "petitioner_and_location"},
        ],
        "unique_candidate_urls": [
            "https://www.akroncitycouncil.org/sites/default/files/docs/advertise%20for%203.9%20public%20hearings.pdf"
        ],
        "observation_boundary": {
            "post_observation_query_expansion_performed": False,
            "search_engine_nonfinding_is_disposition_evidence": False,
        },
    }


def test_target_hearing_notice_is_not_terminal() -> None:
    text = """
    LEGAL NOTICE
    Ordinance authorizing a Conditional Use to establish a defense education training facility
    at 1928 Eastwood Avenue.
    Sara Biviano, Clerk of Council
    """
    result = classify_document(text, plan())
    assert result["identity_hits"] == ["exact_address", "distinctive_use_tokens_and_location"]
    assert result["all_required_section38_markers_present"] is False
    assert result["terminal_positive"] is False
    assert result["classification"] == "target_identity_nonterminal_document"
    assert result["authorized_terminal_status"] is None


def test_direct_target_section38_summary_can_assign_passed_by_council() -> None:
    text = """
    Summary of Ordinance No. 999-2026 passed by Akron City Council July 1, 2026,
    authorizing a Conditional Use to establish a defense education training facility at
    1928 Eastwood Avenue.
    By: Sara Biviano, Clerk of Council
    This summary is being published pursuant to Section 38 of the City Charter.
    """
    result = classify_document(text, plan())
    assert result["terminal_positive"] is True
    assert result["classification"] == "target_section38_passage_summary"
    assert result["authorized_terminal_status"] == "passed_by_council"
    assert result["approval_or_effective_date_inferred"] is False


def test_non_target_section38_summary_does_not_assign_eastwood_outcome() -> None:
    text = """
    Summary of Ordinance No. 40-2026 passed by Akron City Council February 9, 2026.
    By: Sara Biviano, Clerk of Council
    This summary is being published pursuant to Section 38 of the City Charter.
    """
    result = classify_document(text, plan())
    assert result["all_required_section38_markers_present"] is True
    assert result["identity_hits"] == []
    assert result["terminal_positive"] is False
    assert result["classification"] == "section38_non_target_document"


def test_validate_inputs_preserves_positive_only_absence_boundary() -> None:
    validate_inputs(plan(), inventory(), discovery())

    bad = deepcopy(inventory())
    bad["surfaces"][0]["negative_result_is_terminal"] = True
    with pytest.raises(ValueError, match="absence cannot become terminal"):
        validate_inputs(plan(), bad, discovery())


def test_validate_inputs_rejects_post_observation_query_expansion() -> None:
    bad = deepcopy(discovery())
    bad["observation_boundary"]["post_observation_query_expansion_performed"] = True
    with pytest.raises(ValueError, match="query expansion"):
        validate_inputs(plan(), inventory(), bad)
