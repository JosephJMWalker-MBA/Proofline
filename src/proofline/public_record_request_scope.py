from __future__ import annotations

import hashlib
import json
from typing import Any

PLAN_SCHEMA = "proofline-akron-t21-clerk-public-record-request-plan/v1"
SECTION38_SCHEMA = "proofline-akron-t21-section38-positive-search-receipt/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"
PACKET_SCHEMA = "proofline-public-record-request-packet/v1"

EXPECTED_RECIPIENT = "publicrecords@akronohio.gov"
EXPECTED_POLICY_URL = "https://www.akronohio.gov/departments/law/index.php"
EXPECTED_CATEGORY_IDS = [
    "legislative_identity_index",
    "legislation_versions",
    "final_disposition_or_closure",
    "clerk_status_record",
]


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def validate_upstream(plan: dict, section38: dict, target: dict, policy_contract: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected Clerk request plan schema")
    if section38.get("schema") != SECTION38_SCHEMA:
        raise ValueError("unexpected Section 38 receipt schema")
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError("unexpected target schema")
    if str(section38.get("outcome", {}).get("status", "")).lower() != "unknown":
        raise ValueError("request-scope stage requires upstream outcome Unknown")
    if section38.get("counts", {}).get("section38_terminal_positive_candidate_count") != 0:
        raise ValueError("Clerk request fallback is invalid after a Section 38 terminal-positive candidate")
    if plan.get("base_continuity", {}).get("merge_commit") != "03d0fad062dc7adc6882f221b7b26b7a69523bce":
        raise ValueError("request plan is not anchored to merged #111")

    submission = plan.get("submission_policy", {})
    if submission.get("recipient") != EXPECTED_RECIPIENT:
        raise ValueError("public-record request recipient drifted")
    if submission.get("policy_url") != EXPECTED_POLICY_URL:
        raise ValueError("public-record request policy URL drifted")
    if policy_contract.get("recipient") != EXPECTED_RECIPIENT:
        raise ValueError("live policy contract recipient drifted")
    if policy_contract.get("policy_url") != EXPECTED_POLICY_URL:
        raise ValueError("live policy contract URL drifted")
    if policy_contract.get("records_only_instruction_verified") is not True:
        raise ValueError("live policy contract no longer says to identify records sought")

    identity = plan.get("target_identity", {})
    if identity.get("planning_case") != target.get("planning_case", {}).get("normalized_key"):
        raise ValueError("planning-case identity drifted")
    if identity.get("ordinance_title") != target.get("ordinance_title"):
        raise ValueError("ordinance-title identity drifted")
    if identity.get("address") != "1928 Eastwood Avenue":
        raise ValueError("address identity drifted")
    if identity.get("petitioner") != "David Walker" or identity.get("petition_label") != "D-14":
        raise ValueError("petition identity drifted")
    if identity.get("date_range_start") != "2026-02-09" or identity.get("date_range_end") != "2026-08-25":
        raise ValueError("bounded request horizon drifted")

    categories = plan.get("requested_existing_record_categories", [])
    if [row.get("id") for row in categories] != EXPECTED_CATEGORY_IDS:
        raise ValueError("requested record categories drifted")
    if len({row.get("id") for row in categories}) != len(EXPECTED_CATEGORY_IDS):
        raise ValueError("duplicate request category")

    body = plan.get("request_body", "")
    required_body_literals = [
        "PC-2025-80-CU",
        "D-14",
        "David Walker",
        "1928 Eastwood Avenue",
        target["ordinance_title"],
        "February 9, 2026 through August 25, 2026",
        "existing records only",
        "does not ask the City to create a new record",
        "provide a legal conclusion",
        "answer an interrogatory",
    ]
    missing = [literal for literal in required_body_literals if literal not in body]
    if missing:
        raise ValueError(f"request body lost required scope literals: {missing}")

    semantics = plan.get("response_semantics", {})
    required_false = [
        "assigned_number_alone_is_terminal",
        "no_responsive_records_is_terminal",
        "partial_production_is_exhaustive_without_explicit_custodian_statement",
        "referral_or_forwarding_is_terminal",
        "delay_or_no_response_is_terminal",
        "redaction_or_exemption_is_terminal",
        "different_matter_record_is_target_evidence",
    ]
    if any(semantics.get(key) is not False for key in required_false):
        raise ValueError("future-response non-terminal semantics drifted")
    if semantics.get("responsive_terminal_record_may_be_reviewed_for_disposition") is not True:
        raise ValueError("responsive-record review boundary drifted")

    boundary = plan.get("authority_boundary", {})
    for key in (
        "request_submitted_in_this_stage",
        "email_send_authorized",
        "future_response_interpreted_in_this_stage",
        "absence_treated_as_disposition",
        "terminal_outcome_assigned",
        "causality_assigned",
        "detector_or_lead_semantics_authorized",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"request-scope authority boundary drifted: {key}")


def build_request_packet(plan: dict, section38: dict, target: dict, policy_contract: dict) -> dict:
    validate_upstream(plan, section38, target, policy_contract)
    packet = {
        "schema": PACKET_SCHEMA,
        "delivery": {
            "method": "email",
            "recipient": plan["submission_policy"]["recipient"],
            "policy_url": plan["submission_policy"]["policy_url"],
            "subject": plan["request_subject"],
            "body": plan["request_body"],
            "electronic_delivery_requested_if_available": True,
        },
        "target_identity": plan["target_identity"],
        "requested_existing_record_categories": plan["requested_existing_record_categories"],
        "response_semantics": plan["response_semantics"],
        "submission_state": {
            "submitted": False,
            "send_authorized": False,
            "recipient_verified_from_live_city_policy": True,
            "records_only_scope_verified": True,
        },
        "authority_boundary": plan["authority_boundary"],
        "outcome": {
            "status": "unknown",
            "reason": "This packet governs a future records request only. No request has been submitted and no future custodian response is interpreted in this stage.",
        },
    }
    packet["request_scope_signature_sha256"] = sha256_json({
        "target_identity": packet["target_identity"],
        "requested_existing_record_categories": packet["requested_existing_record_categories"],
        "response_semantics": packet["response_semantics"],
    })
    packet["delivery_signature_sha256"] = sha256_json(packet["delivery"])
    return packet
