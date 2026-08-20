from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract() -> dict:
    return json.loads(
        (ROOT / "experiments" / "akron-2026" / "akron-money-role-contract-v1.json").read_text(
            encoding="utf-8"
        )
    )


def _classify(text: str, token: str, normalized: str) -> dict:
    module = _load_module(
        "experiments/akron-2026/evaluate_money_roles.py", "akron_money_role_evaluator"
    )
    start = text.index(token)
    return module.classify_money_role(
        _contract(),
        page_text=text,
        char_start=start,
        char_end=start + len(token),
        raw_text=token,
        normalized_text=normalized,
    )


def test_t9_derived_role_contract_reproduces_supported_context_roles() -> None:
    cases = [
        (
            "Top 1% of agents in the country by sales volume. Sold over $138MM since 2013, 466+ Lransactions",
            "$138MM",
            "138000000.00",
            "private_background_amount",
        ),
        (
            "Was this expenditure budgeted? City Expenditures City Receipts Amount: $51,780.00",
            "$51,780.00",
            "51780.00",
            "city_expenditure_amount",
        ),
        (
            "Project Code: 2025 Annual Plant Renewal. Total expenditure (if applicable): $ 51 ,780.00",
            "$ 51 ,780.00",
            "51780.00",
            "city_expenditure_amount",
        ),
        (
            "To allow the City to contract with Raftelis to support SpryCIS. This will be funded out of the OWDA loan. $ 853,000.00",
            "$ 853,000.00",
            "853000.00",
            "contract_amount",
        ),
        (
            "TYPE OF PROJECT Resurfacing CASH RESURFACING OTHER USE $11.25",
            "$11.25",
            "11.25",
            "assessment_rate",
        ),
        (
            "A filing schedule lists Estimated TOTAL Project Cost Applicable Fee $20,000 $250",
            "$20,000",
            "20000.00",
            "fee_schedule_threshold",
        ),
        (
            "A filing schedule lists Estimated TOTAL Project Cost Applicable Fee $20,000 $250",
            "$250",
            "250.00",
            "filing_fee_amount",
        ),
        (
            "3. Estimated TOTAL project cost: $400,000",
            "$400,000",
            "400000.00",
            "estimated_project_cost",
        ),
    ]

    for text, token, normalized, role in cases:
        result = _classify(text, token, normalized)
        assert result["role"] == role
        assert result["rule_id"] is not None


def test_known_money_value_without_required_context_stays_unclassified() -> None:
    result = _classify("General reference amount: $250", "$250", "250.00")
    assert result["role"] == "unclassified_money"
    assert result["rule_id"] is None


def test_contract_language_without_funding_context_stays_unclassified() -> None:
    result = _classify(
        "A private narrative mentions a contract with a vendor for $853,000.",
        "$853,000",
        "853000.00",
    )
    assert result["role"] == "unclassified_money"


def test_role_classifier_rejects_detached_or_shifted_token_anchor() -> None:
    module = _load_module(
        "experiments/akron-2026/evaluate_money_roles.py", "akron_money_role_anchor"
    )
    text = "Estimated TOTAL project cost: $400,000"
    start = text.index("$400,000")
    with pytest.raises(ValueError, match="preferred Silver anchor"):
        module.classify_money_role(
            _contract(),
            page_text=text,
            char_start=start,
            char_end=start + len("$400,000"),
            raw_text="$500,000",
            normalized_text="500000.00",
        )


def test_contract_keeps_detector_authorization_off_and_unclassified_default() -> None:
    module = _load_module(
        "experiments/akron-2026/evaluate_money_roles.py", "akron_money_role_contract"
    )
    contract = _contract()
    module.validate_contract(contract)
    assert contract["detector_authorized"] is False
    assert contract["default_role"] == "unclassified_money"


def test_frozen_selection_resolves_by_source_identity_hash_only() -> None:
    module = _load_module(
        "experiments/akron-2026/sync_frozen_attachment_selection.py",
        "akron_frozen_attachment_selection",
    )
    resources = [
        {
            "source_uri": f"https://records.example.gov/Documents/DownloadFile/{index}.pdf",
            "source_name": f"Fixture {index}",
            "native_identifier": f"fixture-{index}",
            "expected_media_type": "application/pdf",
            "fetch_strategy": "onbase_download_bytes",
        }
        for index in range(40)
    ]
    ranked = sorted(
        resources,
        key=lambda item: (
            hashlib.sha256(item["source_uri"].encode("utf-8")).hexdigest(),
            item["source_uri"],
        ),
    )
    hashes = [hashlib.sha256(item["source_uri"].encode("utf-8")).hexdigest() for item in ranked]
    selection = {
        "schema": "proofline-akron-t11-disjoint-source-set/v1",
        "excluded": {"source_uri_sha256": hashes[:8]},
        "selected": {"source_uri_sha256": hashes[8:32]},
    }

    selected, metadata = module.resolve_selection(
        {"resources": list(reversed(resources))}, selection
    )

    assert [item["source_uri"] for item in selected] == [item["source_uri"] for item in ranked[8:32]]
    assert metadata["live_excluded_ranks"] == list(range(1, 9))
    assert metadata["live_selected_ranks"] == list(range(9, 33))
    assert set(metadata["excluded_source_hashes"]).isdisjoint(metadata["selected_source_hashes"])
