from __future__ import annotations

import pytest

from proofline.disposition_surfaces import build_inventory


def public_access_fixture() -> dict:
    return {
        "schema": "proofline-akron-t21-public-access-source-contract-receipt/v1",
        "custom_queries": {
            "queries": [
                {"name": "Committee Meeting Minutes"},
                {"name": "Council Meeting Minutes"},
                {"name": "Passed Legislation"},
                {"name": "Street Cards"},
            ]
        },
    }


def chronology_fixture() -> dict:
    return {
        "schema": "proofline-akron-t21-evidence-chronology-receipt/v1",
        "outcome": {"status": "unknown"},
    }


def council_contract_fixture() -> dict:
    return {
        "legal_notices_section38_declared": True,
        "legal_notices_full_passed_list_points_to_agenda": True,
        "legislation_minutes_passed_archive_declared": True,
        "legislation_minutes_municipal_code_declared": True,
    }


def test_inventory_selects_positive_only_section38_surface() -> None:
    inventory = build_inventory(public_access_fixture(), chronology_fixture(), council_contract_fixture())
    assert inventory["counts"] == {
        "surface_count": 8,
        "tested_count": 4,
        "untested_positive_only_count": 1,
        "next_priority_count": 1,
    }
    assert inventory["selected_next_surface_id"] == "charter_section38_legal_notices"
    selected = next(row for row in inventory["surfaces"] if row["next_priority"])
    assert selected["completeness"] == "positive_only_not_full_passed_archive"
    assert selected["negative_result_is_terminal"] is False
    assert inventory["authority_boundary"]["target_search_submitted"] is False
    assert inventory["outcome"]["status"] == "unknown"


def test_public_access_registry_drift_fails_closed() -> None:
    public_access = public_access_fixture()
    public_access["custom_queries"]["queries"].append({"name": "Mystery Disposition Ledger"})
    with pytest.raises(ValueError, match="registry drifted"):
        build_inventory(public_access, chronology_fixture(), council_contract_fixture())


def test_terminal_upstream_outcome_fails_closed() -> None:
    chronology = chronology_fixture()
    chronology["outcome"]["status"] = "approved"
    with pytest.raises(ValueError, match="remains Unknown"):
        build_inventory(public_access_fixture(), chronology, council_contract_fixture())


def test_notice_completeness_cannot_be_upgraded_silently() -> None:
    contract = council_contract_fixture()
    contract["legal_notices_full_passed_list_points_to_agenda"] = False
    with pytest.raises(ValueError, match="missing required declaration"):
        build_inventory(public_access_fixture(), chronology_fixture(), contract)
