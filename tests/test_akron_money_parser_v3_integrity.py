from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"


def _load_measure_module():
    path = EXPERIMENT / "measure_money_parser_v3_delta.py"
    spec = importlib.util.spec_from_file_location("akron_t15_money_parser_v3_delta", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t15_t13b_population_delta_is_exactly_one_fail_closed_removal() -> None:
    module = _load_measure_module()
    result = module.measure(EXPERIMENT / "r1_t13b_money_anchor_fixture.json")

    assert result["old_parser_version"] == "proofline-structured/v2"
    assert result["new_parser_version"] == "proofline-structured/v3"
    assert result["fact_count"] == 194
    assert result["unchanged_fact_count"] == 193
    assert result["removed_fact_count"] == 1
    assert result["changed_fact_count"] == 0
    assert result["changed"] == []
    assert result["removed"][0]["old_raw_text"] == "$20"
    assert "$20,001___" in result["removed"][0]["snippet"]
    assert result["semantic_contract_changed"] is False
    assert result["detector_authorized"] is False
    assert result["lead_count"] is None


def test_t15_fixture_is_explicitly_already_opened_evidence() -> None:
    module = _load_measure_module()
    result = module.measure(EXPERIMENT / "r1_t13b_money_anchor_fixture.json")

    provenance = result["fixture"]["provenance"]
    assert provenance["stage"] == "already_opened_t13b_evidence_derivative"
    assert provenance["workflow_run_id"] == 32440471169
    assert provenance["workflow_artifact_id"] == 9432387690
    assert provenance["workflow_artifact_digest"] == (
        "sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338"
    )
