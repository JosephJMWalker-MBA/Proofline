import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path("experiments/akron-2026/acquire_t21_april27_supporting_documents.py")
SELECTION = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def _module():
    spec = importlib.util.spec_from_file_location("t21_april27_acquisition", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_selection(module, relations: list[dict]) -> dict:
    rows = [
        {
            "meeting_id": relation["meeting_id"],
            "item_id": relation["item_id"],
            "publish_id": relation["publish_id"],
            "source_uri_sha256": module._sha256_text(relation["source_uri"]),
            "link_text_sha256": module._sha256_text(relation["link_text"]),
        }
        for relation in relations
    ]
    rows.sort(key=lambda row: (row["publish_id"], row["source_uri_sha256"]))
    return {
        "schema": module.SELECTION_SCHEMA,
        "basis": {
            "parent_meeting_id": 1,
            "parent_item_id": 2,
            "publisher_declared_relation_count": len(rows),
        },
        "selected_document_count": len(rows),
        "selected_documents": rows,
        "selection_signature_sha256": module._sha256_json(rows),
    }


def test_frozen_april27_selection_round_trips() -> None:
    module = _module()
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    rows = module.selection_rows(selection)
    assert len(rows) == 20
    assert rows[0]["publish_id"] == 102587
    assert rows[-1]["publish_id"] == 102606
    assert selection["selection_signature_sha256"] == "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"


def test_verify_publisher_relations_requires_exact_frozen_set() -> None:
    module = _module()
    relations = [
        {
            "meeting_id": 1,
            "item_id": 2,
            "publish_id": 10,
            "source_uri": "https://example.test/a",
            "link_text": "A",
        },
        {
            "meeting_id": 1,
            "item_id": 2,
            "publish_id": 11,
            "source_uri": "https://example.test/b",
            "link_text": "B",
        },
    ]
    selection = _synthetic_selection(module, relations)
    verified = module.verify_publisher_relations(selection, relations)
    assert [row["publish_id"] for row in verified] == [10, 11]

    drifted = [dict(row) for row in relations]
    drifted[1]["link_text"] = "changed"
    with pytest.raises(ValueError, match="no longer match frozen selection"):
        module.verify_publisher_relations(selection, drifted)

    extra = relations + [
        {
            "meeting_id": 1,
            "item_id": 2,
            "publish_id": 12,
            "source_uri": "https://example.test/c",
            "link_text": "C",
        }
    ]
    with pytest.raises(ValueError, match="relation count drifted"):
        module.verify_publisher_relations(selection, extra)


def test_selected_manifest_uses_only_verified_transport() -> None:
    module = _module()
    relations = [
        {
            "meeting_id": 1,
            "item_id": 2,
            "publish_id": 10,
            "source_uri": "https://example.test/a",
            "link_text": "A",
        },
        {
            "meeting_id": 1,
            "item_id": 2,
            "publish_id": 11,
            "source_uri": "https://example.test/b",
            "link_text": "B",
        },
    ]
    selection = _synthetic_selection(module, relations)
    manifest = {
        "schema": "proofline-source-manifest/v1",
        "resources": [
            {
                "source_uri": relation["source_uri"],
                "source_name": f"source-{relation['publish_id']}",
                "native_identifier": str(relation["publish_id"]),
                "expected_media_type": "application/pdf",
                "sequence_group": "test",
                "sequence_number": index,
                "fetch_strategy": module.FETCH_STRATEGY,
            }
            for index, relation in enumerate(relations, start=1)
        ],
    }
    verified = module.verify_publisher_relations(selection, relations)
    selected = module.selected_manifest(selection, verified, manifest)
    assert len(selected.resources) == 2
    assert [resource.source_uri for resource in selected.resources] == [
        "https://example.test/a",
        "https://example.test/b",
    ]

    manifest["resources"][1]["fetch_strategy"] = "wrong"
    with pytest.raises(ValueError, match="fetch strategy"):
        module.selected_manifest(selection, verified, manifest)
