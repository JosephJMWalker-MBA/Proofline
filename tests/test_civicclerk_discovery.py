from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from proofline import SourceManifest
from proofline.discovery import (
    DiscoverySpec,
    civicclerk_calendar_month_uris,
    discover_civicclerk_calendar_events,
    discover_civicclerk_event_metadata,
    discover_civicclerk_published_files,
    load_discovery_plan,
    manifest_to_dict,
)


def _spec() -> DiscoverySpec:
    return DiscoverySpec(
        kind="civicclerk_calendar",
        source_uri="https://city.example.gov/calendar.aspx?CID=31",
        categories=(),
        years=(2026,),
        formats=(),
        include_previous_versions=False,
        event_text="City Council Regular Meeting Agenda (PDF)",
        file_types=("Agenda",),
    )


def test_calendar_month_uris_are_bounded_and_preserve_official_filter() -> None:
    uris = civicclerk_calendar_month_uris(_spec())
    assert len(uris) == 12
    assert len(set(uris)) == 12
    first = urlsplit(uris[0])
    last = urlsplit(uris[-1])
    assert first.hostname == "city.example.gov"
    assert parse_qs(first.query) == {
        "CID": ["31"],
        "month": ["1"],
        "view": ["list"],
        "year": ["2026"],
    }
    assert parse_qs(last.query)["month"] == ["12"]


def test_calendar_discovery_requires_exact_event_text_and_same_host() -> None:
    listing_uri = "https://city.example.gov/calendar.aspx?CID=31&month=1&view=list&year=2026"
    html = """
    <a href="/Calendar.aspx?EID=2425"><span>City Council Regular Meeting Agenda (PDF)</span></a>
    <a href="/Calendar.aspx?EID=2426">City Council Regular Meeting</a>
    <a href="https://evil.example/Calendar.aspx?EID=9999">City Council Regular Meeting Agenda (PDF)</a>
    """
    resources = discover_civicclerk_calendar_events(html, listing_uri=listing_uri, spec=_spec())
    assert len(resources) == 1
    assert resources[0].source_uri == "https://city.example.gov/Calendar.aspx?EID=2425"
    assert resources[0].native_identifier == "calendar-event-2425"
    assert resources[0].expected_media_type == "text/html"


def test_event_page_derives_only_structurally_valid_civicclerk_metadata() -> None:
    event_uri = "https://city.example.gov/Calendar.aspx?EID=2425"
    html = """
    <a href="https://cantonoh.portal.civicclerk.com/event/2067/files">Download Agenda</a>
    <a href="https://cantonoh.portal.civicclerk.com/events/999/files">Wrong path</a>
    <a href="https://other.example/event/123/files">Untrusted portal</a>
    """
    resources = discover_civicclerk_event_metadata(html, event_uri=event_uri)
    assert len(resources) == 1
    assert resources[0].source_uri == "https://cantonoh.api.civicclerk.com/v1/Events/2067"
    assert resources[0].native_identifier == "civicclerk-cantonoh-event-2067"
    assert resources[0].expected_media_type == "application/json"


def test_metadata_emits_only_requested_same_tenant_matching_file_ids() -> None:
    metadata_uri = "https://cantonoh.api.civicclerk.com/v1/Events/2067"
    payload = {
        "eventName": "City Council Regular Meeting Agenda (PDF)",
        "categoryName": "City Council",
        "eventDate": "2026-01-05T19:00:00Z",
        "publishedFiles": [
            {
                "fileId": 3695,
                "fileType": 1,
                "name": "Agenda 1/5/26",
                "type": "Agenda",
                "url": (
                    "https://cantonoh.api.civicclerk.com/v1/Meetings/"
                    "GetMeetingFile(fileId=3695,plainText=false)"
                ),
            },
            {
                "fileId": 3696,
                "fileType": 2,
                "name": "Packet 1/5/26",
                "type": "Packet",
                "url": (
                    "https://cantonoh.api.civicclerk.com/v1/Meetings/"
                    "GetMeetingFile(fileId=3696,plainText=false)"
                ),
            },
            {
                "fileId": 4000,
                "fileType": 1,
                "name": "Host mismatch",
                "type": "Agenda",
                "url": (
                    "https://evil.example/v1/Meetings/"
                    "GetMeetingFile(fileId=4000,plainText=false)"
                ),
            },
            {
                "fileId": 5000,
                "fileType": 1,
                "name": "ID mismatch",
                "type": "Agenda",
                "url": (
                    "https://cantonoh.api.civicclerk.com/v1/Meetings/"
                    "GetMeetingFile(fileId=5001,plainText=false)"
                ),
            },
        ],
    }
    resources = discover_civicclerk_published_files(payload, metadata_uri=metadata_uri, spec=_spec())
    assert len(resources) == 1
    resource = resources[0]
    assert resource.native_identifier == "civicclerk-cantonoh-file-3695-agenda"
    assert resource.expected_media_type == "application/pdf"
    assert resource.fetch_strategy == "civicclerk_blob"
    assert "City Council" in (resource.source_name or "")
    assert "2026-01-05" in (resource.source_name or "")

    serialized = manifest_to_dict(SourceManifest(name="fixture", resources=resources))
    assert serialized["resources"][0]["fetch_strategy"] == "civicclerk_blob"


def test_metadata_outside_scoped_year_emits_no_files() -> None:
    payload = {
        "eventDate": "2025-12-31T19:00:00Z",
        "publishedFiles": [
            {
                "fileId": 1,
                "type": "Agenda",
                "url": (
                    "https://cantonoh.api.civicclerk.com/v1/Meetings/"
                    "GetMeetingFile(fileId=1,plainText=false)"
                ),
            }
        ],
    }
    assert (
        discover_civicclerk_published_files(
            payload,
            metadata_uri="https://cantonoh.api.civicclerk.com/v1/Events/1",
            spec=_spec(),
        )
        == ()
    )


def test_discovery_plan_accepts_mixed_civicengage_and_civicclerk_sources(tmp_path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-discovery-plan/v1",
                "name": "mixed public records",
                "discoverers": [
                    {
                        "type": "civicengage_agenda_center",
                        "source_uri": "https://city.example.gov/AgendaCenter",
                        "categories": ["Board of Control"],
                        "years": [2026],
                        "formats": ["pdf"],
                        "include_previous_versions": True,
                    },
                    {
                        "type": "civicclerk_calendar",
                        "source_uri": "https://city.example.gov/calendar.aspx?CID=31",
                        "years": [2026],
                        "event_text": "City Council Regular Meeting Agenda (PDF)",
                        "file_types": ["Agenda"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = load_discovery_plan(path)
    assert [spec.kind for spec in plan.discoverers] == [
        "civicengage_agenda_center",
        "civicclerk_calendar",
    ]
    assert plan.discoverers[1].categories == ()
    assert plan.discoverers[1].file_types == ("Agenda",)
