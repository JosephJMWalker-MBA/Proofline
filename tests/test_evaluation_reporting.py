from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofline.evaluation_reporting import build_scorable_report, load_evaluation_result


def _case(
    case_id: str,
    *,
    mode: str = "lexical",
    expected=(),
    returned=(),
    unresolved=(),
    expect_empty: bool = False,
    expectation_met: bool = False,
    failure_class: str | None = None,
    provenance_validity: float = 1.0,
):
    return {
        "case_id": case_id,
        "query": case_id,
        "mode": mode,
        "expected_evidence_ids": list(expected),
        "returned_evidence_ids": list(returned),
        "unresolved_targets": list(unresolved),
        "expect_empty": expect_empty,
        "expectation_met": expectation_met,
        "failure_class": failure_class,
        "provenance_validity": provenance_validity,
    }


def test_scorable_report_excludes_partially_unresolved_case_from_retrieval_metrics() -> None:
    payload = {
        "schema": "proofline-retrieval-eval/v2",
        "suite": "mixed",
        "case_results": [
            _case(
                "positive-hit",
                expected=("e1",),
                returned=("e1",),
                expectation_met=True,
            ),
            _case(
                "negative-correct",
                returned=(),
                expect_empty=True,
                expectation_met=True,
            ),
            _case(
                "partial-resolution",
                mode="date",
                expected=("e2",),
                returned=("e2", "replacement"),
                unresolved=({"source_uri": "https://example.gov/volatile", "locator": "record:1"},),
                expectation_met=True,
                failure_class="unresolved_target",
            ),
        ],
    }

    report = build_scorable_report(payload)
    assert report.cases == 3
    assert report.scorable_case_count == 2
    assert report.unscorable_case_count == 1
    assert report.unresolved_target_count == 1
    assert report.scorable_expectation_accuracy == 1.0
    assert report.scorable_positive_case_count == 1
    assert report.scorable_positive_hit_rate == 1.0
    assert report.scorable_target_recall_at_k == 1.0
    assert report.scorable_negative_case_count == 1
    assert report.scorable_negative_accuracy == 1.0
    assert report.retrieval_failure_counts == ()
    assert report.unscorable_cases[0].raw_expectation_met is True
    assert report.unscorable_cases[0].failure_class == "unresolved_target"


def test_all_targets_unresolved_is_unscorable_not_retrieval_miss() -> None:
    payload = {
        "schema": "proofline-retrieval-eval/v2",
        "suite": "unresolved",
        "case_results": [
            _case(
                "all-unresolved",
                mode="date",
                expected=(),
                returned=("new-version",),
                unresolved=(
                    {"source_uri": "https://example.gov/a", "locator": "record:1"},
                    {"source_uri": "https://example.gov/b", "locator": "record:1"},
                ),
                expectation_met=False,
                failure_class="unresolved_target",
            )
        ],
    }
    report = build_scorable_report(payload)
    assert report.scorable_case_count == 0
    assert report.unscorable_case_count == 1
    assert report.unresolved_target_count == 2
    assert report.scorable_expectation_accuracy == 1.0
    assert report.scorable_positive_case_count == 0
    assert report.retrieval_failure_counts == ()
    assert report.unscorable_mode_counts == ({"mode": "date", "count": 1},)


def test_actual_scorable_retrieval_failure_remains_visible() -> None:
    payload = {
        "schema": "proofline-retrieval-eval/v2",
        "suite": "miss",
        "case_results": [
            _case(
                "miss",
                expected=("e1",),
                returned=("other",),
                expectation_met=False,
                failure_class="miss_all_targets",
            )
        ],
    }
    report = build_scorable_report(payload)
    assert report.scorable_case_count == 1
    assert report.scorable_expectation_accuracy == 0.0
    assert report.scorable_positive_hit_rate == 0.0
    assert report.scorable_target_recall_at_k == 0.0
    assert report.retrieval_failure_counts == ({"failure_class": "miss_all_targets", "count": 1},)


def test_preserved_first_r1_score_reproduces_documented_scorable_metrics() -> None:
    path = Path("experiments/canton-2026/retrieval/r1-first-score/evaluation.json")
    payload = load_evaluation_result(path)
    report = build_scorable_report(payload)

    assert report.cases == 33
    assert report.scorable_case_count == 27
    assert report.unscorable_case_count == 6
    assert report.unresolved_target_count == 10
    assert report.scorable_expectation_accuracy == 1.0
    assert report.scorable_positive_case_count == 22
    assert report.scorable_positive_hit_rate == 1.0
    assert report.scorable_target_recall_at_k == 1.0
    assert report.scorable_negative_case_count == 5
    assert report.scorable_negative_accuracy == 1.0
    assert report.scorable_mean_case_provenance_validity == 1.0
    assert report.retrieval_failure_counts == ()
    assert report.unscorable_mode_counts == (
        {"mode": "date", "count": 5},
        {"mode": "native_identifier", "count": 1},
    )

    modes = {row["mode"]: row for row in report.mode_metrics}
    assert modes["lexical"]["scorable_cases"] == 11
    assert modes["lexical"]["scorable_expectation_accuracy"] == 1.0
    assert modes["money"]["scorable_expectation_accuracy"] == 1.0
    assert modes["date"]["unscorable_cases"] == 5
    assert modes["native_identifier"]["unscorable_cases"] == 1


def test_loader_rejects_non_object(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_evaluation_result(path)
