from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proofline.public_record_request_scope import build_request_packet

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXP / name).read_text())


def policy_contract() -> dict:
    return {
        "schema": "proofline-akron-public-record-request-policy-contract/v1",
        "policy_url": "https://www.akronohio.gov/departments/law/index.php",
        "recipient": "publicrecords@akronohio.gov",
        "law_department_oversees_requests_verified": True,
        "records_only_instruction_verified": True,
        "email_submission_path_verified": True,
    }


def build() -> dict:
    return build_request_packet(
        load("r1_t21_clerk_public_record_request_plan.json"),
        load("r1_t21_section38_positive_search_summary.json"),
        load("r1_t21_terminal_record_target.json"),
        policy_contract(),
    )


def test_packet_is_records_only_and_unsent() -> None:
    packet = build()
    assert packet["delivery"]["recipient"] == "publicrecords@akronohio.gov"
    assert len(packet["requested_existing_record_categories"]) == 4
    assert packet["submission_state"]["submitted"] is False
    assert packet["submission_state"]["send_authorized"] is False
    assert packet["outcome"]["status"] == "unknown"
    assert packet["response_semantics"]["no_responsive_records_is_terminal"] is False
    assert "existing records only" in packet["delivery"]["body"]
    assert "does not ask the City to create a new record" in packet["delivery"]["body"]


def test_plan_recipient_drift_fails_closed() -> None:
    plan = load("r1_t21_clerk_public_record_request_plan.json")
    plan["submission_policy"]["recipient"] = "someone@example.com"
    with pytest.raises(ValueError, match="recipient drifted"):
        build_request_packet(
            plan,
            load("r1_t21_section38_positive_search_summary.json"),
            load("r1_t21_terminal_record_target.json"),
            policy_contract(),
        )


def test_no_records_cannot_become_terminal() -> None:
    plan = load("r1_t21_clerk_public_record_request_plan.json")
    plan["response_semantics"]["no_responsive_records_is_terminal"] = True
    with pytest.raises(ValueError, match="non-terminal semantics drifted"):
        build_request_packet(
            plan,
            load("r1_t21_section38_positive_search_summary.json"),
            load("r1_t21_terminal_record_target.json"),
            policy_contract(),
        )


def test_request_horizon_cannot_expand_silently() -> None:
    plan = load("r1_t21_clerk_public_record_request_plan.json")
    plan["target_identity"]["date_range_end"] = "2026-09-30"
    with pytest.raises(ValueError, match="horizon drifted"):
        build_request_packet(
            plan,
            load("r1_t21_section38_positive_search_summary.json"),
            load("r1_t21_terminal_record_target.json"),
            policy_contract(),
        )


def test_upstream_terminal_positive_blocks_fallback_request() -> None:
    section38 = copy.deepcopy(load("r1_t21_section38_positive_search_summary.json"))
    section38["counts"]["section38_terminal_positive_candidate_count"] = 1
    with pytest.raises(ValueError, match="invalid after a Section 38 terminal-positive"):
        build_request_packet(
            load("r1_t21_clerk_public_record_request_plan.json"),
            section38,
            load("r1_t21_terminal_record_target.json"),
            policy_contract(),
        )
