from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "experiments" / "akron-2026" / "r1_t21_passed_legislation_recall_expansion_summary.json"


def test_recall_expansion_receipt_preserves_nonterminal_boundary() -> None:
    r = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert r["schema"] == "proofline-akron-t21-passed-legislation-recall-expansion-receipt/v1"
    assert r["pre_observation_plan_commit"] == "c62eb20298d902b7bab24278cc86a0be67a95952"
    assert r["counts"] == {
        "request_count": 4,
        "returned_retrieval_handle_count": 1557,
        "stable_candidate_group_count": 1528,
        "successful_request_count": 4,
        "target_screened_candidate_group_count": 12,
        "truncated_request_count": 0,
    }
    observations = r["screening_observations"]
    assert observations["action_and_location_group_count"] == 12
    assert observations["street_number_and_location_group_count"] == 0
    assert observations["distinctive_use_tokens_group_count"] == 0
    assert observations["use_and_location_group_count"] == 0
    assert r["authority_boundary"]["returned_document_dereferenced"] is False
    assert r["authority_boundary"]["terminal_outcome_assigned"] is False
    assert r["authority_boundary"]["absence_treated_as_disposition"] is False
    assert r["outcome"]["status"] == "unknown"


def test_1928_expansion_result_is_frozen_zero_without_disposition_semantics() -> None:
    r = json.loads(RECEIPT.read_text(encoding="utf-8"))
    by_id = {row["request_id"]: row for row in r["search_receipts"]}
    street = by_id["title_clause_street_number_token"]
    assert street["value"] == "*1928*"
    assert street["canonical_returned_document_count"] == 0
    assert street["canonical_stable_unique_projection_count"] == 0
    assert r["receipt_guards"]["zero_1928_result_not_disposition"] is True
