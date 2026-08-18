"""Auditable discovery of public-record resources from official index pages."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from .hashing import sha256_text
from .watcher import CorpusWatcher, ManifestResource, SourceManifest

_DISCOVERY_SCHEMA = "proofline-discovery-plan/v1"
_MEETING_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_NATIVE_ID_RE = re.compile(r"_([0-9]{8})-([0-9]+)")


@dataclass(frozen=True, slots=True)
class DiscoverySpec:
    kind: str
    source_uri: str
    categories: tuple[str, ...]
    years: tuple[int, ...]
    formats: tuple[str, ...] = ("html", "pdf")
    include_previous_versions: bool = True


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
        if kind != "civicengage_agenda_center":
            raise ValueError(f"unsupported discoverer type: {kind!r}")
        source_uri = raw.get("source_uri")
        parsed = urlparse(source_uri or "")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("discoverer source_uri must use http/https")
        categories = raw.get("categories")
        years = raw.get("years")
        formats = raw.get("formats", ["html", "pdf"])
        if (
            not isinstance(categories, list)
            or not categories
            or not all(isinstance(v, str) and v for v in categories)
        ):
            raise ValueError("categories must be a non-empty string list")
        if not isinstance(years, list) or not years or not all(isinstance(v, int) for v in years):
            raise ValueError("years must be a non-empty integer list")
        if (
            not isinstance(formats, list)
            or not formats
            or not all(v in {"html", "pdf", "packet"} for v in formats)
        ):
            raise ValueError("formats must contain html, pdf, and/or packet")
        specs.append(
            DiscoverySpec(
                kind=kind,
                source_uri=source_uri,
                categories=tuple(categories),
                years=tuple(years),
                formats=tuple(formats),
                include_previous_versions=bool(raw.get("include_previous_versions", True)),
            )
        )
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

    def run(self, plan: DiscoveryPlan) -> DiscoveryResult:
        combined: dict[str, ManifestResource] = {}
        index_artifacts: list[str] = []
        supporting_artifacts: list[str] = []

        for spec in plan.discoverers:
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
                continue
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

            if spec.include_previous_versions and version_listings:
                version_manifest = SourceManifest(
                    name=f"{plan.name}:version-listings",
                    resources=tuple(version_listings),
                )
                version_watch = self.watcher.run(version_manifest)
                resource_by_uri = {item.source_uri: item for item in version_listings}
                for result in version_watch["results"]:
                    version_artifact_id = result.get("artifact_id")
                    source_uri = result.get("source_uri")
                    if not version_artifact_id or source_uri not in resource_by_uri:
                        continue
                    supporting_artifacts.append(version_artifact_id)
                    version_html = self._artifact_text(version_artifact_id)
                    for archived in discover_civicengage_previous_versions(
                        version_html,
                        listing_uri=source_uri,
                        spec=spec,
                    ):
                        combined[archived.source_uri] = archived

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
