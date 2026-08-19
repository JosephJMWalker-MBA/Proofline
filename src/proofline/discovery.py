"""Auditable discovery of public-record resources from official index pages."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import (
    parse_qs,
    parse_qsl,
    urlencode,
    urljoin,
    urlparse,
    urlsplit,
    urlunsplit,
)

from .hashing import sha256_text
from .watcher import CorpusWatcher, ManifestResource, SourceManifest

_DISCOVERY_SCHEMA = "proofline-discovery-plan/v1"
_MEETING_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_NATIVE_ID_RE = re.compile(r"_([0-9]{8})-([0-9]+)")
_CIVICCLERK_EVENT_PATH_RE = re.compile(r"^/event/(\d+)/files/?$")
_CIVICCLERK_FILE_PATH_RE = re.compile(
    r"^/v1/Meetings/GetMeetingFile\(fileId=(\d+),plainText=false\)$"
)


@dataclass(frozen=True, slots=True)
class DiscoverySpec:
    kind: str
    source_uri: str
    categories: tuple[str, ...]
    years: tuple[int, ...]
    formats: tuple[str, ...] = ("html", "pdf")
    include_previous_versions: bool = True
    event_text: str | None = None
    file_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    name: str
    discoverers: tuple[DiscoverySpec, ...]
    schema: str = _DISCOVERY_SCHEMA


@dataclass(frozen=True, slots=True)
class DiscoveredLink:
    category: str
    meeting_label: str
    link_text: str
    source_uri: str


@dataclass(frozen=True, slots=True)
class SimpleLink:
    link_text: str
    source_uri: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    plan: str
    manifest: SourceManifest
    index_artifact_ids: tuple[str, ...]
    supporting_artifact_ids: tuple[str, ...]
    manifest_sha256: str

    def to_dict(self) -> dict:
        return {
            "plan": self.plan,
            "manifest": manifest_to_dict(self.manifest),
            "index_artifact_ids": list(self.index_artifact_ids),
            "supporting_artifact_ids": list(self.supporting_artifact_ids),
            "manifest_sha256": self.manifest_sha256,
        }


class _AgendaCenterParser(HTMLParser):
    """Capture links under h2 category / h3 meeting headings."""

    def __init__(self, base_uri: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_uri = base_uri
        self.category = ""
        self.meeting = ""
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._link_href: str | None = None
        self._link_category = ""
        self._link_meeting = ""
        self.links: list[DiscoveredLink] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.casefold()
        if tag in {"h2", "h3"}:
            self._capture = tag
            self._buffer = []
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._capture = "a"
                self._buffer = []
                self._link_href = href
                self._link_category = self.category
                self._link_meeting = self.meeting

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._capture != tag:
            return
        text = " ".join("".join(self._buffer).split())
        if tag == "h2":
            self.category = text
            self.meeting = ""
        elif tag == "h3":
            self.meeting = text
        elif tag == "a" and self._link_href:
            self.links.append(
                DiscoveredLink(
                    category=self._link_category,
                    meeting_label=self._link_meeting,
                    link_text=text,
                    source_uri=urljoin(self.base_uri, self._link_href),
                )
            )
        self._capture = None
        self._buffer = []
        self._link_href = None


class _SimpleLinkParser(HTMLParser):
    """Capture anchors while allowing nested markup inside link text."""

    def __init__(self, base_uri: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_uri = base_uri
        self._href: str | None = None
        self._parts: list[str] = []
        self.links: list[SimpleLink] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        text = " ".join("".join(self._parts).split())
        self.links.append(
            SimpleLink(
                link_text=text,
                source_uri=urljoin(self.base_uri, self._href),
            )
        )
        self._href = None
        self._parts = []


def _valid_years(raw: object) -> tuple[int, ...]:
    if not isinstance(raw, list) or not raw or not all(isinstance(value, int) for value in raw):
        raise ValueError("years must be a non-empty integer list")
    return tuple(raw)


def load_discovery_plan(path: str | Path) -> DiscoveryPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _DISCOVERY_SCHEMA:
        raise ValueError(f"discovery schema must be {_DISCOVERY_SCHEMA!r}")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("discovery plan name must be a non-empty string")
    raw_specs = payload.get("discoverers")
    if not isinstance(raw_specs, list) or not raw_specs:
        raise ValueError("discoverers must be a non-empty list")

    specs: list[DiscoverySpec] = []
    for raw in raw_specs:
        if not isinstance(raw, dict):
            raise ValueError("each discoverer must be an object")
        kind = raw.get("type")
        source_uri = raw.get("source_uri")
        parsed = urlparse(source_uri or "")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("discoverer source_uri must use http/https")
        years = _valid_years(raw.get("years"))

        if kind == "civicengage_agenda_center":
            categories = raw.get("categories")
            formats = raw.get("formats", ["html", "pdf"])
            if (
                not isinstance(categories, list)
                or not categories
                or not all(isinstance(value, str) and value for value in categories)
            ):
                raise ValueError("categories must be a non-empty string list")
            if (
                not isinstance(formats, list)
                or not formats
                or not all(value in {"html", "pdf", "packet"} for value in formats)
            ):
                raise ValueError("formats must contain html, pdf, and/or packet")
            specs.append(
                DiscoverySpec(
                    kind=kind,
                    source_uri=source_uri,
                    categories=tuple(categories),
                    years=years,
                    formats=tuple(formats),
                    include_previous_versions=bool(raw.get("include_previous_versions", True)),
                )
            )
            continue

        if kind == "civicclerk_calendar":
            event_text = raw.get("event_text")
            file_types = raw.get("file_types", ["Agenda"])
            if not isinstance(event_text, str) or not event_text.strip():
                raise ValueError("civicclerk_calendar event_text must be a non-empty string")
            if (
                not isinstance(file_types, list)
                or not file_types
                or not all(isinstance(value, str) and value for value in file_types)
            ):
                raise ValueError("civicclerk_calendar file_types must be a non-empty string list")
            specs.append(
                DiscoverySpec(
                    kind=kind,
                    source_uri=source_uri,
                    categories=(),
                    years=years,
                    formats=(),
                    include_previous_versions=False,
                    event_text=" ".join(event_text.split()),
                    file_types=tuple(file_types),
                )
            )
            continue

        raise ValueError(f"unsupported discoverer type: {kind!r}")

    return DiscoveryPlan(name=name, discoverers=tuple(specs))


def _meeting_year(label: str) -> int | None:
    match = _MEETING_YEAR_RE.search(label)
    return int(match.group(1)) if match else None


def _link_format(link: DiscoveredLink) -> str | None:
    text = link.link_text.casefold().strip()
    parsed = urlparse(link.source_uri)
    query = parse_qs(parsed.query)
    if text == "html" or query.get("html") == ["true"]:
        return "html"
    if text == "packet" or query.get("packet") == ["true"]:
        return "packet"
    if text == "pdf" and "/AgendaCenter/ViewFile/" in parsed.path:
        return "pdf"
    if text == "previous versions" and "/AgendaCenter/PreviousVersions/" in parsed.path:
        return "versions"
    return None


def _native_identifier(uri: str, fmt: str) -> str | None:
    match = _NATIVE_ID_RE.search(urlparse(uri).path)
    if not match:
        return None
    return f"civicengage-{match.group(1)}-{match.group(2)}-{fmt}"


def _resource_from_link(link: DiscoveredLink, fmt: str, *, archived: bool = False) -> ManifestResource:
    media_type = "text/html" if fmt == "html" else "application/pdf"
    label = f"ARCHIVED {fmt.upper()}" if archived else fmt.upper()
    identifier_format = f"archived-{fmt}" if archived else fmt
    return ManifestResource(
        source_uri=link.source_uri,
        source_name=f"{link.category} — {link.meeting_label} — {label}",
        native_identifier=_native_identifier(link.source_uri, identifier_format),
        expected_media_type=media_type,
    )


def discover_civicengage_resources(
    html: str,
    spec: DiscoverySpec,
) -> tuple[ManifestResource, ...]:
    """Discover current meeting records and published version-listing pages."""
    parser = _AgendaCenterParser(spec.source_uri)
    parser.feed(html)
    parser.close()

    wanted_categories = {value.casefold() for value in spec.categories}
    resources: dict[str, ManifestResource] = {}
    for link in parser.links:
        if link.category.casefold() not in wanted_categories:
            continue
        year = _meeting_year(link.meeting_label)
        if year not in spec.years:
            continue
        fmt = _link_format(link)
        if fmt == "versions":
            if not spec.include_previous_versions:
                continue
            resources[link.source_uri] = ManifestResource(
                source_uri=link.source_uri,
                source_name=f"{link.category} — {link.meeting_label} — VERSIONS",
                native_identifier=_native_identifier(link.source_uri, "versions"),
                expected_media_type="text/html",
            )
        elif fmt is not None and fmt in spec.formats:
            resources[link.source_uri] = _resource_from_link(link, fmt)

    return tuple(resources[uri] for uri in sorted(resources))


def discover_civicengage_previous_versions(
    html: str,
    *,
    listing_uri: str,
    spec: DiscoverySpec,
) -> tuple[ManifestResource, ...]:
    """Enumerate historical files explicitly linked by a Previous Versions page.

    Only `ArchivedAgenda` links are accepted. Current `Agenda` links are ignored
    so a historical listing cannot make the current record look like independent
    corroboration.
    """
    parser = _AgendaCenterParser(listing_uri)
    parser.feed(html)
    parser.close()

    wanted_categories = {value.casefold() for value in spec.categories}
    resources: dict[str, ManifestResource] = {}
    for link in parser.links:
        if link.category.casefold() not in wanted_categories:
            continue
        year = _meeting_year(link.meeting_label)
        if year not in spec.years:
            continue
        parsed = urlparse(link.source_uri)
        if "/AgendaCenter/ViewFile/ArchivedAgenda/" not in parsed.path:
            continue
        fmt = _link_format(link)
        if fmt is None or fmt not in spec.formats:
            continue
        resources[link.source_uri] = _resource_from_link(link, fmt, archived=True)

    return tuple(resources[uri] for uri in sorted(resources))


def civicclerk_calendar_month_uris(spec: DiscoverySpec) -> tuple[str, ...]:
    """Build a bounded month-by-month calendar listing set while preserving base filters."""
    if spec.kind != "civicclerk_calendar":
        raise ValueError("calendar month URIs require a civicclerk_calendar spec")
    parsed = urlsplit(spec.source_uri)
    base_query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    uris: list[str] = []
    for year in sorted(set(spec.years)):
        for month in range(1, 13):
            query = dict(base_query)
            query.update({"month": str(month), "view": "list", "year": str(year)})
            uris.append(
                urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urlencode(query),
                        "",
                    )
                )
            )
    return tuple(uris)


def discover_civicclerk_calendar_events(
    html: str,
    *,
    listing_uri: str,
    spec: DiscoverySpec,
) -> tuple[ManifestResource, ...]:
    """Discover exact-matching official calendar event pages, never arbitrary site links."""
    if spec.kind != "civicclerk_calendar" or not spec.event_text:
        raise ValueError("calendar event discovery requires a civicclerk_calendar spec")
    parser = _SimpleLinkParser(listing_uri)
    parser.feed(html)
    parser.close()
    listing = urlsplit(listing_uri)
    wanted_text = " ".join(spec.event_text.split()).casefold()
    resources: dict[str, ManifestResource] = {}
    for link in parser.links:
        if " ".join(link.link_text.split()).casefold() != wanted_text:
            continue
        candidate = urlsplit(link.source_uri)
        if candidate.scheme not in {"http", "https"} or candidate.hostname != listing.hostname:
            continue
        query = parse_qs(candidate.query)
        event_ids = query.get("EID") or query.get("eid")
        if not event_ids or not event_ids[0].isdigit():
            continue
        event_id = event_ids[0]
        resources[link.source_uri] = ManifestResource(
            source_uri=link.source_uri,
            source_name=f"Official calendar event — {spec.event_text} — EID {event_id}",
            native_identifier=f"calendar-event-{event_id}",
            expected_media_type="text/html",
        )
    return tuple(resources[uri] for uri in sorted(resources))


def discover_civicclerk_event_metadata(
    html: str,
    *,
    event_uri: str,
) -> tuple[ManifestResource, ...]:
    """Derive stable CivicClerk event metadata endpoints from publisher-linked portal pages."""
    parser = _SimpleLinkParser(event_uri)
    parser.feed(html)
    parser.close()
    resources: dict[str, ManifestResource] = {}
    for link in parser.links:
        parsed = urlsplit(link.source_uri)
        hostname = (parsed.hostname or "").lower()
        suffix = ".portal.civicclerk.com"
        if parsed.scheme != "https" or not hostname.endswith(suffix):
            continue
        tenant = hostname[: -len(suffix)]
        if not tenant or "." in tenant:
            continue
        match = _CIVICCLERK_EVENT_PATH_RE.fullmatch(parsed.path)
        if not match:
            continue
        event_id = match.group(1)
        metadata_uri = f"https://{tenant}.api.civicclerk.com/v1/Events/{event_id}"
        resources[metadata_uri] = ManifestResource(
            source_uri=metadata_uri,
            source_name=f"CivicClerk event metadata — {tenant} — {event_id}",
            native_identifier=f"civicclerk-{tenant}-event-{event_id}",
            expected_media_type="application/json",
        )
    return tuple(resources[uri] for uri in sorted(resources))


def _event_year(value: object) -> int | None:
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _identifier_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "file"


def discover_civicclerk_published_files(
    payload: object,
    *,
    metadata_uri: str,
    spec: DiscoverySpec,
) -> tuple[ManifestResource, ...]:
    """Emit stable published file APIs from preserved CivicClerk event metadata."""
    if spec.kind != "civicclerk_calendar":
        raise ValueError("published CivicClerk files require a civicclerk_calendar spec")
    metadata = urlsplit(metadata_uri)
    hostname = (metadata.hostname or "").lower()
    suffix = ".api.civicclerk.com"
    if metadata.scheme != "https" or not hostname.endswith(suffix):
        raise ValueError("metadata_uri must be an HTTPS CivicClerk API event URI")
    tenant = hostname[: -len(suffix)]
    if not tenant or "." in tenant:
        raise ValueError("metadata_uri must identify one CivicClerk tenant")
    if not isinstance(payload, dict):
        raise ValueError("CivicClerk event metadata must be a JSON object")
    if _event_year(payload.get("eventDate")) not in spec.years:
        return ()
    files = payload.get("publishedFiles")
    if not isinstance(files, list):
        return ()

    wanted_types = {value.casefold() for value in spec.file_types}
    event_name = payload.get("eventName") if isinstance(payload.get("eventName"), str) else "Event"
    category_name = (
        payload.get("categoryName") if isinstance(payload.get("categoryName"), str) else "Public meeting"
    )
    event_date = payload.get("eventDate") if isinstance(payload.get("eventDate"), str) else "unknown-date"
    resources: dict[str, ManifestResource] = {}

    for item in files:
        if not isinstance(item, dict):
            continue
        file_type = item.get("type")
        file_id = item.get("fileId")
        source_uri = item.get("url")
        if not isinstance(file_type, str) or file_type.casefold() not in wanted_types:
            continue
        if not isinstance(file_id, int) or file_id < 0:
            continue
        if not isinstance(source_uri, str):
            continue
        parsed = urlsplit(source_uri)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != hostname:
            continue
        match = _CIVICCLERK_FILE_PATH_RE.fullmatch(parsed.path)
        if not match or int(match.group(1)) != file_id:
            continue
        if parsed.query or parsed.fragment:
            continue
        name = item.get("name") if isinstance(item.get("name"), str) else file_type
        resources[source_uri] = ManifestResource(
            source_uri=source_uri,
            source_name=(
                f"{category_name} — {event_date[:10]} — {event_name} — {file_type}: {name}"
            ),
            native_identifier=(
                f"civicclerk-{tenant}-file-{file_id}-{_identifier_slug(file_type)}"
            ),
            expected_media_type="application/pdf",
            fetch_strategy="civicclerk_blob",
        )

    return tuple(resources[uri] for uri in sorted(resources))


def manifest_to_dict(manifest: SourceManifest) -> dict:
    resources: list[dict] = []
    for resource in manifest.resources:
        payload = asdict(resource)
        resources.append({key: value for key, value in payload.items() if value is not None})
    return {
        "schema": manifest.schema,
        "name": manifest.name,
        "resources": resources,
    }


class SourceDiscoverer:
    """Preserve official discovery pages, then derive a deterministic watch manifest."""

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
            raise RuntimeError(f"discovery artifact missing from store: {artifact_id}")
        return (self.state_dir / row["stored_path"]).read_text(encoding="utf-8", errors="replace")

    def _artifact_json(self, artifact_id: str) -> object:
        try:
            return json.loads(self._artifact_text(artifact_id))
        except json.JSONDecodeError as exc:
            raise ValueError(f"supporting artifact is not valid JSON: {artifact_id}") from exc

    def _run_civicengage(
        self,
        *,
        plan: DiscoveryPlan,
        spec: DiscoverySpec,
        combined: dict[str, ManifestResource],
        index_artifacts: list[str],
        supporting_artifacts: list[str],
    ) -> None:
        index_manifest = SourceManifest(
            name=f"{plan.name}:discovery-index",
            resources=(
                ManifestResource(
                    source_uri=spec.source_uri,
                    source_name=f"Discovery index: {plan.name}",
                    expected_media_type="text/html",
                ),
            ),
        )
        watched = self.watcher.run(index_manifest)
        item = watched["results"][0]
        artifact_id = item.get("artifact_id")
        if not artifact_id:
            return
        index_artifacts.append(artifact_id)

        raw_html = self._artifact_text(artifact_id)
        primary = discover_civicengage_resources(raw_html, spec)
        version_listings = [
            resource
            for resource in primary
            if "/AgendaCenter/PreviousVersions/" in urlparse(resource.source_uri).path
        ]
        for resource in primary:
            if resource not in version_listings:
                combined[resource.source_uri] = resource

        if not spec.include_previous_versions or not version_listings:
            return
        version_manifest = SourceManifest(
            name=f"{plan.name}:version-listings",
            resources=tuple(version_listings),
        )
        version_watch = self.watcher.run(version_manifest)
        for result in version_watch["results"]:
            version_artifact_id = result.get("artifact_id")
            source_uri = result.get("source_uri")
            if not version_artifact_id or not source_uri:
                continue
            supporting_artifacts.append(version_artifact_id)
            version_html = self._artifact_text(version_artifact_id)
            for archived in discover_civicengage_previous_versions(
                version_html,
                listing_uri=source_uri,
                spec=spec,
            ):
                combined[archived.source_uri] = archived

    def _run_civicclerk_calendar(
        self,
        *,
        plan: DiscoveryPlan,
        spec: DiscoverySpec,
        combined: dict[str, ManifestResource],
        index_artifacts: list[str],
        supporting_artifacts: list[str],
    ) -> None:
        month_resources = tuple(
            ManifestResource(
                source_uri=uri,
                source_name=f"Discovery calendar index: {plan.name}",
                expected_media_type="text/html",
            )
            for uri in civicclerk_calendar_month_uris(spec)
        )
        month_watch = self.watcher.run(
            SourceManifest(name=f"{plan.name}:calendar-indexes", resources=month_resources)
        )

        event_pages: dict[str, ManifestResource] = {}
        for result in month_watch["results"]:
            artifact_id = result.get("artifact_id")
            listing_uri = result.get("source_uri")
            if not artifact_id or not listing_uri:
                continue
            index_artifacts.append(artifact_id)
            for resource in discover_civicclerk_calendar_events(
                self._artifact_text(artifact_id),
                listing_uri=listing_uri,
                spec=spec,
            ):
                event_pages[resource.source_uri] = resource

        if not event_pages:
            return
        event_watch = self.watcher.run(
            SourceManifest(
                name=f"{plan.name}:calendar-events",
                resources=tuple(event_pages[uri] for uri in sorted(event_pages)),
            )
        )
        metadata_resources: dict[str, ManifestResource] = {}
        for result in event_watch["results"]:
            artifact_id = result.get("artifact_id")
            event_uri = result.get("source_uri")
            if not artifact_id or not event_uri:
                continue
            supporting_artifacts.append(artifact_id)
            for resource in discover_civicclerk_event_metadata(
                self._artifact_text(artifact_id),
                event_uri=event_uri,
            ):
                metadata_resources[resource.source_uri] = resource

        if not metadata_resources:
            return
        metadata_watch = self.watcher.run(
            SourceManifest(
                name=f"{plan.name}:civicclerk-event-metadata",
                resources=tuple(metadata_resources[uri] for uri in sorted(metadata_resources)),
            )
        )
        for result in metadata_watch["results"]:
            artifact_id = result.get("artifact_id")
            metadata_uri = result.get("source_uri")
            if not artifact_id or not metadata_uri:
                continue
            supporting_artifacts.append(artifact_id)
            for resource in discover_civicclerk_published_files(
                self._artifact_json(artifact_id),
                metadata_uri=metadata_uri,
                spec=spec,
            ):
                combined[resource.source_uri] = resource

    def run(self, plan: DiscoveryPlan) -> DiscoveryResult:
        combined: dict[str, ManifestResource] = {}
        index_artifacts: list[str] = []
        supporting_artifacts: list[str] = []

        for spec in plan.discoverers:
            if spec.kind == "civicengage_agenda_center":
                self._run_civicengage(
                    plan=plan,
                    spec=spec,
                    combined=combined,
                    index_artifacts=index_artifacts,
                    supporting_artifacts=supporting_artifacts,
                )
            elif spec.kind == "civicclerk_calendar":
                self._run_civicclerk_calendar(
                    plan=plan,
                    spec=spec,
                    combined=combined,
                    index_artifacts=index_artifacts,
                    supporting_artifacts=supporting_artifacts,
                )
            else:
                raise ValueError(f"unsupported discoverer type: {spec.kind!r}")

        manifest = SourceManifest(
            name=f"{plan.name}:discovered",
            resources=tuple(combined[uri] for uri in sorted(combined)),
        )
        serialized = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
        return DiscoveryResult(
            plan=plan.name,
            manifest=manifest,
            index_artifact_ids=tuple(index_artifacts),
            supporting_artifact_ids=tuple(supporting_artifacts),
            manifest_sha256=sha256_text(serialized),
        )

    def write_manifest(self, result: DiscoveryResult, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(manifest_to_dict(result.manifest), indent=2, sort_keys=True) + "\n"
        destination.write_text(serialized, encoding="utf-8")
        return destination
