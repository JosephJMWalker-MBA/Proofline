import pytest

from proofline.agenda_status import (
    AGENDA_STATUS_METHOD,
    classify_agenda_status_label,
)


def test_time_is_procedural_hold_not_terminal_outcome():
    status = classify_agenda_status_label("TIME:", evidence_id="evidence:agenda:675")
    assert status is not None
    assert status.normalized_status == "time"
    assert status.procedural_category == "hold"
    assert status.terminal_outcome_assigned is False
    assert status.method == AGENDA_STATUS_METHOD


def test_referred_is_procedural_referral_not_terminal_outcome():
    status = classify_agenda_status_label("REFERRED:", evidence_id="evidence:agenda:685")
    assert status is not None
    assert status.normalized_status == "referred"
    assert status.procedural_category == "referral"
    assert status.terminal_outcome_assigned is False


def test_first_reading_public_hearing_label_is_bounded_and_normalized():
    status = classify_agenda_status_label(
        "FIRST READING AND REFERRED: UP FOR PUBLIC HEARING APRIL 6, 2026:",
        evidence_id="evidence:agenda:675",
    )
    assert status is not None
    assert status.normalized_status == "first_reading_referred_public_hearing"
    assert status.procedural_category == "referral"
    assert status.terminal_outcome_assigned is False


def test_public_hearing_label_is_procedural_not_proof_meeting_occurred():
    status = classify_agenda_status_label(
        "UP FOR PUBLIC HEARING MARCH 9, 2026:",
        evidence_id="evidence:agenda:671",
    )
    assert status is not None
    assert status.normalized_status == "public_hearing"
    assert status.procedural_category == "hearing"
    assert status.terminal_outcome_assigned is False


def test_unknown_or_terminal_sounding_text_fails_closed():
    for label in (
        "PASSED",
        "APPROVED",
        "DENIED",
        "WITHDRAWN",
        "TIME TO APPROVE",
        "This item was referred last week",
    ):
        assert (
            classify_agenda_status_label(label, evidence_id="evidence:agenda:x")
            is None
        )


def test_no_items_is_section_metadata_not_outcome():
    status = classify_agenda_status_label("NO ITEMS", evidence_id="evidence:agenda:675")
    assert status is not None
    assert status.normalized_status == "no_items"
    assert status.procedural_category == "empty_section"
    assert status.terminal_outcome_assigned is False


def test_whitespace_and_case_are_normalized_without_fuzzy_matching():
    status = classify_agenda_status_label("  time :  ", evidence_id="evidence:agenda:1")
    assert status is not None
    assert status.normalized_status == "time"


def test_status_ids_are_deterministic():
    first = classify_agenda_status_label("TIME:", evidence_id="evidence:agenda:1")
    second = classify_agenda_status_label("TIME:", evidence_id="evidence:agenda:1")
    assert first == second


def test_requires_evidence_id():
    with pytest.raises(ValueError, match="evidence_id"):
        classify_agenda_status_label("TIME:", evidence_id="")


def test_requires_string_label():
    with pytest.raises(TypeError, match="label"):
        classify_agenda_status_label(None, evidence_id="evidence:agenda:1")  # type: ignore[arg-type]
