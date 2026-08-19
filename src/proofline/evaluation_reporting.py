"""Derived retrieval measurements that separate target resolvability from retrieval success.

The raw retrieval evaluator remains an immutable historical producer. This module interprets a
saved evaluation result without changing it, so corpus/target drift cannot be mistaken for a
lexical or structured retrieval miss.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class UnscorableCase:
    case_id: str
    mode: str
    unresolved_target_count: int
    failure_class: str | None
    raw_expectation_met: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScorableEvaluationReport:
    source_schema: str
    suite: str
    cases: int
    scorable_case_count: int
    unscorable_case_count: int
    unresolved_target_count: int
    scorable_expectation_accuracy: float
    scorable_positive_case_count: int
    scorable_positive_hit_rate: float
    scorable_target_recall_at_k: float
    scorable_negative_case_count: int
    scorable_negative_accuracy: float
    scorable_mean_case_provenance_validity: float
    retrieval_failure_counts: tuple[dict, ...]
    unscorable_mode_counts: tuple[dict, ...]
    unscorable_cases: tuple[UnscorableCase, ...]
    mode_metrics: tuple[dict, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["retrieval_failure_counts"] = list(self.retrieval_failure_counts)
        data["unscorable_mode_counts"] = list(self.unscorable_mode_counts)
        data["unscorable_cases"] = [item.to_dict() for item in self.unscorable_cases]
        data["mode_metrics"] = list(self.mode_metrics)
        return data


def load_evaluation_result(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation result must be a JSON object")
    return payload


def _cases(payload: Mapping[str, Any]) -> list[dict]:
    raw = payload.get("case_results")
    if not isinstance(raw, list):
        raise ValueError("evaluation result must contain case_results list")
    cases: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each case result must be an object")
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case result requires non-empty case_id")
        if case_id in seen:
            raise ValueError(f"duplicate case result: {case_id}")
        seen.add(case_id)
        unresolved = item.get("unresolved_targets")
        expected = item.get("expected_evidence_ids")
        returned = item.get("returned_evidence_ids")
        if not isinstance(unresolved, list):
            raise ValueError(f"unresolved_targets must be a list for {case_id}")
        if not isinstance(expected, list) or not isinstance(returned, list):
            raise ValueError(f"expected/returned evidence IDs must be lists for {case_id}")
        cases.append(item)
    return cases


def _case_expectation(case: Mapping[str, Any]) -> tuple[bool, float]:
    returned = {str(value) for value in case.get("returned_evidence_ids") or ()}
    if bool(case.get("expect_empty")):
        return not returned, 1.0 if not returned else 0.0
    expected = {str(value) for value in case.get("expected_evidence_ids") or ()}
    found = expected & returned
    met = bool(expected) and found == expected
    recall = len(found) / len(expected) if expected else 0.0
    return met, recall


def _mode_metrics(cases: list[dict]) -> tuple[dict, ...]:
    output: list[dict] = []
    for mode in sorted({str(case.get("mode") or "lexical") for case in cases}):
        rows = [case for case in cases if str(case.get("mode") or "lexical") == mode]
        scorable = [case for case in rows if not case.get("unresolved_targets")]
        unscorable = [case for case in rows if case.get("unresolved_targets")]
        positives = [case for case in scorable if not case.get("expect_empty")]
        negatives = [case for case in scorable if case.get("expect_empty")]
        positive_metrics = [_case_expectation(case) for case in positives]
        negative_metrics = [_case_expectation(case) for case in negatives]
        output.append(
            {
                "mode": mode,
                "cases": len(rows),
                "scorable_cases": len(scorable),
                "unscorable_cases": len(unscorable),
                "scorable_expectation_accuracy": (
                    sum(_case_expectation(case)[0] for case in scorable) / len(scorable)
                    if scorable
                    else 1.0
                ),
                "scorable_positive_cases": len(positives),
                "scorable_positive_hit_rate": (
                    sum(met for met, _ in positive_metrics) / len(positive_metrics)
                    if positive_metrics
                    else 1.0
                ),
                "scorable_mean_target_recall": (
                    sum(recall for _, recall in positive_metrics) / len(positive_metrics)
                    if positive_metrics
                    else 1.0
                ),
                "scorable_negative_cases": len(negatives),
                "scorable_negative_accuracy": (
                    sum(met for met, _ in negative_metrics) / len(negative_metrics)
                    if negative_metrics
                    else 1.0
                ),
            }
        )
    return tuple(output)


def build_scorable_report(payload: Mapping[str, Any]) -> ScorableEvaluationReport:
    cases = _cases(payload)
    scorable = [case for case in cases if not case.get("unresolved_targets")]
    unscorable = [case for case in cases if case.get("unresolved_targets")]
    positives = [case for case in scorable if not case.get("expect_empty")]
    negatives = [case for case in scorable if case.get("expect_empty")]

    scorable_metrics = [_case_expectation(case) for case in scorable]
    positive_metrics = [_case_expectation(case) for case in positives]
    negative_metrics = [_case_expectation(case) for case in negatives]

    expected_total = 0
    found_total = 0
    for case in positives:
        expected = {str(value) for value in case.get("expected_evidence_ids") or ()}
        returned = {str(value) for value in case.get("returned_evidence_ids") or ()}
        expected_total += len(expected)
        found_total += len(expected & returned)

    unresolved_target_count = sum(len(case.get("unresolved_targets") or ()) for case in cases)
    unscorable_mode_counter = Counter(str(case.get("mode") or "lexical") for case in unscorable)

    # Retrieval failure counts explicitly exclude target-resolution failures. They describe only
    # scorable cases whose retrieval/provenance expectation failed.
    retrieval_failure_counter: Counter[str] = Counter()
    for case in scorable:
        failure = case.get("failure_class")
        if failure and failure != "unresolved_target":
            retrieval_failure_counter[str(failure)] += 1

    unscorable_items = tuple(
        UnscorableCase(
            case_id=str(case["case_id"]),
            mode=str(case.get("mode") or "lexical"),
            unresolved_target_count=len(case.get("unresolved_targets") or ()),
            failure_class=(str(case["failure_class"]) if case.get("failure_class") else None),
            raw_expectation_met=bool(case.get("expectation_met")),
        )
        for case in unscorable
    )

    return ScorableEvaluationReport(
        source_schema=str(payload.get("schema") or "unknown"),
        suite=str(payload.get("suite") or "unknown"),
        cases=len(cases),
        scorable_case_count=len(scorable),
        unscorable_case_count=len(unscorable),
        unresolved_target_count=unresolved_target_count,
        scorable_expectation_accuracy=(
            sum(met for met, _ in scorable_metrics) / len(scorable_metrics)
            if scorable_metrics
            else 1.0
        ),
        scorable_positive_case_count=len(positives),
        scorable_positive_hit_rate=(
            sum(met for met, _ in positive_metrics) / len(positive_metrics)
            if positive_metrics
            else 1.0
        ),
        scorable_target_recall_at_k=(found_total / expected_total if expected_total else 1.0),
        scorable_negative_case_count=len(negatives),
        scorable_negative_accuracy=(
            sum(met for met, _ in negative_metrics) / len(negative_metrics)
            if negative_metrics
            else 1.0
        ),
        scorable_mean_case_provenance_validity=(
            sum(float(case.get("provenance_validity", 0.0)) for case in scorable) / len(scorable)
            if scorable
            else 1.0
        ),
        retrieval_failure_counts=tuple(
            {"failure_class": key, "count": retrieval_failure_counter[key]}
            for key in sorted(retrieval_failure_counter)
        ),
        unscorable_mode_counts=tuple(
            {"mode": key, "count": unscorable_mode_counter[key]}
            for key in sorted(unscorable_mode_counter)
        ),
        unscorable_cases=unscorable_items,
        mode_metrics=_mode_metrics(cases),
    )
