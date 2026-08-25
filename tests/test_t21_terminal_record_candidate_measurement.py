import importlib.util
from pathlib import Path

from proofline.onbase import OnBaseAgendaPlan
from proofline.terminal_record_candidates import extract_numbered_vote_record_candidates

SCRIPT = Path("experiments/akron-2026/measure_t21_terminal_record_candidates.py")
_spec = importlib.util.spec_from_file_location("t21_terminal_candidates", SCRIPT)
assert _spec and _spec.loader
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)

TARGET = {
    "schema": module.TARGET_SCHEMA,
    "planning_case": {"kind": "planning_case", "normalized_key": "PC-2025-80-CU"},
    "ordinance_title": "ORDINANCE authorizing a Conditional Use to establish a defense education training facility at 1928 Eastwood Avenue; and declaring an emergency.",
    "ordinance_title_sha256": "1c34ab1c1907c9d7d31a90b7e57cf7d0bc6b040a816c9b9a854b60ba1a33a421",
    "introduced_on_or_after": "2026-02-23",
}


def _candidate(text: str):
    rows = extract_numbered_vote_record_candidates(text, evidence_id="marked-agenda:test")
    assert len(rows) == 1
    return rows[0]


def test_exact_eastwood_numbered_ordinance_is_relationship_match_not_outcome():
    row = _candidate(
        "ORDINANCE NO. 144-2026 authorizing a Conditional Use to establish a defense education "
        "training facility at 1928 Eastwood Avenue; and declaring an emergency.\nVote: 12-0."
    )
    assert module.candidate_matches_target(row, TARGET) is True
    assert row.terminal_outcome_assigned is False


def test_resolution_with_same_words_is_not_target_match():
    row = _candidate(
        "RESOLUTION NO. 144-2026 authorizing a Conditional Use to establish a defense education "
        "training facility at 1928 Eastwood Avenue; and declaring an emergency.\nVote: 12-0."
    )
    assert module.candidate_matches_target(row, TARGET) is False


def test_near_match_fails_closed():
    row = _candidate(
        "ORDINANCE NO. 144-2026 authorizing a Conditional Use to establish a defense training "
        "facility at 1928 Eastwood Avenue; and declaring an emergency.\nVote: 12-0."
    )
    assert module.candidate_matches_target(row, TARGET) is False


def test_target_hash_drift_fails_closed():
    row = _candidate(
        "ORDINANCE NO. 144-2026 authorizing a Conditional Use to establish a defense education "
        "training facility at 1928 Eastwood Avenue; and declaring an emergency.\nVote: 12-0."
    )
    changed = dict(TARGET)
    changed["ordinance_title_sha256"] = "0" * 64
    try:
        module.candidate_matches_target(row, changed)
    except ValueError as exc:
        assert "hash" in str(exc)
    else:
        raise AssertionError("target hash drift must fail closed")


def test_agenda_pdf_uri_uses_only_publisher_declared_unique_name_and_meeting_id():
    plan = OnBaseAgendaPlan(
        name="akron",
        source_uri="https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/Meetings",
        meeting_type_ids=(101,),
        years=(2026,),
    )
    uri = module.agenda_pdf_uri(
        plan,
        meeting_id=669,
        agenda_unique_name="February 23, 2026 669 Agenda 2 23 2026 6 30 00 PM",
    )
    assert uri.startswith(
        "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/Documents/DownloadFile/"
    )
    assert "February%2023%2C%202026%20669%20Agenda" in uri
    assert uri.endswith(".pdf?documentType=1&meetingId=669")


def test_target_spec_requires_exact_case_and_title_hash():
    assert module._validate_target(TARGET).isoformat() == "2026-02-23"
    wrong_case = dict(TARGET)
    wrong_case["planning_case"] = {"kind": "planning_case", "normalized_key": "PC-OTHER"}
    try:
        module._validate_target(wrong_case)
    except ValueError as exc:
        assert "PC-2025-80-CU" in str(exc)
    else:
        raise AssertionError("wrong planning-case target must fail closed")
