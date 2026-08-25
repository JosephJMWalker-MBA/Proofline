from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_committee_minutes_content_audit_summary.json"
PLAN_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_committee_minutes_content_audit_plan.json"
SOURCE_RECEIPT_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_committee_minutes_document_retrieval_summary.json"


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def test_frozen_committee_minutes_content_audit_receipt_is_non_terminal_and_exact():
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_RECEIPT_PATH.read_text(encoding="utf-8"))

    assert receipt["schema"] == "proofline-akron-t21-committee-minutes-content-audit-receipt/v1"
    assert receipt["pre_observation_plan_commit"] == "4da562c21557b4ea683c2e0e13a18f48362ccd11"
    assert receipt["plan_sha256"] == sha256_json(plan) == "2802e732eca628494a567b264adb6cddb52c72ca21ede28b35769e09d772fc51"
    assert receipt["source_document_receipt_population_signature_sha256"] == source["stable_document_receipt_population_signature_sha256"]

    assert receipt["text_extraction"] == {
        "engine": "PyMuPDF",
        "literal_pattern_matching": "case-insensitive normalized whole phrase with alphanumeric boundaries",
        "ocr_used": False,
        "version": "1.28.2",
    }
    assert receipt["counts"] == {
        "document_count": 18,
        "documents_with_target_pages": 2,
        "page_count": 93,
        "target_block_count": 2,
        "target_page_count": 2,
        "terminal_candidate_block_count": 0,
    }
    assert [row["meeting_id"] for row in receipt["target_page_receipts"]] == [669, 671]
    assert [row["meeting_id"] for row in receipt["target_block_receipts"]] == [669, 671]
    assert receipt["anchor_block_counts"]["petition_label"] == 0
    assert receipt["anchor_block_counts"]["planning_case"] == 0
    assert receipt["procedural_phrase_block_counts"]["recommended_approval"] == 1
    assert receipt["procedural_phrase_block_counts"]["referred"] == 1
    assert receipt["procedural_phrase_block_counts"]["motion_for_passage"] == 0
    assert receipt["procedural_phrase_block_counts"]["final_passage"] == 0
    assert receipt["procedural_phrase_block_counts"]["declared_passed"] == 0
    assert receipt["terminal_candidate_blocks"] == []
    assert receipt["terminal_candidate_population_signature_sha256"] == "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"

    authority = receipt["authority_boundary"]
    assert authority["source_pdf_population_verified"] is True
    assert authority["target_block_locality_enforced"] is True
    assert authority["committee_recommendation_treated_as_final_council_disposition"] is False
    assert authority["terminal_outcome_assigned"] is False
    assert authority["absence_treated_as_disposition"] is False
    assert receipt["outcome"]["status"] == "unknown"
