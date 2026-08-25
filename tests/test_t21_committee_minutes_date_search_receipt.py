from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_receipt_pins_pre_observation_plan_and_source_contract() -> None:
    receipt = load("r1_t21_committee_minutes_date_search_summary.json")
    plan = load("r1_t21_committee_minutes_date_search_plan.json")
    source = load("r1_t21_committee_minutes_source_contract_summary.json")

    assert receipt["schema"] == "proofline-akron-t21-committee-minutes-date-search-receipt/v1"
    assert receipt["plan"]["sha256"] == sha256_json(plan)
    assert receipt["plan"]["pre_observation_plan_commit"] == "de6d2aa0b533bd620ee43a820ee4243f618aacfa"
    assert receipt["source_contract"]["query_id"] == source["source_contract"]["query"]["id"] == "202"
    assert receipt["source_contract"]["committee_value"] == source["keyword_metadata"]["committee"]["planning_economic_development_value"]


def test_receipt_pins_18_returned_dates_and_four_bounded_nonfindings() -> None:
    receipt = load("r1_t21_committee_minutes_date_search_summary.json")
    counts = receipt["counts"]
    assert counts["eastwood_request_count"] == 22
    assert counts["successful_eastwood_request_count"] == 22
    assert counts["truncated_eastwood_request_count"] == 0
    assert counts["eastwood_dates_with_results"] == 18
    assert counts["eastwood_dates_without_results"] == 4
    assert counts["eastwood_returned_document_token_count"] == 18
    assert counts["eastwood_stable_metadata_group_count"] == 18
    assert counts["eastwood_duplicate_metadata_group_count"] == 0

    zeros = [(row["meeting_id"], row["meeting_date"]) for row in receipt["eastwood_searches"] if row["returned_document_count"] == 0]
    assert zeros == [
        (675, "2026-03-30"),
        (677, "2026-04-13"),
        (678, "2026-04-20"),
        (697, "2026-07-27"),
    ]
    assert receipt["bounded_nonfinding_dates"] == [
        {"meeting_id": 675, "meeting_date": "2026-03-30"},
        {"meeting_id": 677, "meeting_date": "2026-04-13"},
        {"meeting_id": 678, "meeting_date": "2026-04-20"},
        {"meeting_id": 697, "meeting_date": "2026-07-27"},
    ]


def test_receipt_pins_each_date_payload_and_stable_result() -> None:
    receipt = load("r1_t21_committee_minutes_date_search_summary.json")
    rows = receipt["eastwood_searches"]
    assert len(rows) == 22
    assert len({row["meeting_id"] for row in rows}) == 22
    assert all(len(row["request_payload_sha256"]) == 64 for row in rows)
    assert all(len(row["stable_result_signature_sha256"]) == 64 for row in rows)
    assert all(row["truncated"] is False for row in rows)
    assert all(row["returned_document_count"] in (0, 1) for row in rows)
    assert all(row["stable_unique_projection_count"] == row["returned_document_count"] for row in rows)


def test_receipt_keeps_control_growing_population_out_of_replay_identity() -> None:
    receipt = load("r1_t21_committee_minutes_date_search_summary.json")
    control = receipt["positive_control"]
    assert control["canonical_returned_document_count"] == 23
    assert control["minimum_returned_document_count"] == 1
    assert control["excluded_from_eastwood_population"] is True
    assert control["population_not_pinned_for_replay"] is True
    assert receipt["receipt_guards"]["positive_control_population_not_pinned"] is True
    assert receipt["receipt_guards"]["opaque_document_tokens_not_pinned"] is True
    assert receipt["receipt_guards"]["raw_rows_with_opaque_tokens_not_pinned"] is True


def test_receipt_keeps_outcome_unknown_and_nonfindings_nonterminal() -> None:
    receipt = load("r1_t21_committee_minutes_date_search_summary.json")
    assert receipt["outcome"]["status"] == "unknown"
    authority = receipt["authority_boundary"]
    assert authority["returned_document_dereferenced"] is False
    assert authority["terminal_outcome_assigned"] is False
    assert authority["absence_treated_as_disposition"] is False
    assert authority["committee_value_guessed"] is False
    assert authority["opaque_document_token_treated_as_stable_identity"] is False
    assert receipt["receipt_guards"]["zero_minutes_result_is_not_disposition"] is True
