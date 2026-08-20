"""Publisher-linked OnBase Supporting Documents discovery and transport.

The stable source identity is the publisher-declared ``DownloadFile`` URI found in a
preserved agenda-item artifact. The actual bytes are fetched only after the official
HTML wrapper explicitly declares the ``DownloadFileBytes`` transport transformation.

This module deliberately does not guess attachment IDs, infer links from filenames, or
treat text similarity as relationship evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .discovery import manifest_to_dict
from .hashing import sha256_text, source_id_from_uri
from .onbase import OnBaseAgendaPlan
from .relations import RelationStore
from .watch_storage import WatcherStore
from .watcher import CorpusWatcher, ManifestResource, SourceManifest

FETCH_STRATEGY = "onbase_download_bytes"
RELATION_TYPE = "supporting_document_of"
RELATION_METHOD = "onbase_supporting_document_link"
RELATION_METHOD_VERSION = "1"
_MAX_WRAPPER_BYTES = 256 * 1024
_USER_AGENT = "Proofline/0.1 OnBase supporting-document watcher"
_WRAPPER_DECLARATION_RE = re.compile(
    r"""window\.location(?:\.toString\(\))?\.replace\(\s*["']DownloadFile["']\s*,\s*["']DownloadFileBytes["']\s*\)""",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class OnBaseAttachmentRelation:
    source_uri: str
    parent_source_uri: str
    parent_artifact_id: str
    parent_artifact_sha256: str
    meeting_id: int
    item_id: int
    publish_id: int
    link_text: str
    raw_href: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OnBaseAttachmentRejection:
    parent_source_uri: str
    parent_artifact_id: str
    link_text: str
    raw_href: str
    resolved_uri: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OnBaseAttachmentDiscoveryResult:
    manifest: SourceManifest
    relations: tuple[OnBaseAttachmentRelation, ...]
    rejected_links: tuple[OnBaseAttachmentRejection, ...]
    parent_item_count: int
    items_with_support_marker: int
    items_with_accepted_links: int
    manifest_sha256: str

    def to_dict(self) -> dict:
        return {
            "schema": "proofline-onbase-attachment-discovery/v1",
            "manifest": manifest_to_dict(self.manifest),
            "manifest_sha256": self.manifest_sha256,
            "parent_item_count": self.parent_item_count,
            "items_with_support_marker": self.items_with_support_marker,
            "items_with_accepted_links": self.items_with_accepted_links,
            "relation_count": len(self.relations),
            "rejected_link_count": len(self.rejected_links),
            "relations": [item.to_dict() for item in self.relations],
            "rejected_links": [item.to_dict() for item in self.rejected_links],
        }


class _SupportingDocumentParser(HTMLParser):
    """Capture anchors published inside the visible Supporting Documents section."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_support_section = False
        self.saw_support_marker = False
        self._href: str | None = None
        self._parts: list[str] = []
        self._anchor_in_support = False
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if isinstance(href, str):
            self._href = href
            self._parts = []
            self._anchor_in_support = self.in_support_section

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)
        folded = " ".join(data.split()).casefold()
        if folded == "supporting documents":
            self.in_support_section = True
            self.saw_support_marker = True
        elif "back to meeting outline" in folded:
            self.in_support_section = False

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        href = self._href
        text = " ".join("".join(self._parts).split())
        in_support = self._anchor_in_support
        self._href = None
        self._parts = []
        self._anchor_in_support = False

        if "back to meeting outline" in text.casefold():
            return
        if in_support or "supporting document" in text.casefold():
            self.links.append((href, text))


def _single_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    if values is None or len(values) != 1 or not values[0]:
        raise ValueError(f"attachment URI requires exactly one non-empty {key}")
    return values[0]


def _parent_ids(source_uri: str) -> tuple[int, int]:
    parsed = urlsplit(source_uri)
    if "/Meetings/ViewMeetingAgendaItem" not in parsed.path:
        raise ValueError("parent source is not an OnBase agenda-item URI")
    query = parse_qs(parsed.query, keep_blank_values=True)
    meeting = _single_query_value(query, "meetingId")
    item = _single_query_value(query, "itemId")
    if _single_query_value(query, "isSection").casefold() != "false":
        raise ValueError("parent agenda-item URI must declare isSection=false")
    if _single_query_value(query, "type").casefold() != "agenda":
        raise ValueError("parent agenda-item URI must declare type=agenda")
    if not meeting.isdigit() or int(meeting) <= 0:
        raise ValueError("parent meetingId must be a positive integer")
    if not item.isdigit() or int(item) <= 0:
        raise ValueError("parent itemId must be a positive integer")
    return int(meeting), int(item)


def _instance_root_path(item_source_uri: str) -> str:
    parsed = urlsplit(item_source_uri)
    marker = "/Meetings/ViewMeetingAgendaItem"
    index = parsed.path.find(marker)
    if index < 0:
        raise ValueError("parent source is not an OnBase agenda-item URI")
    return parsed.path[:index].rstrip("/") + "/"


def _eligible_href(href: str) -> bool:
    value = href.strip()
    if not value:
        return False
    folded = value.casefold()
    return not (
        value.startswith("#")
        or folded.startswith("javascript:")
        or folded.startswith("mailto:")
        or folded.startswith("tel:")
    )


def _validate_attachment_link(
    *,
    parent_source_uri: str,
    parent_artifact_id: str,
    parent_artifact_sha256: str,
    raw_href: str,
    link_text: str,
) -> OnBaseAttachmentRelation:
    meeting_id, item_id = _parent_ids(parent_source_uri)
    resolved = urljoin(parent_source_uri, raw_href)
    parent = urlsplit(parent_source_uri)
    parsed = urlsplit(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("attachment URI must use http/https")
    if (parsed.scheme, parsed.netloc) != (parent.scheme, parent.netloc):
        raise ValueError("attachment URI leaves the parent OnBase instance")
    if parsed.fragment:
        raise ValueError("attachment URI must not include a fragment")

    root = _instance_root_path(parent_source_uri)
    expected_prefix = root + "Documents/DownloadFile/"
    if not parsed.path.startswith(expected_prefix):
        raise ValueError("attachment URI is not under the publisher DownloadFile route")
    if "/DownloadFileBytes/" in parsed.path:
        raise ValueError("attachment source identity may not use the byte-transport route")
    if not parsed.path.casefold().endswith(".pdf"):
        raise ValueError("attachment path is not the proven PDF supporting-document contract")

    query = parse_qs(parsed.query, keep_blank_values=True)
    expected_keys = {
        "documentType",
        "meetingId",
        "itemId",
        "publishId",
        "isSection",
        "isAttachment",
    }
    if set(query) != expected_keys:
        raise ValueError("attachment URI query shape differs from the proven publisher contract")
    if _single_query_value(query, "documentType") != "1":
        raise ValueError("attachment documentType must equal 1")
    if _single_query_value(query, "meetingId") != str(meeting_id):
        raise ValueError("attachment meetingId does not match parent agenda item")
    if _single_query_value(query, "itemId") != str(item_id):
        raise ValueError("attachment itemId does not match parent agenda item")
    if _single_query_value(query, "isSection").casefold() != "false":
        raise ValueError("attachment isSection must be false")
    if _single_query_value(query, "isAttachment").casefold() != "true":
        raise ValueError("attachment isAttachment must be true")
    publish = _single_query_value(query, "publishId")
    if not publish.isdigit() or int(publish) <= 0:
        raise ValueError("attachment publishId must be a positive integer")

    return OnBaseAttachmentRelation(
        source_uri=resolved,
        parent_source_uri=parent_source_uri,
        parent_artifact_id=parent_artifact_id,
        parent_artifact_sha256=parent_artifact_sha256,
        meeting_id=meeting_id,
        item_id=item_id,
        publish_id=int(publish),
        link_text=link_text,
        raw_href=raw_href,
    )


def _byte_transport_uri(source_uri: str, wrapper_html: str) -> str:
    parsed = urlsplit(source_uri)
    marker = "/Documents/DownloadFile/"
    if marker not in parsed.path or "/Documents/DownloadFileBytes/" in parsed.path:
        raise ValueError("OnBase attachment source URI is not a DownloadFile source identity")
    if "window.location" not in wrapper_html or _WRAPPER_DECLARATION_RE.search(wrapper_html) is None:
        raise ValueError("OnBase DownloadFile wrapper did not declare DownloadFileBytes transport")
    byte_path = parsed.path.replace(marker, "/Documents/DownloadFileBytes/", 1)
    return urlunsplit((parsed.scheme, parsed.netloc, byte_path, parsed.query, ""))


class OnBaseAttachmentWatcher(CorpusWatcher):
    """CorpusWatcher transport that validates the OnBase wrapper before fetching file bytes."""

    def _download_resource(self, resource: ManifestResource, destination: Path):
        if resource.fetch_strategy != FETCH_STRATEGY:
            return super()._download_resource(resource, destination)

        wrapper_request = Request(
            resource.source_uri,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
            method="GET",
        )
        with urlopen(wrapper_request, timeout=self.timeout) as response:
            if response.geturl() != resource.source_uri:
                raise ValueError("OnBase DownloadFile wrapper unexpectedly redirected")
            content_type = self._base_content_type(response.headers.get("Content-Type"))
            if content_type != "text/html":
                raise ValueError(
                    f"OnBase DownloadFile wrapper must be text/html, received {content_type or 'unknown'}"
                )
            raw = response.read(_MAX_WRAPPER_BYTES + 1)
            if len(raw) > _MAX_WRAPPER_BYTES:
                raise ValueError("OnBase DownloadFile wrapper exceeded size limit")
        try:
            wrapper_html = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("OnBase DownloadFile wrapper was not valid UTF-8") from exc

        bytes_uri = _byte_transport_uri(resource.source_uri, wrapper_html)
        payload_request = Request(
            bytes_uri,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": resource.expected_media_type or "application/pdf",
            },
            method="GET",
        )
        with urlopen(payload_request, timeout=self.timeout) as response:
            if response.geturl() != bytes_uri:
                raise ValueError("OnBase DownloadFileBytes transport unexpectedly redirected")
            source = urlsplit(resource.source_uri)
            final = urlsplit(response.geturl())
            if (final.scheme, final.netloc) != (source.scheme, source.netloc):
                raise ValueError("OnBase DownloadFileBytes transport left the source instance")
            return self._write_response(response, destination)


def _instance_slug(plan: OnBaseAgendaPlan) -> str:
    parsed = urlsplit(plan.source_uri)
    path = parsed.path.rstrip("/")
    if path.casefold().endswith("/meetings"):
        path = path[: -len("/Meetings")]
    raw = f"{parsed.hostname or ''}-{path}"
    return re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-") or "onbase"


class OnBaseAttachmentDiscoverer:
    """Derive and optionally sync publisher-linked supporting documents."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.watcher = OnBaseAttachmentWatcher(self.state_dir)
        self.watch_store = WatcherStore(self.state_dir / "proofline.db")
        self.relations = RelationStore(self.state_dir)

    def _parent_artifact(self, source_uri: str) -> tuple[str, str, Path]:
        source_id = source_id_from_uri(source_uri)
        artifact_id = self.watch_store.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = self.watcher.store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"canonical OnBase parent has no successful artifact: {source_uri}")
        with self.watcher.store.connection() as connection:
            row = connection.execute(
                "SELECT sha256, stored_path FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"canonical OnBase parent artifact is missing: {artifact_id}")
        return artifact_id, str(row["sha256"]), self.state_dir / str(row["stored_path"])

    def discover(
        self,
        plan: OnBaseAgendaPlan,
        canonical_manifest: SourceManifest,
    ) -> OnBaseAttachmentDiscoveryResult:
        accepted: list[OnBaseAttachmentRelation] = []
        rejected: list[OnBaseAttachmentRejection] = []
        support_markers = 0
        accepted_parents: set[str] = set()

        for parent in sorted(canonical_manifest.resources, key=lambda resource: resource.source_uri):
            artifact_id, artifact_sha256, artifact_path = self._parent_artifact(parent.source_uri)
            html = artifact_path.read_text(encoding="utf-8", errors="replace")
            parser = _SupportingDocumentParser()
            parser.feed(html)
            parser.close()
            support_markers += int(parser.saw_support_marker)

            for raw_href, link_text in parser.links:
                if not _eligible_href(raw_href):
                    continue
                resolved = urljoin(parent.source_uri, raw_href)
                try:
                    relation = _validate_attachment_link(
                        parent_source_uri=parent.source_uri,
                        parent_artifact_id=artifact_id,
                        parent_artifact_sha256=artifact_sha256,
                        raw_href=raw_href,
                        link_text=link_text,
                    )
                except ValueError as exc:
                    rejected.append(
                        OnBaseAttachmentRejection(
                            parent_source_uri=parent.source_uri,
                            parent_artifact_id=artifact_id,
                            link_text=link_text,
                            raw_href=raw_href,
                            resolved_uri=resolved,
                            reason=str(exc),
                        )
                    )
                    continue
                accepted.append(relation)
                accepted_parents.add(parent.source_uri)

        relation_map: dict[tuple[str, str, str], OnBaseAttachmentRelation] = {}
        for relation in accepted:
            key = (relation.source_uri, relation.parent_source_uri, relation.link_text)
            relation_map[key] = relation
        relations = tuple(relation_map[key] for key in sorted(relation_map))

        resource_by_uri: dict[str, ManifestResource] = {}
        slug = _instance_slug(plan)
        for relation in relations:
            candidate = ManifestResource(
                source_uri=relation.source_uri,
                source_name=relation.link_text or "OnBase supporting document",
                native_identifier=f"onbase-{slug}-attachment-{relation.publish_id}",
                expected_media_type="application/pdf",
                fetch_strategy=FETCH_STRATEGY,
            )
            previous = resource_by_uri.get(relation.source_uri)
            if previous is not None and previous.native_identifier != candidate.native_identifier:
                raise ValueError(
                    f"OnBase attachment URI has conflicting publish identity: {relation.source_uri}"
                )
            resource_by_uri.setdefault(relation.source_uri, candidate)

        manifest = SourceManifest(
            name=f"{plan.name}:onbase-supporting-documents",
            resources=tuple(resource_by_uri[uri] for uri in sorted(resource_by_uri)),
        )
        serialized = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
        return OnBaseAttachmentDiscoveryResult(
            manifest=manifest,
            relations=relations,
            rejected_links=tuple(
                sorted(
                    rejected,
                    key=lambda item: (
                        item.parent_source_uri,
                        item.resolved_uri,
                        item.link_text,
                        item.reason,
                    ),
                )
            ),
            parent_item_count=len(canonical_manifest.resources),
            items_with_support_marker=support_markers,
            items_with_accepted_links=len(accepted_parents),
            manifest_sha256=sha256_text(serialized),
        )

    @staticmethod
    def bounded_manifest(
        result: OnBaseAttachmentDiscoveryResult,
        *,
        limit: int | None,
    ) -> SourceManifest:
        if limit is None:
            return result.manifest
        if limit < 1:
            raise ValueError("attachment sync limit must be positive")
        ranked = sorted(
            result.manifest.resources,
            key=lambda resource: (
                hashlib.sha256(resource.source_uri.encode("utf-8")).hexdigest(),
                resource.source_uri,
            ),
        )
        return SourceManifest(
            name=f"{result.manifest.name}:bounded-{limit}",
            resources=tuple(ranked[:limit]),
        )

    def sync(
        self,
        result: OnBaseAttachmentDiscoveryResult,
        *,
        limit: int | None = None,
    ) -> dict:
        manifest = self.bounded_manifest(result, limit=limit)
        watched = self.watcher.run(manifest)
        selected = {resource.source_uri for resource in manifest.resources}
        created = 0
        for relation in result.relations:
            if relation.source_uri not in selected:
                continue
            added = self.relations.add(
                source_uri=relation.source_uri,
                relation_type=RELATION_TYPE,
                related_source_uri=relation.parent_source_uri,
                evidence_artifact_id=relation.parent_artifact_id,
                method=RELATION_METHOD,
                method_version=RELATION_METHOD_VERSION,
                details={
                    "meeting_id": relation.meeting_id,
                    "item_id": relation.item_id,
                    "publish_id": relation.publish_id,
                    "link_text": relation.link_text,
                    "parent_artifact_sha256": relation.parent_artifact_sha256,
                    "evidence_kind": "publisher_supporting_documents_anchor",
                },
            )
            created += int(added is not None)

        serialized = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
        return {
            "manifest": manifest.name,
            "manifest_sha256": sha256_text(serialized),
            "resource_count": len(manifest.resources),
            "watch": watched,
            "relations_created": created,
            "relations_total": len(self.relations.list(relation_type=RELATION_TYPE)),
        }

    @staticmethod
    def write_manifest(result: OnBaseAttachmentDiscoveryResult, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(manifest_to_dict(result.manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination

    @staticmethod
    def write_relations(result: OnBaseAttachmentDiscoveryResult, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([item.to_dict() for item in result.relations], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return destination

    @staticmethod
    def write_rejections(result: OnBaseAttachmentDiscoveryResult, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([item.to_dict() for item in result.rejected_links], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return destination
