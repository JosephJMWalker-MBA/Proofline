from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def test_t20_anchor_v1_development_result_preserves_refinement_boundary() -> None:
    result = json.loads(
        (EXP / "r1_t20_spatial_anchor_v1_development_result.json").read_text(encoding="utf-8")
    )

    assert result["schema"] == "proofline-akron-t20-spatial-anchor-v1-development-result/v1"
    assert result["stage"] == "post_hoc_t19b_development_result_before_anchor_v2_refinement"

    run = result["run"]
    assert run["workflow_run_id"] == 32501978519
    assert run["artifact_id"] == 9454036743
    assert run["artifact_digest"] == (
        "sha256:5eb741beb393fb660cd26de4e90c3f54b9bb4ab67bfbbfbdb83be9fab544c3f5"
    )

    measured = result["result"]
    assert measured["page_parser_money_fact_count"] == 375
    assert measured["anchored_money_fact_count"] == 369
    assert measured["anchor_failure_count"] == 6
    assert measured["cross_line_anchor_count"] == 285
    assert measured["same_line_anchor_count"] == 84

    interpretation = result["development_interpretation"]
    assert interpretation["motivating_cross_line_failures_recovered"] == 285
    assert interpretation["motivating_cross_line_recovery_complete"] is True
    assert interpretation["same_line_regression_count"] == 6
    assert interpretation["v1_ready_to_freeze_for_new_holdout"] is False

    failures = result["v1_failure_localization"]
    assert failures["count"] == 6
    assert failures["outside_span_content_is_adjacent_punctuation_only"] is True
    assert failures["suffix_counts"] == {",": 3, ".": 3}

    refinement = result["next_refinement"]
    assert refinement["method_version_must_change"] is True
    assert refinement["target_method"] == "proofline-spatial-text-anchor/source-span-v2"
    assert refinement["future_holdout_ranks"] == [97, 128]
    assert refinement["future_holdout_remains_unopened"] is True

    boundary = result["semantic_boundary"]
    assert boundary["detector_authorized"] is False
    assert boundary["lead_count"] is None
