from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "measure_t21_council_minutes_date_search.py"

spec = importlib.util.spec_from_file_location("t21_minutes_date_search", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_frozen_plan_matches_source_target_and_chronology() -> None:
    plan = load("r1_t21_council_minutes_date_search_plan.json")
    source = load("r1_t21_council_minutes_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")
    sequence = load("r1_t21_agenda_status_sequence_summary.json")

    module.validate_inputs(plan, source, target, sequence)

    requests = plan["eastwood_requests"]
    assert len(requests) == 22
    assert [row["meeting_id"] for row in requests] == target["provenance"]["publisher_meeting_ids_with_exact_title"]
    assert requests[0]["keyword_value"] == "02/23/2026"
    assert requests[-1]["keyword_value"] == "07/27/2026"
    assert plan["positive_control"]["included_in_eastwood_population"] is False
    assert plan["selection_rule"]["post_result_date_or_term_expansion_allowed"] is False


def test_plan_rejects_date_drift() -> None:
    plan = load("r1_t21_council_minutes_date_search_plan.json")
    source = load("r1_t21_council_minutes_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")
    sequence = load("r1_t21_agenda_status_sequence_summary.json")
    plan["eastwood_requests"][0]["keyword_value"] = "02/24/2026"

    with pytest.raises(ValueError, match="MM/DD/YYYY"):
        module.validate_inputs(plan, source, target, sequence)


def test_plan_rejects_population_expansion() -> None:
    plan = load("r1_t21_council_minutes_date_search_plan.json")
    source = load("r1_t21_council_minutes_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")
    sequence = load("r1_t21_agenda_status_sequence_summary.json")
    plan["eastwood_requests"].append({
        "meeting_id": 695,
        "meeting_date": "2026-07-20",
        "request_id": "meeting_695_2026_07_20",
        "keyword_value": "07/20/2026",
    })

    with pytest.raises(ValueError, match="exactly equal"):
        module.validate_inputs(plan, source, target, sequence)


def test_response_parser_excludes_opaque_token_from_stable_projection() -> None:
    raw = json.dumps({
        "Data": [{
            "ID": "rotating-token-a",
            "Name": "Council Meeting Minutes - 03/09/2026",
            "DisplayColumnValues": [{"Value": "03/09/2026", "RawValue": "2026-03-09"}],
            "Score": None,
            "Summary": None,
        }],
        "DisplayColumns": [{"Heading": "Meeting Date", "DataType": "Date"}],
        "Truncated": False,
    }).encode()

    documents, truncated, columns = module.parse_search_response(raw)

    assert truncated is False
    assert columns[0]["Heading"] == "Meeting Date"
    assert documents[0]["document_token"] == "rotating-token-a"
    assert "document_token" not in documents[0]["stable_projection"]
    assert documents[0]["stable_projection"]["name"] == "Council Meeting Minutes - 03/09/2026"


def test_response_parser_fails_closed_on_missing_token() -> None:
    with pytest.raises(ValueError, match="document token"):
        module.parse_search_response(b'{"Data":[{"Name":"minutes"}],"Truncated":false}')


def test_response_parser_surfaces_truncation() -> None:
    documents, truncated, _ = module.parse_search_response(b'{"Data":[],"Truncated":true}')
    assert documents == []
    assert truncated is True
