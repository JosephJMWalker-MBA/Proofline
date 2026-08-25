from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "measure_t21_public_access_eastwood_search.py"

spec = importlib.util.spec_from_file_location("t21_public_access_search", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_frozen_search_plan_inherits_source_contract_and_target() -> None:
    plan = load("r1_t21_public_access_eastwood_search_plan.json")
    source = load("r1_t21_public_access_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")

    module.validate_inputs(plan, source, target)

    assert [row["request_id"] for row in plan["requests"]] == list(module.EXPECTED_REQUEST_IDS)
    assert [row["keyword"]["Value"] for row in plan["requests"]] == list(module.EXPECTED_VALUES)
    assert plan["selection_rule"]["post_result_term_expansion_allowed"] is False
    assert plan["selection_rule"]["document_retrieval_in_this_stage"] is False

    for request in plan["requests"]:
        assert request["query_id"] == 101
        assert request["QueryLimit"] == 0
        assert request["keyword"]["ID"] == 103
        assert request["keyword"]["Name"] == "Title Clause"
        assert request["keyword"]["KeywordOperator"] == "="
        assert module.tokens_appear_in_order(request["keyword"]["Value"], target["ordinance_title"])


def test_plan_rejects_post_result_term_expansion() -> None:
    plan = load("r1_t21_public_access_eastwood_search_plan.json")
    source = load("r1_t21_public_access_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")
    plan["selection_rule"]["post_result_term_expansion_allowed"] = True

    with pytest.raises(ValueError, match="term expansion"):
        module.validate_inputs(plan, source, target)


def test_search_response_parser_preserves_publisher_rows_without_interpretation() -> None:
    raw = json.dumps(
        {
            "Data": [
                {
                    "ID": "opaque-1",
                    "Name": "Document",
                    "DisplayColumnValues": [{"Value": "example", "RawValue": "example"}],
                }
            ],
            "DisplayColumns": [{"Heading": "Title Clause", "DataType": "AlphaNumeric"}],
            "Truncated": False,
        }
    ).encode()

    payload, documents, truncated = module.parse_search_response(raw)

    assert payload["DisplayColumns"][0]["Heading"] == "Title Clause"
    assert truncated is False
    assert documents == [
        {
            "id": "opaque-1",
            "name": "Document",
            "display_column_values": [{"Value": "example", "RawValue": "example"}],
            "score": None,
            "summary": None,
            "raw_row_sha256": module.sha256_json(payload["Data"][0]),
        }
    ]
    assert "outcome" not in documents[0]


def test_search_response_parser_surfaces_truncation() -> None:
    _, documents, truncated = module.parse_search_response(b'{"Data":[],"Truncated":true}')
    assert documents == []
    assert truncated is True


def test_search_response_parser_fails_closed_on_missing_data_array() -> None:
    with pytest.raises(ValueError, match="Data array"):
        module.parse_search_response(b'{"Truncated":false}')


def test_search_response_parser_fails_closed_on_missing_document_id() -> None:
    with pytest.raises(ValueError, match="stable returned ID"):
        module.parse_search_response(b'{"Data":[{"Name":"no id"}]}')
