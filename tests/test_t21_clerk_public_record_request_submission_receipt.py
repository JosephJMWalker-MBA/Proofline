from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_submission_receipt_matches_frozen_scope_and_no_response_semantics() -> None:
    scope = json.loads((EXP / "r1_t21_clerk_public_record_request_scope_summary.json").read_text())
    receipt = json.loads((EXP / "r1_t21_clerk_public_record_request_submission_summary.json").read_text())

    assert receipt["schema"] == "proofline-akron-t21-clerk-public-record-request-submission-receipt/v1"
    assert receipt["base_continuity"]["merged_pr"] == 112
    assert receipt["base_continuity"]["request_scope_signature_sha256"] == scope["request_packet"]["request_scope_signature_sha256"]
    assert receipt["base_continuity"]["delivery_signature_sha256"] == scope["request_packet"]["delivery_signature_sha256"]

    sent = receipt["submission"]
    delivery = scope["request_packet"]["delivery"]
    assert sent["recipient"] == delivery["recipient"]
    assert sent["subject"] == delivery["subject"]
    assert sent["subject_sha256"] == sha256_text(delivery["subject"])
    assert sent["body_sha256"] == sha256_text(delivery["body"])
    assert sent["gmail_message_id"] == "1a039e0ad7fd78b4"
    assert sent["gmail_thread_id"] == "1a039e0ad7fd78b4"
    assert sent["sent_at"] == "2026-08-25T13:03:40-04:00"
    assert sent["labels"] == ["SENT"]
    assert sent["cc"] == []
    assert sent["bcc"] == []
    assert sent["has_attachment"] is False
    assert sent["submission_successful"] is True

    boundary = receipt["authority_boundary"]
    assert boundary["request_submitted"] is True
    assert boundary["duplicate_send_authorized"] is False
    assert boundary["response_interpreted"] is False
    assert boundary["response_polled_in_this_stage"] is False
    assert boundary["absence_treated_as_disposition"] is False
    assert boundary["terminal_outcome_assigned"] is False
    assert receipt["outcome"]["status"] == "unknown"
