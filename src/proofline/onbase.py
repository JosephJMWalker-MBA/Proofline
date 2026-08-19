"""Generic, auditable discovery for Hyland OnBase Agenda Online publishers.

The adapter follows only publisher-declared structures observed in the source contract:

meeting search → embedded SearchResults JSON → agenda tree → loadAgendaItem(id, false)
→ stable agenda-item endpoint.

Search and agenda-tree responses are supporting provenance. Agenda-item HTML is emitted as the
canonical watch manifest. No PDF URL is inferred and no numeric meeting/item IDs are swept.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .discovery import DiscoveryResult, manifest_to_dict
from .hashing import sha256_text
from .watcher import CorpusWatcher, ManifestResource, SourceManifest

_PLAN_SCHEMA = "proofline-onbase-agenda-plan/v1"
_SEARCH_RESULTS_MARKER = "showSearchResults(new SearchResults("
_AGENDA_ITEM_CALL_RE = re.compile(
    r"loadAgendaItem\(\s*(?P<item_id>\d+)\s*,\s*(?P<is_section>true|false)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class OnBaseAgendaPlan:
    name: str
    source_uri: str
    meeting_type_ids: tuple[int, ...]
    years: tuple[int, ...]
    schema: str = _PLAN_SCHEMA


@dataclass(frozen=True, slots=True)
class OnBaseMeeting:
    meeting_id: int
    name: str
    meeting_type_name: str | None
    time: str | None
    agenda_unique_name: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OnBaseAgendaItem:
    meeting_id: int
    item_id: int
    link_text: str


@dataclass(frozen=True, slots=True)
class OnBaseDiscoveryResult:
    discovery: DiscoveryResult
    meetings: tuple[OnBaseMeeting, ...]
    agenda_tree_count: int
    agenda_item_count: int

    def to_dict(self) -> dict:
        payload = self.discovery.to_dict()
        payload["onbase"] = {
            "meetings": [meeting.to_dict() for meeting in self.meetings],
            "meeting_count": len(self.meetings),
            "agenda_tree_count": self.agenda_tree_count,
            "agenda_item_count": self.agenda_item_count,
        }
        return payload


class _AgendaTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._parts: list[str] = []
        self.items: list[OnBaseAgendaItem] = []
        self.meeting_id: int | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if isinstance(href, str):
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        href = self._href
        text = " ".join("".join(self._parts).split())
        self._href = None
        self._parts = []
        match = _AGENDA_ITEM_CALL_RE.search(href)
        if not match or match.group("is_section").casefold() != "false":
            return
        if self.meeting_id is None:
            raise RuntimeError("agenda-tree parser meeting_id was not set")
        self.items.append(
            OnBaseAgendaItem(
                meeting_id=self.meeting_id,
                item_id=int(match.group("item_id")),
                link_text=text,
            )
        )


def load_onbase_agenda_plan(path: str | Path) -> OnBaseAgendaPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _PLAN_SCHEMA:
        raise ValueError(f"OnBase agenda plan schema must be {_PLAN_SCHEMA!r}")
    name = payload.get("name")
    source_uri = payload.get("source_uri")
    meeting_type_ids = payload.get("meeting_type_ids")
    years = payload.get("years")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("OnBase agenda plan name must be a non-empty string")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise ValueError("OnBase source_uri must be a non-empty string")
    parsed = urlsplit(source_uri)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OnBase source_uri must use http/https")
    if parsed.query or parsed.fragment:
        raise ValueError("OnBase source_uri must not include query or fragment")
    if not parsed.path.rstrip("/").casefold().endswith("/meetings"):
        raise ValueError("OnBase source_uri must identify the Agenda Online /Meetings endpoint")
    if (
        not isinstance(meeting_type_ids, list)
        or not meeting_type_ids
        or not all(isinstance(value, int) and value > 0 for value in meeting_type_ids)
    ):
        raise ValueError("meeting_type_ids must be a non-empty positive integer list")
    if (
        not isinstance(years, list)
        or not years
        or not all(isinstance(value, int) and 1900 <= value <= 2200 for value in years)
    ):
        raise ValueError("years must be a non-empty integer list")
    return OnBaseAgendaPlan(
        name=name.strip(),
        source_uri=source_uri.rstrip("/"),
        meeting_type_ids=tuple(sorted(set(meeting_type_ids))),
        years=tuple(sorted(set(years))),
    )


def onbase_search_uris(plan: OnBaseAgendaPlan) -> tuple[str, ...]:
    parsed = urlsplit(plan.source_uri)
    meeting_types = ",".join(str(value) for value in plan.meeting_type_ids)
    uris: list[str] = []
    for year in plan.years:
        query = urlencode(
            {
                "dropid": "11",
                "mtids": meeting_types,
                "dropsv": f"01/01/{year}",
                "dropev": f"12/31/{year}",
            }
        )
        uris.append(urlunsplit((parsed.scheme, parsed.netloc, parsed.path + "/Search", query, "")))
    return tuple(uris)


def _balanced_json_object(source: str, start: int) -> str:
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] != "{":
        raise ValueError("SearchResults marker was not followed by a JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        character = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise ValueError("unterminated SearchResults JSON object")


def extract_onbase_search_payloads(html: str) -> tuple[dict, ...]:
    payloads: list[dict] = []
    offset = 0
    while True:
        marker_index = html.find(_SEARCH_RESULTS_MARKER, offset)
        if marker_index < 0:
            break
        object_start = marker_index + len(_SEARCH_RESULTS_MARKER)
        serialized = _balanced_json_object(html, object_start)
        payload = json.loads(serialized)
        if isinstance(payload, dict):
            payloads.append(payload)
        offset = object_start + len(serialized)
    return tuple(payloads)


def discover_onbase_meetings(html: str) -> tuple[OnBaseMeeting, ...]:
    payloads = extract_onbase_search_payloads(html)
    meetings: dict[int, OnBaseMeeting] = {}
    for payload in payloads:
        raw_meetings = payload.get("Meetings")
        if not isinstance(raw_meetings, list):
            continue
        for raw in raw_meetings:
            if not isinstance(raw, dict) or raw.get("IsAgendaAvailable") is not True:
                continue
            meeting_id = raw.get("ID")
            name = raw.get("Name")
            if not isinstance(meeting_id, int) or meeting_id <= 0:
                continue
            if not isinstance(name, str) or not name.strip():
                continue
            candidate = OnBaseMeeting(
                meeting_id=meeting_id,
                name=" ".join(name.split()),
                meeting_type_name=(
                    " ".join(raw["MeetingTypeName"].split())
                    if isinstance(raw.get("MeetingTypeName"), str) and raw["MeetingTypeName"].strip()
                    else None
                ),
                time=(raw.get("Time") if isinstance(raw.get("Time"), str) else None),
                agenda_unique_name=(
                    raw.get("AgendaUniqueName")
                    if isinstance(raw.get("AgendaUniqueName"), str)
                    else None
                ),
            )
            previous = meetings.get(meeting_id)
            if previous is not None and previous != candidate:
                raise ValueError(f"OnBase meeting ID {meeting_id} has conflicting embedded metadata")
            meetings[meeting_id] = candidate
    return tuple(meetings[key] for key in sorted(meetings))


def _instance_root(meetings_uri: str) -> str:
    parsed = urlsplit(meetings_uri)
    path = parsed.path.rstrip("/")
    if not path.casefold().endswith("/meetings"):
        raise ValueError("OnBase meetings URI must end in /Meetings")
    root_path = path[: -len("/Meetings")] + "/"
    return urlunsplit((parsed.scheme, parsed.netloc, root_path, "", ""))


def onbase_agenda_tree_uri(plan: OnBaseAgendaPlan, meeting_id: int) -> str:
    root = _instance_root(plan.source_uri)
    query = urlencode(
        {
            "meetingId": str(meeting_id),
            "type": "agenda",
            "doctype": "1",
        }
    )
    return urljoin(root, "Documents/ViewAgenda") + "?" + query


def discover_onbase_agenda_items(
    html: str,
    *,
    meeting_id: int,
) -> tuple[OnBaseAgendaItem, ...]:
    parser = _AgendaTreeParser()
    parser.meeting_id = meeting_id
    parser.feed(html)
    parser.close()
    items: dict[int, OnBaseAgendaItem] = {}
    for item in parser.items:
        previous = items.get(item.item_id)
        if previous is not None and previous.link_text != item.link_text:
            raise ValueError(
                f"OnBase meeting {meeting_id} item {item.item_id} has conflicting agenda-tree labels"
            )
        items[item.item_id] = item
    return tuple(items[key] for key in sorted(items))


def onbase_agenda_item_uri(plan: OnBaseAgendaPlan, *, meeting_id: int, item_id: int) -> str:
    root = _instance_root(plan.source_uri)
    query = urlencode(
        {
            "meetingId": str(meeting_id),
            "itemId": str(item_id),
            "isSection": "false",
            "type": "agenda",
        }
    )
    return urljoin(root, "Meetings/ViewMeetingAgendaItem") + "?" + query


def _instance_slug(plan: OnBaseAgendaPlan) -> str:
    parsed = urlsplit(plan.source_uri)
    path = parsed.path.rstrip("/")[: -len("/Meetings")].strip("/")
    raw = f"{parsed.hostname or ''}-{path}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-")
    return slug or "onbase"


def _meeting_source_name(meeting: OnBaseMeeting) -> str:
    type_name = meeting.meeting_type_name or "Meeting"
    when = meeting.time or meeting.name
    return f"{type_name} — {meeting.name} — {when}"


class OnBaseAgendaDiscoverer:
    """Preserve search/tree provenance and derive canonical agenda-item resources."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.watcher = CorpusWatcher(self.state_dir)

    def _artifact_text(self, artifact_id: str) -> str:
        with self.watcher.store.connection() as connection:
            row = connection.execute(
                "SELECT stored_path FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"OnBase discovery artifact missing from store: {artifact_id}")
        return (self.state_dir / row["stored_path"]).read_text(encoding="utf-8", errors="replace")

    def run(self, plan: OnBaseAgendaPlan) -> OnBaseDiscoveryResult:
        index_artifacts: list[str] = []
        supporting_artifacts: list[str] = []
        meetings: dict[int, OnBaseMeeting] = {}

        search_resources = tuple(
            ManifestResource(
                source_uri=uri,
                source_name=f"OnBase meeting search — {plan.name}",
                native_identifier=(
                    f"onbase-{_instance_slug(plan)}-search-{plan.years[index]}"
                ),
                expected_media_type="text/html",
            )
            for index, uri in enumerate(onbase_search_uris(plan))
        )
        search_watch = self.watcher.run(
            SourceManifest(name=f"{plan.name}:onbase-search", resources=search_resources)
        )
        for result in search_watch["results"]:
            artifact_id = result.get("artifact_id")
            if not artifact_id:
                continue
            index_artifacts.append(artifact_id)
            for meeting in discover_onbase_meetings(self._artifact_text(artifact_id)):
                previous = meetings.get(meeting.meeting_id)
                if previous is not None and previous != meeting:
                    raise ValueError(
                        f"OnBase meeting {meeting.meeting_id} differs across discovery indexes"
                    )
                meetings[meeting.meeting_id] = meeting

        tree_resources = tuple(
            ManifestResource(
                source_uri=onbase_agenda_tree_uri(plan, meeting.meeting_id),
                source_name=f"{_meeting_source_name(meeting)} — Agenda tree",
                native_identifier=(
                    f"onbase-{_instance_slug(plan)}-meeting-{meeting.meeting_id}-agenda-tree"
                ),
                expected_media_type="text/html",
            )
            for meeting in (meetings[key] for key in sorted(meetings))
        )
        canonical: dict[str, ManifestResource] = {}
        if tree_resources:
            tree_watch = self.watcher.run(
                SourceManifest(name=f"{plan.name}:onbase-agenda-trees", resources=tree_resources)
            )
            meeting_by_tree_uri = {
                onbase_agenda_tree_uri(plan, meeting.meeting_id): meeting
                for meeting in meetings.values()
            }
            for result in tree_watch["results"]:
                artifact_id = result.get("artifact_id")
                tree_uri = result.get("source_uri")
                if not artifact_id or not tree_uri:
                    continue
                meeting = meeting_by_tree_uri.get(tree_uri)
                if meeting is None:
                    raise RuntimeError(f"unexpected OnBase agenda-tree result: {tree_uri}")
                supporting_artifacts.append(artifact_id)
                for item in discover_onbase_agenda_items(
                    self._artifact_text(artifact_id), meeting_id=meeting.meeting_id
                ):
                    source_uri = onbase_agenda_item_uri(
                        plan, meeting_id=meeting.meeting_id, item_id=item.item_id
                    )
                    canonical[source_uri] = ManifestResource(
                        source_uri=source_uri,
                        source_name=(
                            f"{_meeting_source_name(meeting)} — Agenda Item {item.item_id}"
                        ),
                        native_identifier=(
                            f"onbase-{_instance_slug(plan)}-meeting-{meeting.meeting_id}-item-{item.item_id}"
                        ),
                        expected_media_type="text/html",
                    )

        manifest = SourceManifest(
            name=f"{plan.name}:onbase-agenda-items",
            resources=tuple(canonical[uri] for uri in sorted(canonical)),
        )
        serialized = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
        discovery = DiscoveryResult(
            plan=plan.name,
            manifest=manifest,
            index_artifact_ids=tuple(index_artifacts),
            supporting_artifact_ids=tuple(supporting_artifacts),
            manifest_sha256=sha256_text(serialized),
        )
        return OnBaseDiscoveryResult(
            discovery=discovery,
            meetings=tuple(meetings[key] for key in sorted(meetings)),
            agenda_tree_count=len(supporting_artifacts),
            agenda_item_count=len(manifest.resources),
        )

    def write_manifest(self, result: OnBaseDiscoveryResult, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(
            manifest_to_dict(result.discovery.manifest), indent=2, sort_keys=True
        ) + "\n"
        destination.write_text(serialized, encoding="utf-8")
        return destination
