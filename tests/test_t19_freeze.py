from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "experiments" / "akron-2026" / "r1_t19_future_holdout_sources.json"
SUMMARY = ROOT / "experiments" / "akron-2026" / "r1_t19_local_grouping_development_summary.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def test_t19_future_holdout_is_identity_hash_only_and_signature_stable() -> None:
    data = _load(HOLDOUT)
    assert data["schema"] == "proofline-akron-t19-future-holdout-source-set/v1"
    assert data["content_inspection_status"] == "identity_hash_only_not_resolved_or_inspected"

    selected = data["selected"]
    hashes = selected["source_uri_sha256"]
    assert selected["count"] == 32
    assert selected["original_manifest_ranks"] == [65, 96]
    assert len(hashes) == 32
    assert hashes == sorted(hashes)
    assert len(set(hashes)) == 32
    assert all(HEX64.fullmatch(value) for value in hashes)

    payload = "".join(f"{value}\n" for value in hashes).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == selected["signature_sha256"]
    assert selected["signature_sha256"] == "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"

    forbidden_exact_keys = {
        "source_uri",
        "source_name",
        "document_text",
        "document_bytes",
        "money_facts",
        "layout_features",
        "semantic_labels",
    }
    assert forbidden_exact_keys.isdisjoint(set(_walk_keys(data)))
    assert not any(value.startswith(("http://", "https://")) for value in _walk_strings(data))


def test_t19_development_summary_keeps_future_holdout_closed() -> None:
    summary = _load(SUMMARY)
    assert summary["schema"] == "proofline-akron-t19-local-grouping-development/v1"
    assert summary["representation"]["method"] == "proofline-local-grouping/nearest-components-v1"
    assert summary["representation"]["threshold_free"] is True
    assert summary["representation"]["semantic_labels_are_grouping_inputs"] is False
    assert summary["future_holdout"]["opened_for_this_measurement"] is False
    assert summary["future_holdout"]["selection_signature_sha256"] == "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"

    result = summary["result"]
    assert result["nearest_directed_edge_count"] == 49
    assert result["component_count"] == 19
    assert result["component_size_counts"] == {"2": 8, "3": 11}
    assert result["post_hoc_pure_component_count"] == 19
    assert result["post_hoc_mixed_component_count"] == 0
    assert result["component_membership_signature_sha256"] == "f92b1c6e4a4797118bbffe542307491864b9d20b441783407fc3342e712b4043"

    boundary = summary["semantic_boundary"]
    assert boundary["detector_authorized"] is False
    assert boundary["financial_semantics_authorized"] is False
    assert boundary["event_identity_assigned"] is False
    assert boundary["lead_count"] is None
