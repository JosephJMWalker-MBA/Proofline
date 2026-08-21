from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).parents[1]
    / "experiments"
    / "akron-2026"
    / "measure_t21_record_family_evolution.py"
)
_SPEC = importlib.util.spec_from_file_location("t21_record_family_evolution", _SCRIPT)
assert _SPEC and _SPEC.loader
_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_module)

_selection_rows = _module._selection_rows
verify_publisher_relations = _module.verify_publisher_relations
selected_manifest = _module.selected_manifest
_publisher_time_relation = _module._publisher_time_relation


def _packet(meeting_id: int, item_id: int, publish_id: int) -> str:
    return (
        "https://records.example.gov/Agenda/Documents/DownloadFile/D-14.pdf"
        f"?documentType=1&meetingId={meeting_id}&itemId={item_id}"
        f"&publishId={publish_id}&isSection=False&isAttachment=True"
    )


def _selection() -> dict:
    packets = []
    for meeting_id, item_id, publish_id in ((10, 100, 500), (11, 101, 501)):
        source_uri = _packet(meeting_id, item_id, publish_id)
        packets.append(
            {
                "meeting_id": meeting_id,
                "item_id": item_id,
                "publish_id": publish_id,
                "source_uri_sha256": hashlib.sha256(source_uri.encode()).hexdigest(),
            }
        )
    packets.sort(
        key=lambda row: (
            row["meeting_id"],
            row["item_id"],
            row["publish_id"],
            row["source_uri_sha256"],
        )
    )
    signature = hashlib.sha256(
        json.dumps(packets, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": "proofline-akron-t21-record-family-packet-selection/v1",
        "reference": {
            "kind": "planning_case",
            "normalized_key": "PC-2025-80-CU",
        },
        "basis": {"probe_run_id": 1},
        "selected_packet_count": 2,
        "selection_signature_sha256": signature,
        "selected_packets": packets,
    }


def _relation(meeting_id: int, item_id: int, publish_id: int, *, text: str) -> dict:
    return {
        "meeting_id": meeting_id,
        "item_id": item_id,
        "publish_id": publish_id,
        "source_uri": _packet(meeting_id, item_id, publish_id),
        "parent_source_uri": (
            "https://records.example.gov/Agenda/Meetings/ViewMeetingAgendaItem"
            f"?meetingId={meeting_id}&itemId={item_id}&isSection=false&type=agenda"
        ),
        "parent_artifact_id": f"artifact:parent-{meeting_id}",
        "parent_artifact_sha256": f"sha-{meeting_id}",
        "link_text": text,
    }


def test_frozen_selection_verifies_exact_publisher_relations() -> None:
    selection = _selection()
    relations = [
        _relation(10, 100, 500, text="D-14 conditional use PC-2025-80-CU"),
        _relation(11, 101, 501, text="D-14 conditional use PC-2025-80-CU"),
        _relation(10, 100, 999, text="Other packet PC-2024-1-CU"),
    ]

    assert len(_selection_rows(selection)) == 2
    verified = verify_publisher_relations(selection, relations)
    assert [(row["meeting_id"], row["publish_id"]) for row in verified] == [
        (10, 500),
        (11, 501),
    ]


def test_selection_signature_or_relation_drift_fails_closed() -> None:
    selection = _selection()
    selection["selected_packets"][0]["publish_id"] = 999
    with pytest.raises(ValueError, match="selection signature"):
        _selection_rows(selection)

    selection = _selection()
    relations = [
        _relation(10, 100, 500, text="D-14 conditional use PC-2025-80-CU"),
    ]
    with pytest.raises(ValueError, match="exactly one current publisher relation"):
        verify_publisher_relations(selection, relations)


def test_selected_manifest_preserves_publisher_transport_contract() -> None:
    selection = _selection()
    relations = [
        _relation(10, 100, 500, text="D-14 conditional use PC-2025-80-CU"),
        _relation(11, 101, 501, text="D-14 conditional use PC-2025-80-CU"),
    ]
    verified = verify_publisher_relations(selection, relations)
    manifest = {
        "schema": "proofline-source-manifest/v1",
        "name": "all",
        "resources": [
            {
                "source_uri": _packet(
                    row["meeting_id"], row["item_id"], row["publish_id"]
                ),
                "source_name": "D-14 packet",
                "native_identifier": f"attachment-{row['publish_id']}",
                "expected_media_type": "application/pdf",
                "fetch_strategy": "onbase_download_bytes",
            }
            for row in selection["selected_packets"]
        ],
    }

    result = selected_manifest(selection, verified, manifest)
    assert len(result.resources) == 2
    assert all(
        resource.fetch_strategy == "onbase_download_bytes"
        for resource in result.resources
    )
    assert all(
        resource.expected_media_type == "application/pdf"
        for resource in result.resources
    )


def test_publisher_time_relation_never_claims_occurrence() -> None:
    observation = datetime.fromisoformat("2026-08-21T14:48:00-04:00")
    assert (
        _publisher_time_relation("2026-07-20T18:30:00-04:00", observation)
        == "at_or_before_observation"
    )
    assert (
        _publisher_time_relation("2026-09-14T18:30:00-04:00", observation)
        == "after_observation"
    )
    assert _publisher_time_relation(None, observation) == "unknown"
