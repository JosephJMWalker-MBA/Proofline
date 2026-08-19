from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from proofline.onbase import (
    OnBaseAgendaDiscoverer,
    OnBaseAgendaPlan,
    discover_onbase_agenda_items,
    discover_onbase_meetings,
    extract_onbase_search_payloads,
    load_onbase_agenda_plan,
    onbase_agenda_item_uri,
    onbase_agenda_tree_uri,
    onbase_search_uris,
)


def _search_html(meetings: list[dict]) -> str:
    payload = {
        "MeetingTypeIDs": [101],
        "DateRangeOptionID": 11,
        "Meetings": meetings,
        "Nested": {"safe": "brace } inside string", "items": [{"x": 1}]},
    }
    return (
        "<html><body><script>"
        "showSearchResults(new SearchResults("
        + json.dumps(payload)
        + "));</script></body></html>"
    )


def _meeting(meeting_id: int, name: str, *, agenda: bool = True) -> dict:
    return {
        "ID": meeting_id,
        "Name": name,
        "MeetingTypeName": "City Council Meeting",
        "Time": f"2026-01-{meeting_id:02d}T18:30:00-05:00",
        "IsAgendaAvailable": agenda,
        "AgendaUniqueName": f"agenda-{meeting_id}",
    }


def test_search_uri_is_bounded_by_declared_year_and_meeting_type() -> None:
    plan = OnBaseAgendaPlan(
        name="fixture",
        source_uri="https://records.example.gov/OnBaseAgendaOnline/Meetings",
        meeting_type_ids=(101, 105),
        years=(2025, 2026),
    )
    uris = onbase_search_uris(plan)
    assert len(uris) == 2
    first = urlsplit(uris[0])
    query = parse_qs(first.query)
    assert first.path == "/OnBaseAgendaOnline/Meetings/Search"
    assert query == {
        "dropid": ["11"],
        "mtids": ["101,105"],
        "dropsv": ["01/01/2025"],
        "dropev": ["12/31/2025"],
    }


def test_embedded_search_json_is_parsed_without_evaluating_javascript() -> None:
    html = _search_html([_meeting(1, "January 5, 2026"), _meeting(2, "January 12, 2026", agenda=False)])
    payloads = extract_onbase_search_payloads(html)
    assert len(payloads) == 1
    assert payloads[0]["Nested"]["safe"] == "brace } inside string"
    meetings = discover_onbase_meetings(html)
    assert [meeting.meeting_id for meeting in meetings] == [1]
    assert meetings[0].agenda_unique_name == "agenda-1"


def test_conflicting_metadata_for_same_meeting_id_is_rejected() -> None:
    html = (
        _search_html([_meeting(1, "January 5, 2026")])
        + _search_html([_meeting(1, "DIFFERENT NAME")])
    )
    with pytest.raises(ValueError, match="conflicting embedded metadata"):
        discover_onbase_meetings(html)


def test_agenda_tree_accepts_only_non_section_publisher_item_calls() -> None:
    html = """
    <html><body>
      <a href="javascript:loadAgendaItem(10,true);">SECTION</a>
      <a href="javascript:loadAgendaItem(11,false);">ORDINANCE Alpha</a>
      <a href="javascript:loadAgendaItem(11,false);"><strong>ORDINANCE Alpha</strong></a>
      <a href="javascript:otherFunction(12,false);">Ignore</a>
    </body></html>
    """
    items = discover_onbase_agenda_items(html, meeting_id=7)
    assert len(items) == 1
    assert items[0].meeting_id == 7
    assert items[0].item_id == 11
    assert items[0].link_text == "ORDINANCE Alpha"


def test_generated_tree_and_item_uris_stay_on_the_declared_instance() -> None:
    plan = OnBaseAgendaPlan(
        name="fixture",
        source_uri="https://records.example.gov/MyAgenda/Meetings",
        meeting_type_ids=(101,),
        years=(2026,),
    )
    assert onbase_agenda_tree_uri(plan, 77) == (
        "https://records.example.gov/MyAgenda/Documents/ViewAgenda?meetingId=77&type=agenda&doctype=1"
    )
    assert onbase_agenda_item_uri(plan, meeting_id=77, item_id=88) == (
        "https://records.example.gov/MyAgenda/Meetings/ViewMeetingAgendaItem?meetingId=77&itemId=88&isSection=false&type=agenda"
    )


