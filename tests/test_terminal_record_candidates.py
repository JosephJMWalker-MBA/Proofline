import pytest

from proofline.terminal_record_candidates import (
    TERMINAL_RECORD_CANDIDATE_METHOD,
    extract_numbered_vote_record_candidates,
)


def test_extracts_numbered_ordinance_with_explicit_vote_without_outcome_assignment():
    text = """
ORDINANCE NO. 44-2026 authorizing the Mayor to enter into a contract; and declaring an emergency.
Vote: 12-0.
"""
    rows = extract_numbered_vote_record_candidates(text, evidence_id="agenda:669")
    assert len(rows) == 1
    row = rows[0]
    assert row.instrument_type == "ordinance"
    assert row.instrument_number == 44
    assert row.instrument_year == 2026
    assert row.vote_ayes == 12
    assert row.vote_nays == 0
    assert row.candidate_basis == "numbered_instrument_with_explicit_vote"
    assert row.terminal_outcome_assigned is False
    assert row.method == TERMINAL_RECORD_CANDIDATE_METHOD


def test_vote_arithmetic_does_not_assign_pass_or_fail_semantics():
    text = """
ORDINANCE NO. 99-2026 authorizing an example action.
Vote: 0-12.
"""
    row = extract_numbered_vote_record_candidates(text, evidence_id="agenda:test")[0]
    assert row.vote_ayes == 0
    assert row.vote_nays == 12
    assert row.terminal_outcome_assigned is False
    assert not hasattr(row, "outcome")
    assert not hasattr(row, "passed")


def test_extracts_multiple_numbered_records_without_cross_record_vote_leakage():
    text = """
ORDINANCE NO. 43-2026 first record.
Vote: 11-1.
RESOLUTION NO. 45-2026 second record.
Vote: 12-0.
"""
    rows = extract_numbered_vote_record_candidates(text, evidence_id="agenda:669")
    assert [(r.instrument_type, r.instrument_number, r.vote_ayes, r.vote_nays) for r in rows] == [
        ("ordinance", 43, 11, 1),
        ("resolution", 45, 12, 0),
    ]


def test_numbered_record_without_vote_fails_closed_even_if_next_record_has_vote():
    text = """
ORDINANCE NO. 43-2026 first record with no recorded vote here.
ORDINANCE NO. 44-2026 second record.
Vote: 12-0.
"""
    rows = extract_numbered_vote_record_candidates(text, evidence_id="agenda:669")
    assert [r.instrument_number for r in rows] == [44]


def test_new_legislation_boundary_prevents_vote_leakage_into_prior_numbered_record():
    text = """
ORDINANCE NO. 43-2026 prior record with no vote shown.
NEW LEGISLATION
ORDINANCE authorizing a pending action.
Vote: 12-0.
"""
    assert extract_numbered_vote_record_candidates(text, evidence_id="agenda:669") == ()


def test_extended_three_part_vote_not_partially_accepted_as_two_part_vote():
    text = "ORDINANCE NO. 44-2026 example.\nVote: 11-1-1."
    assert extract_numbered_vote_record_candidates(text, evidence_id="agenda:669") == ()


def test_unnumbered_pending_legislation_is_not_a_candidate():
    text = """
ORDINANCE authorizing a Conditional Use to establish a defense education training facility at 1928 Eastwood Avenue; and declaring an emergency.
Vote: 12-0.
"""
    assert extract_numbered_vote_record_candidates(text, evidence_id="agenda:pending") == ()


def test_free_form_mention_of_numbered_instrument_is_not_a_line_start_candidate():
    text = "Council discussed ORDINANCE NO. 44-2026 and Vote: 12-0 in narrative prose."
    assert extract_numbered_vote_record_candidates(text, evidence_id="notes:test") == ()


def test_candidate_id_is_deterministic_and_vote_sensitive():
    text = "ORDINANCE NO. 44-2026 example.\nVote: 12-0."
    first = extract_numbered_vote_record_candidates(text, evidence_id="agenda:669")[0]
    second = extract_numbered_vote_record_candidates(text, evidence_id="agenda:669")[0]
    changed = extract_numbered_vote_record_candidates(
        "ORDINANCE NO. 44-2026 example.\nVote: 11-1.", evidence_id="agenda:669"
    )[0]
    assert first.candidate_id == second.candidate_id
    assert first.candidate_id != changed.candidate_id


def test_evidence_id_required():
    with pytest.raises(ValueError):
        extract_numbered_vote_record_candidates("ORDINANCE NO. 1-2026 x. Vote: 1-0.", evidence_id="")


def test_non_string_text_rejected():
    with pytest.raises(TypeError):
        extract_numbered_vote_record_candidates(None, evidence_id="agenda:test")  # type: ignore[arg-type]
