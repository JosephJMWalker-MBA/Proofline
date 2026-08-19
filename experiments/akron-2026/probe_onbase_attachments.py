from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

SCHEMA = "proofline-onbase-attachment-probe/v1"
MAX_SAMPLE_LINKS = 8
MAX_SAMPLE_BYTES = 4 * 1024 * 1024
USER_AGENT = "Proofline/0.1 bounded OnBase supporting-document contract probe"
_WRAPPER_DIRECTIVE = 'replace("DownloadFile", "DownloadFileBytes")'
_DOWNLOAD_SEGMENT = "/Documents/DownloadFile/"
_DOWNLOAD_BYTES_SEGMENT = "/Documents/DownloadFileBytes/"


@dataclass(frozen=True, slots=True)
class AttachmentRelation:
    item_source_uri: str
    item_artifact_id: str
    item_artifact_sha256: str
    meeting_id: str | None
    item_id: str | None
    link_text: str
    raw_href: str
    resolved_uri: str
    same_instance: bool
    link_signature: str

    def to_dict(self) -> dict:
        return asdict(self)


class SupportingLinkParser(HTMLParser):
    """Collect publisher anchors that occur inside the visible Supporting Documents section."""

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
        normalized = " ".join(data.split())
        folded = normalized.casefold()
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

        folded = text.casefold()
        if "back to meeting outline" in folded:
            return
        # The structural section is authoritative. The link-text fallback protects against a
        # publisher template change that moves the marker without changing its visible label.
        if in_support or "supporting document" in folded:
            self.links.append((href, text))


def _item_ids(source_uri: str) -> tuple[str | None, str | None]:
    query = parse_qs(urlsplit(source_uri).query)
    meeting = query.get("meetingId", [None])[0]
    item = query.get("itemId", [None])[0]
    return meeting, item


def _link_signature(uri: str) -> str:
    parsed = urlsplit(uri)
    keys = sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)})
    query_shape = "&".join(keys)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (
        f"?{query_shape}" if query_shape else ""
    )


def _eligible_href(href: str) -> bool:
    stripped = href.strip()
    if not stripped:
        return False
    folded = stripped.casefold()
    return not (
        folded.startswith("javascript:")
        or folded.startswith("mailto:")
        or folded.startswith("tel:")
        or stripped.startswith("#")
    )


def _detect_media(prefix: bytes) -> str:
    stripped = prefix.lstrip()
    lowered = stripped[:64].lower()
    if prefix.startswith(b"%PDF-"):
        return "application/pdf"
    if prefix.startswith(b"PK\x03\x04"):
        return "application/zip-container"
    if prefix.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        return "application/x-ole-compound"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html"):
        return "text/html"
    return "unknown"


