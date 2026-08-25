from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "measure_t21_committee_minutes_date_search.py"

spec = importlib.util.spec_from_file_location("t21_committee_minutes_date_search", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load("r1_t21_committee_minutes_date_search_plan.json"),
        load("r1_t21_committee_minutes_source_contract_summary.json"),
        load("r1_t21_terminal_record_target.json"),
        load("r1_t21_agenda_status_sequence_summary.json"),
    )


def test_frozen_plan_validates_against_governed_sources() -> None:
    module.validate_inputs(*inputs())


def test_plan_has_exact_22_date_population_and_publisher_committee_value() -> None:
    plan, source, target, _ = inputs()
    assert len(plan["eastwood_requests"]) == 22
    assert [row["meeting_id"] for row in plan["eastwood_requests"]] == target["provenance"]["publisher_meeting_ids_with_exact_title"]
    assert plan["source_contract"]["committee_keyword"]["value"] == module.COMMITTEE_VALUE
    assert source["keyword_metadata"]["committee"]["planning_economic_development_value"] == module.COMMITTEE_VALUE
    assert plan["selection_rule"]["post_result_date_or_term_expansion_allowed"] is False


def test_validation_rejects_committee_value_drift() -> None:
    plan, source, target, sequence = inputs()
    plan = copy.deepcopy(plan)
    plan["source_contract"]["committee_keyword"]["value"] = "PUBLIC SERVICE"
    with pytest.raises(ValueError, match="Committee contract changed"):
        module.validate_inputs(plan, source, target, sequence)


def test_validation_rejects_date_population_drift() -> None:
    plan, source, target, sequence = inputs()
    plan = copy.deepcopy(plan)
    plan["eastwood_requests"] = plan["eastwood_requests"][:-1]
    with pytest.raises(ValueError, match="exactly equal frozen exact-title meeting IDs"):
        module.validate_inputs(plan, source, target, sequence)


def test_request_payload_preserves_two_exact_keywords() -> None:
    keywords = [
        {"ID": 124, "Name": "Meeting Date", "Value": "03/09/2026", "KeywordOperator": "="},
        {"ID": 105, "Name": "Committee", "Value": module.COMMITTEE_VALUE, "KeywordOperator": "="},
    ]
    assert module.request_payload(202, keywords, 0) == {
        "QueryID": 202,
        "Keywords": keywords,
        "QueryLimit": 0,
    }


def test_search_parser_keeps_token_out_of_stable_projection() -> None:
    base = {
        "Name": "Committee Meeting Minutes - Meeting Date: 3/9/2026",
        "DisplayColumnValues": [{"Name": "Committee", "Value": module.COMMITTEE_VALUE}],
        "Score": None,
        "Summary": None,
    }
    raw_a = json.dumps({"Data": [{"ID": "opaque-A", **base}], "Truncated": False}).encode()
    raw_b = json.dumps({"Data": [{"ID": "opaque-B", **base}], "Truncated": False}).encode()
    docs_a, _, _ = module.parse_search_response(raw_a)
    docs_b, _, _ = module.parse_search_response(raw_b)
    assert docs_a[0]["document_token"] != docs_b[0]["document_token"]
    assert docs_a[0]["stable_projection"] == docs_b[0]["stable_projection"]
    assert docs_a[0]["stable_projection_sha256"] == docs_b[0]["stable_projection_sha256"]


def test_group_signature_excludes_opaque_tokens_and_token_count() -> None:
    stable = {"name": "x", "display_column_values": [], "score": None, "summary": None}
    digest = module.sha256_json(stable)
    search = {
        "meeting_id": 671,
        "meeting_date": "2026-03-09",
        "returned_documents": [
            {"document_token": "A", "stable_projection": stable, "stable_projection_sha256": digest, "raw_row_sha256": "1"},
            {"document_token": "B", "stable_projection": stable, "stable_projection_sha256": digest, "raw_row_sha256": "2"},
        ],
    }
    groups = module.group_stable_candidates([search])
    assert groups[0]["observed_token_count"] == 2
    projection = module.stable_group_signature_projection(groups)
    assert "observed_document_tokens" not in projection[0]
    assert "observed_token_count" not in projection[0]
