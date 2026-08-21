from __future__ import annotations

import hashlib
import json
from pathlib import Path

from proofline.structured import extract_structured_facts


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"


def _load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def test_t14_preserves_exact_frozen_v2_contract() -> None:
    assert _git_blob_sha(EXPERIMENT / "akron-financial-representation-v2.json") == (
        "45e535ececb882f77293e7ddc757a83de1c9031d"
    )


def test_t13b_summary_preserves_blind_result_and_semantic_boundary() -> None:
    summary = _load("r1_t13b_blind_result_summary.json")
    assert summary["schema"] == "proofline-akron-t13b-blind-result-summary/v1"
    assert summary["workflow"]["run_id"] == 32440471169
    assert summary["workflow"]["artifact_id"] == 9432387690
    assert summary["workflow"]["artifact_digest"] == (
        "sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338"
    )
    representation = summary["representation"]
    assert representation["money_fact_count"] == 194
    assert representation["amount_type_known_fact_count"] == 70
    assert representation["fully_unknown_fact_count"] == 124
    assert representation["amount_type_known_fact_count"] + representation["fully_unknown_fact_count"] == 194
    boundary = summary["semantic_boundary"]
    assert boundary == {
        "detector_authorized": False,
        "event_identity_assigned": False,
        "independence_assessed": False,
        "lead_count": None,
    }


def test_t14_audits_every_non_unknown_amount_type_without_tuning_v2() -> None:
    audit = _load("r1_t14_known_amount_type_audit.json")
    assert audit["schema"] == "proofline-akron-t14-known-amount-type-audit/v1"
    assert audit["stage"] == "post_hoc_contextual_precision_audit"
    assert audit["ground_truth_status"] == "assistant_contextual_audit_not_human_ground_truth"
    assert audit["semantic_contract_changed"] is False
    assert audit["counts"] == {
        "supported": 25,
        "generic_by_design": 13,
        "contradicted": 32,
    }
    assert sum(audit["counts"].values()) == audit["source_evidence"]["amount_type_known_fact_count"] == 70
    assert audit["stage_decision"]["detector_authorization"] == "denied"
    assert audit["detector_authorized"] is False
    assert audit["event_identity_assigned"] is False
    assert audit["independence_assessed"] is False


def test_t14_fee_schedule_audit_exposes_flattened_table_error_class() -> None:
    audit = _load("r1_t14_known_amount_type_audit.json")
    groups = audit["fee_schedule_audit"]["groups"]
    assert len(groups) == 6
    assert sum(group["supported_count"] for group in groups) == 19
    assert sum(group["contradicted_count"] for group in groups) == 31
    assert sum(len(group["observed_money_tokens_in_text_order"]) for group in groups) == 50
    for group in groups:
        observed = group["observed_money_tokens_in_text_order"]
        supported = group["supported_filing_fee_tokens"]
        contradicted = group["contradicted_threshold_or_range_tokens_mislabeled_filing_fee"]
        assert group["supported_count"] == len(supported)
        assert group["contradicted_count"] == len(contradicted)
        assert len(observed) == len(supported) + len(contradicted)
        assert set(supported).isdisjoint(contradicted)


def test_t14_assessment_rate_assignment_is_directly_contradicted_by_label() -> None:
    finding = _load("r1_t14_known_amount_type_audit.json")["assessment_audit"]
    assert finding["assigned_amount_type"] == "assessment_rate"
    assert finding["raw_text"] == "$220,682.90"
    assert finding["finding"] == "contradicted"
    assert "CASH ASSESSED" in finding["evidence_excerpt"]
    assert "RATE PER LINEAR FOOT" in finding["evidence_excerpt"]


def test_explicit_v2_reproduces_new_partial_token_numeric_integrity_defect() -> None:
    text = "Estimated TOTAL Project Cost Applicable Fee\n$20,001___- $100,000"
    money = [
        fact
        for fact in extract_structured_facts(text, parser_version="proofline-structured/v2")
        if fact.fact_type == "money"
    ]
    assert (money[0].raw_text, money[0].normalized_text) == ("$20", "20.00")
    assert not any(fact.raw_text == "$20,001" for fact in money)

    observation = _load("r1_t14_known_amount_type_audit.json")[
        "new_numeric_integrity_observation"
    ]
    assert observation["frozen_v2_raw_text"] == "$20"
    assert observation["preserved_context_fragment"] == "$20,001___- $100,000"
