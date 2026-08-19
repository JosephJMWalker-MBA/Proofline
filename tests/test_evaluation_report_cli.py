from __future__ import annotations

import json
from pathlib import Path

from proofline.evaluation_report_cli import main


def test_report_cli_reproduces_preserved_first_r1_metrics(tmp_path) -> None:
    source = Path("experiments/canton-2026/retrieval/r1-first-score/evaluation.json")
    output = tmp_path / "report.json"
    assert main([str(source), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["cases"] == 33
    assert payload["scorable_case_count"] == 27
    assert payload["unscorable_case_count"] == 6
    assert payload["unresolved_target_count"] == 10
    assert payload["scorable_expectation_accuracy"] == 1.0
    assert payload["scorable_positive_case_count"] == 22
    assert payload["scorable_positive_hit_rate"] == 1.0
    assert payload["scorable_target_recall_at_k"] == 1.0
    assert payload["scorable_negative_case_count"] == 5
    assert payload["scorable_negative_accuracy"] == 1.0
    assert payload["retrieval_failure_counts"] == []
