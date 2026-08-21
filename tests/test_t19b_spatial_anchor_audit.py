from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def _load(name: str):
    return json.loads((EXP / name).read_text(encoding="utf-8"))


def _signature(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def test_t19b_post_hoc_anchor_audit_freezes_blind_result_and_failure_class() -> None:
    audit = _load("r1_t19b_spatial_anchor_audit.json")

    assert audit["schema"] == "proofline-akron-t19b-spatial-anchor-audit/v1"
    assert audit["audit_stage"] == "post_hoc_failure_localization_after_blind_machine_artifact_frozen"

    blind = audit["blind_evidence"]
    assert blind["run_id"] == 32497051480
    assert blind["artifact_id"] == 9452336639
    assert blind["artifact_digest"] == (
        "sha256:4033ea05fbd122504e0dadf005f200ae32e30f646d086cfdfb2399b0bbb36320"
    )
    assert blind["evaluation_sha256"] == (
        "542b35d019573ce518d22cd3001663f2a4a89d4fcc025c40e97118bf21116e1b"
    )

    population = audit["blind_population"]
    assert population["page_parser_money_fact_count"] == 375
    assert population["spatial_line_money_observation_count"] == 90
    assert population["spatial_money_region_count"] == 90

    gap = audit["coverage_gap"]
    assert gap["unmatched_page_parser_money_fact_count"] == 285
    assert gap["matched_page_parser_money_fact_count"] == 90
    assert gap["matched_rate"] == 0.24
    assert gap["all_unmatched_raw_tokens_match_pattern"] == r"$\n<number>"
    assert gap["all_unmatched_raw_tokens_cross_extractor_line_boundary"] is True
    assert gap["unmatched_by_preferred_method"] == {
        "pymupdf_native_text": 273,
        "pymupdf_tesseract_ocr": 12,
    }

    interpretation = audit["interpretation"]
    assert interpretation["grouping_v1_tuning_justified_by_this_gap"] is False
    assert interpretation["spatial_anchor_repair_justified"] is True
    assert interpretation["t19b_may_validate_repair"] is False

    boundary = audit["semantic_boundary"]
    assert boundary["detector_authorized"] is False
    assert boundary["lead_count"] is None


def test_t20_future_holdout_is_identity_only_and_disjoint_from_opened_ranks() -> None:
    frozen = _load("r1_t20_future_holdout_sources.json")

    assert frozen["schema"] == "proofline-akron-t20-future-holdout-source-set/v1"
    assert frozen["content_inspection_status"] == "identity_hash_only_not_resolved_or_inspected"

    excluded = frozen["already_opened_exclusion"]
    selected = frozen["selected"]
    hashes = selected["source_uri_sha256"]

    assert excluded["count"] == 96
    assert excluded["original_manifest_ranks"] == [1, 96]
    assert excluded["signature_sha256"] == (
        "e6288eeda9d527ffcc9189b01cf0c101e5f42d122070fc563ebe798ce1189b61"
    )
    assert selected["count"] == 32
    assert selected["original_manifest_ranks"] == [97, 128]
    assert len(hashes) == 32
    assert len(set(hashes)) == 32
    assert hashes == sorted(hashes)
    assert _signature(hashes) == (
        "2977671e9680305dfde595d13c77ca31197613eae0c1813f6d7a0b2218938bf3"
    )
    assert selected["signature_sha256"] == _signature(hashes)
    assert frozen["combined_rank_1_128_signature_sha256"] == (
        "8620cf0dab2126035dfccebb82fa6e83f4d44d68c44ae90993455ec36faabaf1"
    )

    serialized = json.dumps(frozen, sort_keys=True)
    for forbidden in (
        '"source_uri":',
        '"source_name":',
        '"document_text":',
        '"document_bytes":',
        '"money_facts":',
        '"layout_features":',
        '"semantic_labels":',
    ):
        assert forbidden not in serialized
