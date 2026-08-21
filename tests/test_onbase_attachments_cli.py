from __future__ import annotations

from types import SimpleNamespace

from proofline.onbase import OnBaseMeeting
from proofline.onbase_attachments_cli import _canonical_payload


def test_attachment_run_preserves_structured_meeting_metadata() -> None:
    meeting = OnBaseMeeting(
        meeting_id=77,
        name="March 9, 2026",
        meeting_type_name="City Council Meeting",
        time="2026-03-09T18:30:00-04:00",
        agenda_unique_name="agenda-77",
    )
    agenda_result = SimpleNamespace(
        meetings=(meeting,),
        agenda_item_count=42,
        discovery=SimpleNamespace(manifest_sha256="manifest-sha"),
    )
    canonical_sync = {
        "counts": {
            "new": 0,
            "changed": 0,
            "unchanged": 42,
            "unavailable": 0,
        }
    }

    payload = _canonical_payload(agenda_result, canonical_sync)

    assert payload == {
        "meeting_count": 1,
        "meetings": [
            {
                "meeting_id": 77,
                "name": "March 9, 2026",
                "meeting_type_name": "City Council Meeting",
                "time": "2026-03-09T18:30:00-04:00",
                "agenda_unique_name": "agenda-77",
            }
        ],
        "agenda_item_count": 42,
        "manifest_sha256": "manifest-sha",
        "sync_counts": canonical_sync["counts"],
    }
