from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH_EXPERIMENT = ROOT / "experiments" / "akron-2026"


def _load_module(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def test_t13_preserves_exact_t12_contract_evaluator_and_holdout_blobs() -> None:
    assert _git_blob_sha(BRANCH_EXPERIMENT / "akron-financial-representation-v2.json") == (
        "45e535ececb882f77293e7ddc757a83de1c9031d"
    )
    assert _git_blob_sha(BRANCH_EXPERIMENT / "financial_representation_v2.py") == (
        "7724694c2a9d2c2e3606a18c3ea1c47d02f8154e"
    )
    assert _git_blob_sha(BRANCH_EXPERIMENT / "r1_t13_disjoint_attachment_sources.json") == (
        "06f86cb6b64d03e38774f9b97909bc3b69048976"
    )


def test_t13_frozen_selection_resolves_by_source_identity_only() -> None:
    module = _load_module(
        "experiments/akron-2026/sync_frozen_attachment_holdout.py",
        "akron_t13_frozen_attachment_holdout",
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
        "schema": "proofline-akron-t13-disjoint-source-set/v1",
        "content_inspection_status": "not_inspected_at_freeze",
        "excluded": {
            "count": 32,
            "original_manifest_ranks": [1, 32],
            "source_uri_sha256": hashes[:32],
        },
        "selected": {
            "count": 32,
            "original_manifest_ranks": [33, 64],
            "source_uri_sha256": hashes[32:64],
        },
    }

    selected, metadata = module.resolve_selection(
        {"resources": list(reversed(resources))}, selection
    )

    assert [item["source_uri"] for item in selected] == [
        item["source_uri"] for item in ranked[32:64]
    ]
    assert metadata["live_excluded_ranks"] == list(range(1, 33))
    assert metadata["live_selected_ranks"] == list(range(33, 65))
    assert metadata["selection_basis"] == "sha256(source_uri) only"
    assert set(metadata["excluded_source_hashes"]).isdisjoint(
        metadata["selected_source_hashes"]
    )


def test_t13_selection_rejects_loss_of_preinspection_freeze_marker() -> None:
    module = _load_module(
        "experiments/akron-2026/sync_frozen_attachment_holdout.py",
        "akron_t13_freeze_marker",
    )
    selection = json.loads(
        (BRANCH_EXPERIMENT / "r1_t13_disjoint_attachment_sources.json").read_text(
            encoding="utf-8"
        )
    )
    selection["content_inspection_status"] = "inspected"
    try:
        module.resolve_selection({"resources": []}, selection)
    except ValueError as exc:
        assert "pre-inspection freeze marker" in str(exc)
    else:
        raise AssertionError("T13 selection accepted a changed freeze marker")


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


def test_t13_evaluator_hard_codes_representation_only_stage() -> None:
    module = _load_module(
        "experiments/akron-2026/evaluate_financial_representation_v2_oos.py",
        "akron_t13_stage_boundary",
    )
    assert module.SCHEMA == "proofline-akron-financial-representation-v2-oos-evaluation/v1"
    assert module.SELECTION_SYNC_SCHEMA == "proofline-akron-t13-frozen-attachment-sync/v1"
    assert module.EXPECTED_SOURCES == 32
