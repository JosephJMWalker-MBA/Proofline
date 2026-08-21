from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH_EXPERIMENT = ROOT / "experiments" / "akron-2026"


def _load_module(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    module_dir = str(path.parent)
    added = module_dir not in sys.path
    if added:
        sys.path.insert(0, module_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(module_dir)
    return module


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _signature(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def test_t13b_preserves_exact_t12_contract_evaluator_and_original_failed_holdout_blobs() -> None:
    assert _git_blob_sha(BRANCH_EXPERIMENT / "akron-financial-representation-v2.json") == (
        "45e535ececb882f77293e7ddc757a83de1c9031d"
    )
    assert _git_blob_sha(BRANCH_EXPERIMENT / "financial_representation_v2.py") == (
        "7724694c2a9d2c2e3606a18c3ea1c47d02f8154e"
    )
    assert _git_blob_sha(BRANCH_EXPERIMENT / "r1_t13_disjoint_attachment_sources.json") == (
        "06f86cb6b64d03e38774f9b97909bc3b69048976"
    )
    assert _git_blob_sha(BRANCH_EXPERIMENT / "r1_t13b_disjoint_attachment_sources.json") == (
        "8f3353769c769ff9329d95761712c0d9862dda02"
    )


def test_t13b_corrected_file_records_failed_closed_audit_and_rank_signatures() -> None:
    payload = json.loads(
        (BRANCH_EXPERIMENT / "r1_t13b_disjoint_attachment_sources.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema"] == "proofline-akron-t13b-disjoint-source-set/v1"
    assert payload["content_inspection_status"] == "not_inspected_for_correction"
    assert payload["provenance"]["source_manifest_sha256"] == (
        "7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a"
    )
    assert payload["correction"]["failed_run_id"] == 32439675353
    assert payload["correction"]["representation_applied_in_failed_run"] is False
    assert payload["correction"]["original_frozen_selected_hashes_valid"] == 8
    assert payload["correction"]["original_frozen_selected_hashes_invalid"] == 24

    excluded = payload["excluded"]["source_uri_sha256"]
    selected = payload["selected"]["source_uri_sha256"]
    assert len(excluded) == len(set(excluded)) == 32
    assert len(selected) == len(set(selected)) == 32
    assert set(excluded).isdisjoint(selected)
    assert excluded == sorted(excluded)
    assert selected == sorted(selected)
    assert payload["excluded"]["signature_sha256"] == _signature(excluded) == (
        "e0e72779fb4e88f1720ff5f00dcb7ac90a11c83ed56094c32a1da2f478383afb"
    )
    assert payload["selected"]["signature_sha256"] == _signature(selected) == (
        "b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966"
    )
    assert payload["combined_rank_1_64_signature_sha256"] == _signature(excluded + selected) == (
        "ce876915836a86c914ca837964a95fcc4f4857d423eaadfa91749978eb9715a0"
    )


def test_t13b_frozen_selection_resolves_by_source_identity_only() -> None:
    module = _load_module(
        "experiments/akron-2026/sync_frozen_attachment_holdout.py",
        "akron_t13b_frozen_attachment_holdout",
    )
    resources = [
        {
            "source_uri": f"https://records.example.gov/Documents/DownloadFile/{index}.pdf",
            "source_name": f"Content-looking label {79 - index}",
            "native_identifier": f"fixture-{index}",
            "expected_media_type": "application/pdf",
            "fetch_strategy": "onbase_download_bytes",
        }
        for index in range(80)
    ]
    ranked = sorted(
        resources,
        key=lambda item: (
            hashlib.sha256(item["source_uri"].encode("utf-8")).hexdigest(),
            item["source_uri"],
        ),
    )
    hashes = [hashlib.sha256(item["source_uri"].encode("utf-8")).hexdigest() for item in ranked]
    selection = {
        "schema": "proofline-akron-t13b-disjoint-source-set/v1",
        "content_inspection_status": "not_inspected_for_correction",
        "provenance": {"source_manifest_sha256": module.EXPECTED_MANIFEST_SHA256},
        "correction": {
            "representation_applied_in_failed_run": False,
            "failed_run_id": 32439675353,
        },
        "excluded": {
            "count": 32,
            "original_manifest_ranks": [1, 32],
            "source_uri_sha256": hashes[:32],
            "signature_sha256": module._signature(hashes[:32]),
        },
        "selected": {
            "count": 32,
            "original_manifest_ranks": [33, 64],
            "source_uri_sha256": hashes[32:64],
            "signature_sha256": module._signature(hashes[32:64]),
        },
    }

    # This fixture has different identities than the production freeze; temporarily align
    # only the expected signatures to prove selection is independent of source-name content.
    old_excluded = module.EXPECTED_EXCLUDED_SIGNATURE
    old_selected = module.EXPECTED_SELECTED_SIGNATURE
    module.EXPECTED_EXCLUDED_SIGNATURE = module._signature(hashes[:32])
    module.EXPECTED_SELECTED_SIGNATURE = module._signature(hashes[32:64])
    try:
        selected, metadata = module.resolve_selection(
            {"resources": list(reversed(resources))}, selection
        )
    finally:
        module.EXPECTED_EXCLUDED_SIGNATURE = old_excluded
        module.EXPECTED_SELECTED_SIGNATURE = old_selected

    assert [item["source_uri"] for item in selected] == [
        item["source_uri"] for item in ranked[32:64]
    ]
    assert metadata["live_excluded_ranks"] == list(range(1, 33))
    assert metadata["live_selected_ranks"] == list(range(33, 65))
    assert metadata["selection_basis"].startswith("sha256(source_uri) only")
    assert set(metadata["excluded_source_hashes"]).isdisjoint(
        metadata["selected_source_hashes"]
    )


def test_t13b_selection_rejects_loss_of_correction_boundary() -> None:
    module = _load_module(
        "experiments/akron-2026/sync_frozen_attachment_holdout.py",
        "akron_t13b_freeze_marker",
    )
    selection = json.loads(
        (BRANCH_EXPERIMENT / "r1_t13b_disjoint_attachment_sources.json").read_text(
            encoding="utf-8"
        )
    )
    selection["content_inspection_status"] = "inspected"
    try:
        module.resolve_selection({"resources": []}, selection)
    except ValueError as exc:
        assert "no-content-inspection marker" in str(exc)
    else:
        raise AssertionError("T13b selection accepted a changed correction marker")


def test_t13_duplicate_source_names_use_only_shared_context() -> None:
    module = _load_module(
        "experiments/akron-2026/evaluate_financial_representation_v2_oos.py",
        "akron_t13_source_name_context",
    )

    name, status, originals = module._source_name_context(
        [
            {"source_name": "Budget Responses"},
            {"source_name": "  budget   responses  "},
        ]
    )
    assert status == "shared_nonblank"
    assert name in originals

    name, status, originals = module._source_name_context(
        [
            {"source_name": "Budget Responses"},
            {"source_name": "External Fire Comparison"},
        ]
    )
    assert name == ""
    assert status == "divergent_omitted"
    assert originals == ["Budget Responses", "External Fire Comparison"]


def test_t13b_evaluator_hard_codes_representation_only_stage() -> None:
    module = _load_module(
        "experiments/akron-2026/evaluate_financial_representation_v2_oos.py",
        "akron_t13b_stage_boundary",
    )
    assert module.SCHEMA == "proofline-akron-financial-representation-v2-oos-evaluation/v1"
    assert module.SELECTION_SYNC_SCHEMA == "proofline-akron-t13b-frozen-attachment-sync/v1"
    assert module.EXPECTED_SOURCES == 32