def test_plan_loader_rejects_query_bearing_or_non_meetings_sources(tmp_path) -> None:
    payload = {
        "schema": "proofline-onbase-agenda-plan/v1",
        "name": "fixture",
        "source_uri": "https://records.example.gov/Agenda/Meetings?x=1",
        "meeting_type_ids": [101],
        "years": [2026],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must not include query"):
        load_onbase_agenda_plan(path)
    payload["source_uri"] = "https://records.example.gov/Agenda/Home"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="/Meetings endpoint"):
        load_onbase_agenda_plan(path)


class _OnBaseHandler(BaseHTTPRequestHandler):
    server_version = "ProoflineOnBaseFixture/1"

    def log_message(self, format, *args):
        return

    def _html(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/OnBaseAgendaOnline/Meetings/Search":
            assert query["dropid"] == ["11"]
            assert query["mtids"] == ["101"]
            assert query["dropsv"] == ["01/01/2026"]
            assert query["dropev"] == ["12/31/2026"]
            self._html(
                _search_html(
                    [
                        _meeting(10, "January 10, 2026"),
                        _meeting(11, "January 11, 2026"),
                        _meeting(12, "January 12, 2026", agenda=False),
                    ]
                )
            )
            return
        if parsed.path == "/OnBaseAgendaOnline/Documents/ViewAgenda":
            meeting_id = int(query["meetingId"][0])
            if meeting_id == 10:
                self._html(
                    '<html><body><a href="javascript:loadAgendaItem(100,true);">SECTION</a>'
                    '<a href="javascript:loadAgendaItem(101,false);">ORDINANCE Alpha</a></body></html>'
                )
            elif meeting_id == 11:
                self._html(
                    '<html><body><a href="javascript:loadAgendaItem(201,false);">RESOLUTION Beta</a></body></html>'
                )
            else:
                self._html("missing", status=404)
            return
        if parsed.path == "/OnBaseAgendaOnline/Meetings/ViewMeetingAgendaItem":
            meeting_id = query["meetingId"][0]
            item_id = query["itemId"][0]
            assert query["isSection"] == ["false"]
            assert query["type"] == ["agenda"]
            self._html(
                "<html><body><main><h1>Item Details</h1><p>"
                f"Meeting {meeting_id} item {item_id}: ORDINANCE authorizing a public contract "
                "with enough substantive source text for deterministic extraction and review."
                "</p></main></body></html>"
            )
            return
        self._html("not found", status=404)


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OnBaseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_full_discoverer_preserves_support_and_emits_stable_canonical_items(tmp_path) -> None:
    server, thread = _serve()
    try:
        host, port = server.server_address
        plan = OnBaseAgendaPlan(
            name="fixture-onbase",
            source_uri=f"http://{host}:{port}/OnBaseAgendaOnline/Meetings",
            meeting_type_ids=(101,),
            years=(2026,),
        )
        state = tmp_path / "state"
        discoverer = OnBaseAgendaDiscoverer(state)
        first = discoverer.run(plan)

        assert len(first.meetings) == 2
        assert first.agenda_tree_count == 2
        assert first.agenda_item_count == 2
        assert len(first.discovery.index_artifact_ids) == 1
        assert len(first.discovery.supporting_artifact_ids) == 2
        assert len(first.discovery.manifest.resources) == 2
        assert all(resource.expected_media_type == "text/html" for resource in first.discovery.manifest.resources)
        assert all("ViewMeetingAgendaItem" in resource.source_uri for resource in first.discovery.manifest.resources)
        assert {resource.native_identifier.rsplit("-", 1)[-1] for resource in first.discovery.manifest.resources} == {"101", "201"}

        watched = discoverer.watcher.run(first.discovery.manifest)
        assert watched["counts"]["new"] == 2
        assert watched["counts"]["unavailable"] == 0
        assert all(result["artifact_id"] for result in watched["results"])

        second = discoverer.run(plan)
        assert second.discovery.manifest_sha256 == first.discovery.manifest_sha256
        assert [meeting.meeting_id for meeting in second.meetings] == [10, 11]
        second_watch = discoverer.watcher.run(second.discovery.manifest)
        assert second_watch["counts"]["unchanged"] == 2
        assert second_watch["counts"]["unavailable"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
