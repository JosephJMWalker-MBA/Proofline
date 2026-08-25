from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "measure_t21_public_access_eastwood_search.py"

spec = importlib.util.spec_from_file_location("t21_public_access_search_receipt", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def test_frozen_public_access_eastwood_search_receipt() -> None:
    receipt = load("r1_t21_public_access_eastwood_search_summary.json")
    plan = load("r1_t21_public_access_eastwood_search_plan.json")
    source = load("r1_t21_public_access_source_contract_summary.json")
    target = load("r1_t21_terminal_record_target.json")

    assert receipt["schema"] == "proofline-akron-t21-public-access-eastwood-search-receipt/v1"
    assert receipt["stage"] == "post_measurement_pre_document_retrieval_receipt"
    assert receipt["plan"]["sha256"] == module.sha256_json(plan)
    assert receipt["plan"]["eastwood_request_count"] == 2
    assert receipt["plan"]["post_result_term_expansion_allowed"] is False

    assert receipt["source_contract"] == {
        "schema": source["schema"],
        "api_root": source["configuration"]["api_root"],
        "query_id": source["passed_legislation_query"]["id"],
        "query_name": source["passed_legislation_query"]["name"],
        "title_clause_keyword_id": "103",
        "ordinance_number_keyword_id": "102",
        "query_limit": source["configuration"]["query_limit"],
    }
    assert receipt["target"] == {
        "planning_case": target["planning_case"]["normalized_key"],
        "ordinance_title_sha256": target["ordinance_title_sha256"],
    }

    assert [row["request_id"] for row in receipt["eastwood_searches"]] == list(
        module.EXPECTED_REQUEST_IDS
    )
    assert [row["value"] for row in receipt["eastwood_searches"]] == list(
        module.EXPECTED_VALUES
    )
    for row in receipt["eastwood_searches"]:
        assert row["response_byte_size"] == 51
        assert row["response_sha256"] == "d067f87ce53dffb0023494b905888c578296914d68b0dd22b5a3210e50863aa9"
        assert row["returned_document_count"] == 0
        assert row["truncated"] is False

    assert receipt["candidate_population"] == {
        "count": 0,
        "signature_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "positive_control_excluded": True,
    }

    control = receipt["positive_control"]
    assert control["control_id"] == module.EXPECTED_CONTROL_ID
    assert control["required_document_name_prefix"] == "O-44-2026 -"
    assert control["specific_known_record_returned"] is True
    assert control["excluded_from_eastwood_candidate_population"] is True
    assert control["opaque_document_tokens_intentionally_not_pinned"] is True

    assert receipt["authority_boundary"]["terminal_outcome_assigned"] is False
    assert receipt["authority_boundary"]["absence_treated_as_disposition"] is False
    assert receipt["authority_boundary"]["returned_document_dereferenced"] is False
    assert receipt["outcome"]["status"] == "unknown"

    guards = receipt["receipt_guards"]
    assert guards["eastwood_empty_response_bytes_pinned"] is True
    assert guards["positive_control_specific_human_readable_record_required"] is True
    assert guards["positive_control_opaque_tokens_not_pinned"] is True
    assert guards["canonical_raw_measurement_preserved_for_provenance_but_not_exactly_replayed"] is True
