from __future__ import annotations

import json
from pathlib import Path


def load_receipt() -> dict:
    return json.loads(Path("experiments/akron-2026/r1_t21_disposition_surface_inventory_summary.json").read_text())


def test_frozen_inventory_receipt_shape() -> None:
    receipt = load_receipt()
    assert receipt["schema"] == "proofline-akron-t21-disposition-surface-inventory-receipt/v1"
    assert receipt["counts"] == {
        "surface_count": 8,
        "tested_count": 4,
        "untested_positive_only_count": 1,
        "next_priority_count": 1,
    }
    assert receipt["selected_next_surface_id"] == "charter_section38_legal_notices"
    assert receipt["surface_population_signature_sha256"] == "56ecb542c795ffae35bd27475c2fe9a3801189c3d9a80defccc2f9a8b48ac12f"
    assert receipt["inventory_signature_sha256"] == "fda5333e4b866cf0b8246c069a61b67fdce15ca9df54b14e5c6cea79eead98d6"


def test_selected_surface_is_positive_only_and_nonterminal_on_absence() -> None:
    receipt = load_receipt()
    selected = next(row for row in receipt["surfaces"] if row["id"] == receipt["selected_next_surface_id"])
    assert selected["authority"] == "official_clerk_publication_positive_disposition_evidence"
    assert selected["completeness"] == "positive_only_not_full_passed_archive"
    assert selected["target_stage_status"] == "untested"
    assert selected["negative_result_is_terminal"] is False
    assert selected["next_priority"] is True
    assert receipt["receipt_guards"]["section38_notice_absence_cannot_be_disposition"] is True


def test_official_council_contract_keeps_full_passed_list_on_agenda() -> None:
    receipt = load_receipt()
    contract = receipt["official_council_publication_contract"]
    assert contract["legal_notices_section38_declared"] is True
    assert contract["legal_notices_full_passed_list_points_to_agenda"] is True
    assert contract["legislation_minutes_passed_archive_declared"] is True
    assert contract["public_record_request_path_declared"] is True


def test_inventory_does_not_assign_outcome_or_search_target() -> None:
    receipt = load_receipt()
    boundary = receipt["authority_boundary"]
    assert boundary["inventory_only"] is True
    assert boundary["target_search_submitted"] is False
    assert boundary["negative_notice_result_would_be_terminal"] is False
    assert boundary["passed_legislation_vocabulary_expanded"] is False
    assert boundary["absence_treated_as_disposition"] is False
    assert boundary["terminal_outcome_assigned"] is False
    assert receipt["outcome"]["status"] == "unknown"
