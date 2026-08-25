from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_frozen_council_minutes_contract_inherits_public_access_query() -> None:
    receipt = load("r1_t21_council_minutes_source_contract_summary.json")
    source = load("r1_t21_public_access_source_contract_summary.json")

    assert receipt["schema"] == "proofline-akron-t21-council-minutes-source-contract-receipt/v1"
    assert receipt["stage"] == "frozen_council_minutes_query_contract_before_document_search"

    expected_query = next(
        row for row in source["custom_queries"]["queries"]
        if row["name"] == "Council Meeting Minutes"
    )
    assert receipt["source_contract"]["query"] == expected_query
    assert expected_query["id"] == "175"
    assert receipt["source_contract"]["api_root"] == source["configuration"]["api_root"]


def test_frozen_council_minutes_keywords_are_meeting_date_and_year_only() -> None:
    receipt = load("r1_t21_council_minutes_source_contract_summary.json")
    keywords = receipt["keyword_metadata"]["keywords"]

    assert receipt["keyword_metadata"]["keyword_count"] == 2
    assert [row["id"] for row in keywords] == ["124", "532"]
    assert [row["name"] for row in keywords] == ["Meeting Date", "Year"]
    assert keywords[0]["data_type"] == "Date"
    assert keywords[0]["dataset"] is None
    assert keywords[1]["data_type"] == "SmallNumeric"
    assert keywords[1]["dataset_summary"] == {
        "count": 151,
        "first": "1900",
        "last": "2050",
        "contains_2026": True,
    }


def test_frozen_council_minutes_contract_remains_metadata_only() -> None:
    receipt = load("r1_t21_council_minutes_source_contract_summary.json")

    assert receipt["authority_boundary"] == {
        "custom_query_metadata_inherited": True,
        "keyword_metadata_requested": True,
        "document_search_submitted": False,
        "query_id_guessed": False,
        "keyword_id_guessed": False,
        "document_token_enumerated": False,
        "returned_document_dereferenced": False,
        "terminal_outcome_assigned": False,
        "absence_treated_as_disposition": False,
        "causality_assigned": False,
        "detector_authorized": False,
        "lead_count": None,
    }
    assert receipt["interpretation"]["eastwood_outcome_status"] == "Unknown"
    assert receipt["interpretation"]["document_search_performed"] is False
