from datetime import date

import pytest

from proofline.explicit_references import (
    EXPLICIT_REFERENCE_METHOD,
    exact_reference_matches,
    extract_explicit_references,
)


def test_extracts_planning_case_with_exact_span_and_normalization():
    text = "Subject: Opposition Case: Petition PC-2025-80-CU"
    refs = extract_explicit_references(text, evidence_id="evidence:letter")
    assert len(refs) == 1
    ref = refs[0]
    assert ref.kind == "planning_case"
    assert ref.normalized_key == "PC-2025-80-CU"
    assert text[ref.char_start:ref.char_end] == "PC-2025-80-CU"
    assert ref.join_eligible is True
    assert ref.method == EXPLICIT_REFERENCE_METHOD


def test_normalizes_docket_and_ordinance_identifiers_without_semantics():
    text = "D-14 was discussed after ORDINANCE NO. 43-2026."
    refs = extract_explicit_references(text, evidence_id="evidence:agenda")
    assert [(ref.kind, ref.normalized_key) for ref in refs] == [
        ("docket", "D-14"),
        ("ordinance", "ORDINANCE-43-2026"),
    ]


def test_partial_month_day_requires_context_year_and_is_not_join_eligible():
    text = "I submitted pictures at the March 9th meeting."
    assert extract_explicit_references(text, evidence_id="evidence:letter") == ()
    refs = extract_explicit_references(
        text,
        evidence_id="evidence:letter",
        context_date=date(2026, 3, 23),
    )
    assert len(refs) == 1
    assert refs[0].normalized_key == "2026-03-09"
    assert refs[0].normalization_basis == "context_year"
    assert refs[0].join_eligible is False


def test_numeric_date_is_bounded_and_invalid_dates_are_ignored():
    refs = extract_explicit_references(
        "Public Hearing held 03/09/26; typo 02/31/26.",
        evidence_id="evidence:agenda",
    )
    assert [(ref.kind, ref.normalized_key) for ref in refs] == [("date", "2026-03-09")]


def test_exact_matches_require_same_strong_identifier_across_distinct_evidence():
    matches = exact_reference_matches(
        {
            "evidence:letter": "Opposition Case: Petition PC-2025-80-CU; March 9, 2026",
            "evidence:agenda": "D-14 Petition for PC-2025-80-CU; hearing March 9, 2026",
            "evidence:other": "Another hearing March 9, 2026",
        }
    )
    assert len(matches) == 1
    assert matches[0].kind == "planning_case"
    assert matches[0].normalized_key == "PC-2025-80-CU"
    assert matches[0].evidence_ids == ("evidence:agenda", "evidence:letter")


def test_date_only_does_not_create_record_family_match():
    assert exact_reference_matches(
        {
            "evidence:a": "Meeting March 9, 2026",
            "evidence:b": "Public Hearing March 9, 2026",
        }
    ) == ()


def test_similar_but_nonliteral_case_text_does_not_fuzzy_match():
    matches = exact_reference_matches(
        {
            "evidence:a": "PC-2025-80-CU",
            "evidence:b": "planning case 2025 80 conditional use",
        }
    )
    assert matches == ()


def test_repeated_reference_in_one_evidence_does_not_self_match():
    matches = exact_reference_matches(
        {"evidence:a": "PC-2025-80-CU and again PC-2025-80-CU"}
    )
    assert matches == ()


def test_reference_ids_are_deterministic():
    first = extract_explicit_references("D-14", evidence_id="evidence:x")
    second = extract_explicit_references("D-14", evidence_id="evidence:x")
    assert first == second


def test_requires_evidence_id():
    with pytest.raises(ValueError, match="evidence_id"):
        extract_explicit_references("D-14", evidence_id="")