def _load_canonical_rows(state_dir: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(state_dir / "proofline.db")
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT
                s.source_uri,
                a.artifact_id,
                a.sha256 AS artifact_sha256,
                a.stored_path
            FROM sources s
            JOIN source_snapshots ss ON ss.source_id = s.source_id
            JOIN artifacts a ON a.artifact_id = ss.artifact_id
            WHERE s.source_uri LIKE '%/Meetings/ViewMeetingAgendaItem?%'
            ORDER BY s.source_uri, a.artifact_id
            """
        ).fetchall()
    finally:
        connection.close()
    return rows


def discover_relations(state_dir: Path) -> tuple[list[AttachmentRelation], dict]:
    rows = _load_canonical_rows(state_dir)
    relations: list[AttachmentRelation] = []
    support_marker_items = 0
    linked_items: set[str] = set()

    for row in rows:
        source_uri = str(row["source_uri"])
        artifact_path = state_dir / str(row["stored_path"])
        html = artifact_path.read_text(encoding="utf-8", errors="replace")
        parser = SupportingLinkParser()
        parser.feed(html)
        parser.close()
        support_marker_items += int(parser.saw_support_marker)
        meeting_id, item_id = _item_ids(source_uri)
        source_host = (urlsplit(source_uri).hostname or "").casefold()

        for raw_href, text in parser.links:
            if not _eligible_href(raw_href):
                continue
            resolved = urljoin(source_uri, raw_href)
            parsed = urlsplit(resolved)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            relation = AttachmentRelation(
                item_source_uri=source_uri,
                item_artifact_id=str(row["artifact_id"]),
                item_artifact_sha256=str(row["artifact_sha256"]),
                meeting_id=meeting_id,
                item_id=item_id,
                link_text=text,
                raw_href=raw_href,
                resolved_uri=resolved,
                same_instance=(parsed.hostname.casefold() == source_host),
                link_signature=_link_signature(resolved),
            )
            relations.append(relation)
            linked_items.add(source_uri)

    # Preserve every publisher-declared relation, but remove exact parser duplicates caused by
    # repeated DOM fragments inside one item page.
    deduped: dict[tuple[str, str, str], AttachmentRelation] = {}
    for relation in relations:
        key = (relation.item_source_uri, relation.resolved_uri, relation.link_text)
        deduped[key] = relation
    ordered = sorted(
        deduped.values(),
        key=lambda item: (item.item_source_uri, item.resolved_uri, item.link_text),
    )
    profile = {
        "canonical_item_rows": len(rows),
        "items_with_support_marker": support_marker_items,
        "items_with_attachment_links": len(linked_items),
    }
    return ordered, profile


def select_sample(relations: list[AttachmentRelation]) -> list[AttachmentRelation]:
    # Fetch a URI once even if multiple agenda items link to it. Prefer distinct meetings first,
    # using only a hash of publisher-declared identities so selection is independent of content.
    representative: dict[str, AttachmentRelation] = {}
    for relation in relations:
        if relation.same_instance:
            representative.setdefault(relation.resolved_uri, relation)
    candidates = sorted(
        representative.values(),
        key=lambda item: hashlib.sha256(item.resolved_uri.encode("utf-8")).hexdigest(),
    )

    selected: list[AttachmentRelation] = []
    selected_uris: set[str] = set()
    meetings: set[str] = set()
    for relation in candidates:
        meeting = relation.meeting_id or ""
        if meeting and meeting not in meetings:
            selected.append(relation)
            selected_uris.add(relation.resolved_uri)
            meetings.add(meeting)
            if len(selected) >= MAX_SAMPLE_LINKS:
                return selected
    for relation in candidates:
        if relation.resolved_uri in selected_uris:
            continue
        selected.append(relation)
        selected_uris.add(relation.resolved_uri)
        if len(selected) >= MAX_SAMPLE_LINKS:
            break
    return selected


def _publisher_declared_bytes_uri(wrapper_uri: str, wrapper_body: bytes) -> str | None:
    """Follow only the exact client-side transport rule preserved in the publisher wrapper."""

    try:
        html = wrapper_body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if _WRAPPER_DIRECTIVE not in html:
        return None

    parsed = urlsplit(wrapper_uri)
    if _DOWNLOAD_SEGMENT not in parsed.path or _DOWNLOAD_BYTES_SEGMENT in parsed.path:
        return None
    path = parsed.path.replace(_DOWNLOAD_SEGMENT, _DOWNLOAD_BYTES_SEGMENT, 1)
    candidate = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
    candidate_parts = urlsplit(candidate)
    if (
        candidate_parts.scheme != parsed.scheme
        or candidate_parts.netloc.casefold() != parsed.netloc.casefold()
    ):
        return None
    return candidate


def _read_bounded_response(response) -> tuple[bytes, dict]:
    status = int(getattr(response, "status", 200))
    final_uri = response.geturl()
    content_type = response.headers.get("Content-Type")
    content_disposition = response.headers.get("Content-Disposition")
    content_length = response.headers.get("Content-Length")
    body = response.read(MAX_SAMPLE_BYTES + 1)
    truncated = len(body) > MAX_SAMPLE_BYTES
    prefix = body[:MAX_SAMPLE_BYTES]
    return prefix, {
        "http_status": status,
        "content_type": content_type,
        "content_disposition": content_disposition,
        "content_length_header": content_length,
        "final_uri": final_uri,
        "captured_bytes": len(prefix),
        "capture_truncated": truncated,
        "complete_sha256": hashlib.sha256(prefix).hexdigest() if not truncated else None,
        "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
        "magic_media_type": _detect_media(prefix),
        "magic_prefix_hex": prefix[:16].hex(),
    }


def fetch_sample(relation: AttachmentRelation, sample_dir: Path, index: int) -> dict:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    wrapper_request = Request(
        relation.resolved_uri,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="GET",
    )
    base = {
        "source_uri": relation.resolved_uri,
        "meeting_id": relation.meeting_id,
        "item_id": relation.item_id,
        "link_text": relation.link_text,
        "link_signature": relation.link_signature,
    }

    try:
        with opener.open(wrapper_request, timeout=30) as response:
            wrapper_body, wrapper_meta = _read_bounded_response(response)
    except Exception as exc:  # probe must retain negative transport results as data
        return {**base, "wrapper_error": f"{type(exc).__name__}: {exc}"}

    wrapper_path = sample_dir / f"sample-{index:02d}-wrapper.bin"
    wrapper_path.write_bytes(wrapper_body)
    wrapper_final = urlsplit(wrapper_meta["final_uri"])
    original = urlsplit(relation.resolved_uri)
    wrapper_meta.update(
        {
            "redirected": wrapper_meta["final_uri"] != relation.resolved_uri,
            "final_same_host": (wrapper_final.hostname or "").casefold()
            == (original.hostname or "").casefold(),
            "saved_file": wrapper_path.name,
        }
    )

    bytes_uri = _publisher_declared_bytes_uri(relation.resolved_uri, wrapper_body)
    result = {
        **base,
        "wrapper": wrapper_meta,
        "publisher_declared_byte_transport": bytes_uri is not None,
        "bytes_uri": bytes_uri,
    }
    if bytes_uri is None:
        return result

    bytes_request = Request(
        bytes_uri,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="GET",
    )
    try:
        with opener.open(bytes_request, timeout=30) as response:
            payload, payload_meta = _read_bounded_response(response)
    except Exception as exc:
        return {**result, "payload_error": f"{type(exc).__name__}: {exc}"}

    payload_path = sample_dir / f"sample-{index:02d}-payload.bin"
    payload_path.write_bytes(payload)
    payload_final = urlsplit(payload_meta["final_uri"])
    bytes_parts = urlsplit(bytes_uri)
    payload_meta.update(
        {
            "redirected": payload_meta["final_uri"] != bytes_uri,
            "final_same_host": (payload_final.hostname or "").casefold()
            == (bytes_parts.hostname or "").casefold(),
            "saved_file": payload_path.name,
        }
    )
    return {**result, "payload": payload_meta}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    samples_dir = output / "samples"
    samples_dir.mkdir(exist_ok=True)

    relations, profile = discover_relations(state_dir)
    sample_relations = select_sample(relations)
    samples = [
        fetch_sample(relation, samples_dir, index)
        for index, relation in enumerate(sample_relations, start=1)
    ]

    signature_counts = Counter(relation.link_signature for relation in relations)
    host_counts = Counter(urlsplit(relation.resolved_uri).hostname or "" for relation in relations)
    unique_uris = {relation.resolved_uri for relation in relations}
    same_instance_uris = {relation.resolved_uri for relation in relations if relation.same_instance}
    external_uris = unique_uris - same_instance_uris

    report = {
        "schema": SCHEMA,
        "profile": profile,
        "relations": {
            "relation_count": len(relations),
            "unique_attachment_uri_count": len(unique_uris),
            "same_instance_unique_uri_count": len(same_instance_uris),
            "external_unique_uri_count": len(external_uris),
            "signature_counts": [
                {"signature": key, "count": signature_counts[key]}
                for key in sorted(signature_counts)
            ],
            "host_counts": [
                {"host": key, "count": host_counts[key]} for key in sorted(host_counts)
            ],
        },
        "sample_policy": {
            "max_links": MAX_SAMPLE_LINKS,
            "max_bytes_per_response": MAX_SAMPLE_BYTES,
            "selection": "sha256(source_uri), distinct meeting first, same-instance links only",
            "external_links_fetched": False,
            "byte_transport_rule": (
                "follow only when the preserved wrapper contains the exact publisher JavaScript "
                'replace(\"DownloadFile\", \"DownloadFileBytes\")'
            ),
        },
        "sample_count": len(samples),
        "samples": samples,
    }

    (output / "relations.json").write_text(
        json.dumps([relation.to_dict() for relation in relations], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "attachment-probe.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
