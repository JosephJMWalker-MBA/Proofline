from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def test_frozen_clerk_request_scope_receipt() -> None:
    receipt = json.loads((EXP / "r1_t21_clerk_public_record_request_scope_summary.json").read_text())
    assert receipt["schema"] == "proofline-akron-t21-clerk-public-record-request-scope-receipt/v1"
    assert receipt["submission_performed"] is False
    packet = receipt["request_packet"]
    assert packet["delivery"]["recipient"] == "publicrecords@akronohio.gov"
    assert packet["delivery_signature_sha256"] == "2a0e561f620bfbbbb18e17266c0d405ccbfea0f64381c254ccac2293a3044b39"
    assert packet["request_scope_signature_sha256"] == "3fa66ea6f290905ec98626fd667e8073a383a96a9d4908deedbbe324b382bf64"
    assert receipt["measurement_signature_sha256"] == "6a367c1a97fac96cd4579dc6a5968bda55bcbb7e55ece7ec314fa2631845c771"
    assert len(packet["requested_existing_record_categories"]) == 4
    assert packet["submission_state"] == {
        "submitted": False,
        "send_authorized": False,
        "recipient_verified_from_live_city_policy": True,
        "records_only_scope_verified": True,
    }
    assert packet["response_semantics"]["no_responsive_records_is_terminal"] is False
    assert packet["response_semantics"]["assigned_number_alone_is_terminal"] is False
    assert packet["response_semantics"]["partial_production_is_exhaustive_without_explicit_custodian_statement"] is False
    assert packet["outcome"]["status"] == "unknown"
    assert receipt["interpretation"]["request_ready_for_separate_submission_stage"] is True
    assert receipt["interpretation"]["request_submitted"] is False
