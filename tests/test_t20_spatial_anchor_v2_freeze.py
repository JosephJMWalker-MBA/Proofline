from __future__ import annotations

import json
from pathlib import Path

from proofline.spatial_anchor import SPATIAL_TEXT_ANCHOR_METHOD


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "experiments" / "akron-2026" / "r1_t20_spatial_anchor_v2_development_summary.json"
HOLDOUT = ROOT / "experiments" / "akron-2026" / "r1_t20_future_holdout_sources.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_t20_v2_development_freeze_matches_representation_and_result() -> None:
    summary = _load(SUMMARY)
    assert summary["schema"] == "proofline-akron-t20-spatial-anchor-v2-development-summary/v1"
    assert summary["representation"]["anchor_method"] == SPATIAL_TEXT_ANCHOR_METHOD
    assert SPATIAL_TEXT_ANCHOR_METHOD == "proofline-spatial-text-anchor/source-span-v2"

    measured = summary["development_evidence"]
    assert measured["page_parser_money_fact_count"] == 375
    assert measured["anchored_money_fact_count"] == 375
    assert measured["anchor_failure_count"] == 0
    assert measured["cross_line_anchor_count"] == 285
    assert measured["same_line_anchor_count"] == 90
    assert measured["boundary_expanded_anchor_count"] == 6
    assert measured["boundary_punctuation_counts"] == {",": 3, ".": 3}
    assert measured["artifact_digest"] == "sha256:d537514fd76eca9e9f8ece24dd4d9787159fe502a769f0b8cf97d3f86ec94000"


def test_t20_future_holdout_remains_identity_only_and_matches_freeze() -> None:
    summary = _load(SUMMARY)
    holdout = _load(HOLDOUT)
    frozen = summary["future_holdout"]

    assert frozen["status"] == "unopened_at_freeze"
    assert frozen["selected_source_identity_count"] == 32
    assert frozen["selected_signature_sha256"] == "2977671e9680305dfde595d13c77ca31197613eae0c1813f6d7a0b2218938bf3"
    assert holdout["content_inspection_status"] == "identity_hash_only_not_resolved_or_inspected"

    selected = holdout["selected"]
    assert set(selected) == {
        "count",
        "original_manifest_ranks",
        "signature_sha256",
        "source_uri_sha256",
    }
    assert selected["count"] == 32
    assert selected["original_manifest_ranks"] == [97, 128]
    assert selected["signature_sha256"] == frozen["selected_signature_sha256"]
    identities = selected["source_uri_sha256"]
    assert len(identities) == 32
    assert all(isinstance(item, str) and len(item) == 64 for item in identities)

    forbidden_keys = {
        "source_uri",
        "source_name",
        "filename",
        "artifact_id",
        "document_text",
        "document_bytes",
        "money_facts",
        "layout_features",
        "semantic_labels",
    }
    assert forbidden_keys.isdisjoint(selected)


def test_t20_v2_freeze_does_not_authorize_semantics() -> None:
    decision = _load(SUMMARY)["stage_decision"]
    assert decision["source_span_v2_development_complete"] is True
    assert decision["open_ranks_97_128_for_blind_validation_after_freeze"] is True
    assert decision["parser_change_authorized"] is False
    assert decision["grouping_change_authorized"] is False
    assert decision["financial_semantics_authorized"] is False
    assert decision["detector_authorized"] is False
    assert decision["lead_count"] is None
