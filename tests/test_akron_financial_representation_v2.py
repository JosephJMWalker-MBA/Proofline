from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "experiments" / "akron-2026" / "financial_representation_v2.py"
    spec = importlib.util.spec_from_file_location("akron_financial_representation_v2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract() -> dict:
    return json.loads(
        (
            ROOT
            / "experiments"
            / "akron-2026"
            / "akron-financial-representation-v2.json"
        ).read_text(encoding="utf-8")
    )


def _represent(
    text: str,
    token: str,
    normalized: str,
    *,
    source_name: str = "",
) -> dict:
    module = _load_module()
    start = text.index(token)
    return module.represent_money_fact(
        _contract(),
        page_text=text,
        char_start=start,
        char_end=start + len(token),
        raw_text=token,
        normalized_text=normalized,
        source_name=source_name,
    )


def _json_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _json_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_keys(child)


@pytest.mark.parametrize(
    ("text", "token", "normalized", "source_name", "scope", "context_type", "amount_type"),
    [
        (
            "Top 1% of agents in the country by sales volume. Sold over $138MM since 2013, 466+ transactions",
            "$138MM",
            "138000000.00",
            "",
            "private_background",
            "private_background",
            "private_background_amount",
        ),
        (
            "To allow the City to contract with Raftelis to support SpryCIS. "
            "This will be funded out of the OWDA loan. $ 853,000.00",
            "$ 853,000.00",
            "853000.00",
            "",
            "akron_municipal_record_context",
            "contract",
            "contract_amount",
        ),
        (
            "TYPE OF PROJECT Resurfacing RESURFACING OTHER USE $11.25 CASH ASSESSED: 205,010.28",
            "$11.25",
            "11.25",
            "",
            "akron_municipal_record_context",
            "assessment",
            "assessment_rate",
        ),
        (
            "3. Estimated TOTAL project cost: $400,000",
            "$400,000",
            "400000.00",
            "",
            "akron_municipal_record_context",
            "project_estimate",
            "estimated_project_cost",
        ),
        (
            "Was this expenditure budgeted? City Expenditures City Receipts Amount: $51,780.00",
            "$51,780.00",
            "51780.00",
            "",
            "akron_municipal_record_context",
            "municipal_financial_form",
            "city_expenditure_amount",
        ),
        (
            "Planning Commission Filing Faes Chart Conditional Use Request "
            "Estimated TOT AL Project Cost $O - $5,000 $5,001 - $20,000 "
            "See the following table: Applicable Fee $100 $150 $300",
            "$5,000",
            "5000.00",
            "",
            "akron_municipal_record_context",
            "fee_schedule",
            "fee_schedule_threshold",
        ),
        (
            "Planning Commission Filing Faes Chart Conditional Use Request "
            "Estimated TOT AL Project Cost $O - $5,000 $5,001 - $20,000 "
            "See the following table: Applicable Fee $100 $150 $300",
            "$100",
            "100.00",
            "",
            "akron_municipal_record_context",
            "fee_schedule",
            "filing_fee_amount",
        ),
        (
            "The agency wishes to acquire vacant City property. "
            "The purchase price of $171 represents a cost of $0.05 per square foot.",
            "$171",
            "171.00",
            "",
            "akron_municipal_record_context",
            "property_transaction",
            "purchase_price",
        ),
        (
            "The agency wishes to acquire vacant City property. "
            "The purchase price of $171 represents a cost of $0.05 per square foot.",
            "$0.05",
            "0.05",
            "",
            "akron_municipal_record_context",
            "property_transaction",
            "unit_rate",
        ),
        (
            "Financial Data: Additional Current Estimate Appropriation Over Budgeted Cost "
            "of Cost Budgeted Cost Current Request: Funding Source Amount Local $95,870,555 "
            "Regional $1,937,920 Total $341,909,940",
            "$95,870,555",
            "95870555.00",
            "",
            "akron_municipal_record_context",
            "municipal_financial_form",
            "municipal_form_amount",
        ),
        (
            "Financial Data: Additional Current Estimate Appropriation Over Budgeted Cost "
            "of Cost Budgeted Cost Current Request: Funding Source Amount Local $95,870,555 "
            "Regional $1,937,920 Total $341,909,940",
            "$341,909,940",
            "341909940.00",
            "",
            "akron_municipal_record_context",
            "municipal_financial_form",
            "total_project_amount",
        ),
        (
            "Budgeting $4 million for both police and fire overtime costs for about $8 million total.",
            "$4",
            "4.00",
            "Responses to questions on Executive Summary",
            "akron_municipal_record_context",
            "municipal_budget_narrative",
            "budget_narrative_amount",
        ),
        (
            "Phoenix Fire Department - dealing with a $36M city budget shortfall, "
            "with rising call volume and staffing demands.",
            "$36M",
            "36000000.00",
            "The Big Picture for Metro Fire Departments Nationally",
            "external_reference",
            "external_comparison",
            "external_comparative_amount",
        ),
        (
            "This grant would cover the cost of a zipline. "
            "There is a cash match of $15,025 being met by pledges donations.",
            "$15,025",
            "15025.00",
            "",
            "akron_municipal_record_context",
            "grant_project",
            "grant_cash_match_amount",
        ),
        (
            "This grant would cover the cost of a zipline and new swings. "
            "Project worksheet amount $60,100.00",
            "$60,100.00",
            "60100.00",
            "",
            "akron_municipal_record_context",
            "grant_project",
            "grant_context_amount",
        ),
    ],
)
def test_v2_representation_reproduces_development_context_facets(
    text: str,
    token: str,
    normalized: str,
    source_name: str,
    scope: str,
    context_type: str,
    amount_type: str,
) -> None:
    result = _represent(text, token, normalized, source_name=source_name)
    assert result["scope"] == scope
    assert result["context_type"] == context_type
    assert result["amount_type"] == amount_type
    assert result["context_rule_id"] is not None
    assert result["amount_rule_id"] is not None
    assert result["detector_authorized"] is False
    assert result["event_identity_assigned"] is False
    assert result["independence_assessed"] is False


def test_v2_does_not_classify_known_amount_without_semantic_context() -> None:
    result = _represent("General reference amount: $250", "$250", "250.00")
    assert result["scope"] == "unknown"
    assert result["context_type"] == "unknown"
    assert result["amount_type"] == "unknown"
    assert result["context_rule_id"] is None
    assert result["amount_rule_id"] is None


def test_v2_does_not_promote_generic_private_contract_language() -> None:
    result = _represent(
        "A private narrative mentions a contract with a vendor for $853,000.",
        "$853,000",
        "853000.00",
    )
    assert result["context_type"] == "unknown"
    assert result["amount_type"] == "unknown"


def test_v2_fee_schedule_generalizes_by_structure_not_amount_whitelist() -> None:
    contract = _contract()
    serialized = json.dumps(contract, sort_keys=True)
    assert "numeric_in" not in serialized

    text = (
        "Planning Commission Filing Fees Chart Estimated TOTAL Project Cost "
        "$1 - $12,345 $12,346 - more Applicable Fee $77 $888"
    )
    threshold = _represent(text, "$12,345", "12345.00")
    fee = _represent(text, "$888", "888.00")
    assert threshold["amount_type"] == "fee_schedule_threshold"
    assert fee["amount_type"] == "filing_fee_amount"


def test_v2_rejects_detached_money_anchor() -> None:
    module = _load_module()
    text = "Estimated TOTAL project cost: $400,000"
    start = text.index("$400,000")
    with pytest.raises(ValueError, match="preferred Silver anchor"):
        module.represent_money_fact(
            _contract(),
            page_text=text,
            char_start=start,
            char_end=start + len("$400,000"),
            raw_text="$500,000",
            normalized_text="500000.00",
        )


def test_v2_contract_cannot_authorize_event_or_detector_semantics() -> None:
    module = _load_module()
    contract = _contract()
    module.validate_contract(contract)
    assert contract["detector_authorized"] is False
    assert contract["event_identity_assigned"] is False
    assert contract["independence_assessed"] is False

    tampered = json.loads(json.dumps(contract))
    tampered["detector_authorized"] = True
    with pytest.raises(ValueError, match="detector_authorized"):
        module.validate_contract(tampered)


def test_t13_holdout_is_frozen_disjoint_and_content_blind() -> None:
    payload = json.loads(
        (
            ROOT
            / "experiments"
            / "akron-2026"
            / "r1_t13_disjoint_attachment_sources.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["schema"] == "proofline-akron-t13-disjoint-source-set/v1"
    assert payload["content_inspection_status"] == "not_inspected_at_freeze"
    assert payload["excluded"]["count"] == 32
    assert payload["excluded"]["original_manifest_ranks"] == [1, 32]
    assert payload["selected"]["count"] == 32
    assert payload["selected"]["original_manifest_ranks"] == [33, 64]

    excluded = payload["excluded"]["source_uri_sha256"]
    selected = payload["selected"]["source_uri_sha256"]
    assert len(excluded) == len(set(excluded)) == 32
    assert len(selected) == len(set(selected)) == 32
    assert set(excluded).isdisjoint(selected)
    assert excluded == sorted(excluded)
    assert selected == sorted(selected)
    assert all(len(value) == 64 for value in [*excluded, *selected])

    keys = set(_json_keys(payload))
    assert "source_uri" not in keys
    assert "source_name" not in keys
    assert "document_text" not in keys
