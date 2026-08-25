from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_frozen_council_minutes_date_search_receipt() -> None:
    receipt = load("r1_t21_council_minutes_date_search_summary.json")
    plan = load("r1_t21_council_minutes_date_search_plan.json")
    source = load("r1_t21_council_minutes_source_contract_summary.json")

    assert receipt["schema"] == "proofline-akron-t21-council-minutes-date-search-receipt/v1"
    assert receipt["stage"] == "frozen_council_minutes_exact_date_candidate_search_before_document_retrieval"
    assert receipt["canonical_measurement"] == {
        "artifact_digest": "sha256:d343b9d93623eb650319da1acec66cd56222ef614739dfac81c1832d315596d2",
        "artifact_id": 9548211264,
        "head_sha": "adfca9edf37354bea87b8354666cec6d6975cc44",
        "job_id": 97676582203,
        "observed_at_utc": "2026-08-25T03:42:43.674762+00:00",
        "raw_measurement_byte_size": 116544,
        "raw_measurement_sha256": "e8972aa3fe2134166b3a69ed88e2bbfb502729cca3a1f1901ce85472ba1cfe0a",
        "workflow_run_id": 32806166952,
    }
    assert receipt["source_contract"]["query_id"] == "175"
    assert receipt["source_contract"]["meeting_date_keyword_id"] == "124"
    assert receipt["source_contract"]["year_keyword_id"] == "532"
    assert receipt["source_contract"]["api_root"] == source["source_contract"]["api_root"]

    assert len(plan["eastwood_requests"]) == len(receipt["date_receipts"]) == 22
    assert receipt["counts"] == {
        "eastwood_dates_with_results": 21,
        "eastwood_dates_without_results": 1,
        "eastwood_duplicate_metadata_group_count": 5,
        "eastwood_request_count": 22,
        "eastwood_returned_document_token_count": 26,
        "eastwood_stable_metadata_group_count": 21,
        "positive_control_returned_document_count": 36,
        "successful_eastwood_request_count": 22,
        "truncated_eastwood_request_count": 0,
    }
    assert receipt["missing_dates"] == [{"meeting_date": "2026-07-27", "meeting_id": 697}]
    assert [row["meeting_id"] for row in receipt["duplicate_visible_metadata_groups"]] == [671, 676, 686, 690, 694]
    assert all(row["observed_token_count"] == 2 for row in receipt["duplicate_visible_metadata_groups"])
    assert receipt["stable_candidate_population_signature_sha256"] == "3c829d69f527322164ea2566e65b459c3824c9ae640918398e1b6e6f476d02d3"
    assert receipt["eastwood_response_population_signature_sha256"] == "00aa150a444503932fc7f5d845a4e9717cfa387513acdf8415919f105a878d9e"

    assert receipt["positive_control"]["request_payload_sha256"] == "de66d251ce956ba16c309d25a2c5f987eb97c6dbf564cb0284cdde2dc916a630"
    assert receipt["positive_control"]["population_not_pinned"] is True
    assert receipt["receipt_guards"] == {
        "duplicate_visible_metadata_does_not_resolve_document_equivalence": True,
        "opaque_document_tokens_not_pinned": True,
        "per_date_request_payloads_pinned": True,
        "per_date_return_counts_pinned": True,
        "per_date_stable_visible_metadata_signatures_pinned": True,
        "positive_control_population_not_pinned": True,
        "raw_rows_with_opaque_tokens_not_pinned": True,
        "zero_minutes_result_is_not_disposition": True,
    }
    assert receipt["authority_boundary"]["returned_document_dereferenced"] is False
    assert receipt["authority_boundary"]["terminal_outcome_assigned"] is False
    assert receipt["authority_boundary"]["absence_treated_as_disposition"] is False
    assert receipt["authority_boundary"]["identical_visible_metadata_assumed_same_document"] is False
    assert receipt["authority_boundary"]["identical_visible_metadata_assumed_distinct_documents"] is False
    assert receipt["outcome"]["status"] == "unknown"
    assert receipt["interpretation"]["eastwood_outcome_status"] == "Unknown"
