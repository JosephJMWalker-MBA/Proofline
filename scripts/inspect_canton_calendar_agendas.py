"""Inspect Canton's verified-host calendar and its linked CivicClerk client contract."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


_BASE = "https://www.cantonohio.gov"
_EVENT_TEXT = "city council regular meeting agenda (pdf)"
_SCRIPT_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+\.js[^\"']*)[\"']", re.IGNORECASE)
_ABSOLUTE_URL_RE = re.compile(r"https://[A-Za-z0-9._-]+(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?")
_API_PATH_RE = re.compile(
    r"(?:/v\d+/[A-Za-z0-9_./?=&{}:$-]+|/[A-Za-z0-9_./-]*(?:Meeting|Event|File|Agenda)[A-Za-z0-9_./?=&{}:$-]*)",
    re.IGNORECASE,
)
_KEYWORD_RE = re.compile(
    r".{0,120}(?:GetMeetingFileStream|GetEventFileStream|meetingFile|agendaFile|eventFiles|api\.civicclerk|apiBase|baseURL).{0,180}",
    re.IGNORECASE,
)
_FILE_KEY_RE = re.compile(r"(?:file|agenda|packet|minutes|attachment|document|meeting)", re.IGNORECASE)


class LinkParser(HTMLParser):
    def __init__(self, base_uri: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_uri = base_uri
        self._href: str | None = None
        self._parts: list[str] = []
        self.links: list[dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a":
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
            {
                "text": text,
                "href": self._href,
                "absolute_uri": urljoin(self.base_uri, self._href),
            }
        )
        self._href = None
        self._parts = []


def fetch_bytes(uri: str) -> tuple[bytes, dict]:
    request = Request(
        uri,
        headers={
            "User-Agent": "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        metadata = {
            "status": response.status,
            "final_url": response.geturl(),
            "content_type": response.headers.get("Content-Type"),
            "content_length": len(body),
        }
    return body, metadata


def fetch(uri: str) -> tuple[str, dict]:
    body, metadata = fetch_bytes(uri)
    return body.decode("utf-8", errors="replace"), metadata


def fetch_json(uri: str) -> tuple[object, dict]:
    body, metadata = fetch_bytes(uri)
    return json.loads(body.decode("utf-8")), metadata


def parse_links(uri: str, html: str) -> list[dict]:
    parser = LinkParser(uri)
    parser.feed(html)
    parser.close()
    return parser.links


def event_id(uri: str) -> str | None:
    query = parse_qs(urlparse(uri).query)
    values = query.get("EID")
    return values[0] if values else None


def _civicclerk_event_id(uri: str) -> str | None:
    match = re.search(r"/event/(\d+)/files(?:[/?#]|$)", urlparse(uri).path)
    return match.group(1) if match else None


def _trim(value: str, limit: int = 500) -> str:
    collapsed = " ".join(value.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _file_like_nodes(value: object, path: str = "$", *, depth: int = 0) -> list[dict]:
    """Return compact public metadata objects that appear to describe files/meetings."""
    if depth > 10:
        return []
    found: list[dict] = []
    if isinstance(value, dict):
        matching_keys = [str(key) for key in value if _FILE_KEY_RE.search(str(key))]
        if matching_keys:
            compact: dict[str, object] = {}
            for key, item in value.items():
                if not _FILE_KEY_RE.search(str(key)) and str(key).casefold() not in {
                    "id",
                    "name",
                    "title",
                    "type",
                    "date",
                }:
                    continue
                if isinstance(item, (str, int, float, bool)) or item is None:
                    compact[str(key)] = item
                elif isinstance(item, list) and len(item) <= 10:
                    compact[str(key)] = item
            if compact:
                found.append({"path": path, "values": compact})
        for key, item in value.items():
            found.extend(_file_like_nodes(item, f"{path}.{key}", depth=depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value[:500]):
            found.extend(_file_like_nodes(item, f"{path}[{index}]", depth=depth + 1))
    return found


def _json_shape(value: object) -> dict:
    if isinstance(value, dict):
        return {
            "type": "object",
            "keys": sorted(str(key) for key in value.keys()),
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "first_item_type": type(value[0]).__name__ if value else None,
        }
    return {"type": type(value).__name__}


def inspect_civicclerk_client(portal_uri: str) -> dict:
    """Inspect only first-party client assets actually referenced by the portal shell."""
    html, portal_response = fetch(portal_uri)
    script_uris = []
    for src in _SCRIPT_RE.findall(html):
        absolute = urljoin(portal_uri, src)
        if absolute not in script_uris:
            script_uris.append(absolute)

    assets: list[dict] = []
    aggregate_urls: set[str] = set()
    aggregate_paths: set[str] = set()
    aggregate_contexts: set[str] = set()

    for script_uri in script_uris[:12]:
        try:
            body, response = fetch_bytes(script_uri)
        except Exception as exc:
            assets.append(
                {
                    "script_uri": script_uri,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        text = body.decode("utf-8", errors="replace")
        urls = {
            match.group(0).rstrip("'\"),;]")
            for match in _ABSOLUTE_URL_RE.finditer(text)
            if "civicclerk" in match.group(0).casefold()
        }
        paths = {
            match.group(0).rstrip("'\"),;]")
            for match in _API_PATH_RE.finditer(text)
            if any(
                token in match.group(0).casefold()
                for token in ("event", "meeting", "file", "agenda", "/v1/")
            )
        }
        contexts = {_trim(match.group(0)) for match in _KEYWORD_RE.finditer(text)}

        aggregate_urls.update(urls)
        aggregate_paths.update(paths)
        aggregate_contexts.update(contexts)
        assets.append(
            {
                "script_uri": script_uri,
                "response": response,
                "civicclerk_urls": sorted(urls)[:200],
                "api_path_candidates": sorted(paths)[:300],
                "keyword_contexts": sorted(contexts)[:200],
            }
        )

    return {
        "portal_uri": portal_uri,
        "portal_response": portal_response,
        "script_uris": script_uris,
        "assets": assets,
        "civicclerk_urls": sorted(aggregate_urls)[:300],
        "api_path_candidates": sorted(aggregate_paths)[:500],
        "keyword_contexts": sorted(aggregate_contexts)[:300],
    }


def inspect_civicclerk_api(event_ids: list[str]) -> dict:
    """Probe the tenant API route explicitly shipped by the CivicClerk client."""
    api_base = "https://cantonoh.api.civicclerk.com/v1"
    results: list[dict] = []
    candidate_files: dict[tuple[int, int], dict] = {}

    for event_id_value in event_ids:
        uri = f"{api_base}/Events/{event_id_value}"
        try:
            payload, metadata = fetch_json(uri)
            nodes = _file_like_nodes(payload)
            result = {
                "event_id": event_id_value,
                "uri": uri,
                "response": metadata,
                "shape": _json_shape(payload),
                "file_like_nodes": nodes[:300],
            }
            results.append(result)

            for node in nodes:
                values = node.get("values", {})
                file_id = values.get("fileId") or values.get("FileId") or values.get("fileID")
                file_type = values.get("fileType") or values.get("FileType")
                if isinstance(file_id, int) and isinstance(file_type, int):
                    candidate_files[(file_id, file_type)] = {
                        "file_id": file_id,
                        "file_type": file_type,
                        "event_id": event_id_value,
                        "node": node,
                    }
        except Exception as exc:
            results.append(
                {
                    "event_id": event_id_value,
                    "uri": uri,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    stream_probes: list[dict] = []
    for item in list(candidate_files.values())[:12]:
        params = urlencode(
            {
                "fileId": item["file_id"],
                "fileType": item["file_type"],
                "plainText": "false",
            }
        )
        uri = f"{api_base}/Events/GetEventFileStream?{params}"
        try:
            body, metadata = fetch_bytes(uri)
            stream_probes.append(
                {
                    **item,
                    "uri": uri,
                    "response": metadata,
                    "magic_hex": body[:16].hex(),
                    "starts_pdf": body.startswith(b"%PDF"),
                }
            )
        except Exception as exc:
            stream_probes.append(
                {
                    **item,
                    "uri": uri,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "api_base": api_base,
        "events": results,
        "candidate_file_count": len(candidate_files),
        "stream_probes": stream_probes,
    }


def main() -> int:
    events: dict[str, dict] = {}

    for month in range(1, 9):
        month_uri = f"{_BASE}/calendar.aspx?CID=31&month={month}&view=list&year=2026"
        html, metadata = fetch(month_uri)
        for link in parse_links(month_uri, html):
            if _EVENT_TEXT not in link["text"].casefold():
                continue
            eid = event_id(link["absolute_uri"])
            if not eid:
                continue
            events[eid] = {
                "eid": eid,
                "listing_uri": month_uri,
                "event_uri": f"{_BASE}/Calendar.aspx?EID={eid}",
                "listing_link": link,
                "listing_response": metadata,
            }

    civicclerk_event_ids: set[str] = set()
    civicclerk_portals: list[str] = []
    for eid, event in sorted(events.items(), key=lambda item: int(item[0])):
        html, metadata = fetch(event["event_uri"])
        links = parse_links(event["event_uri"], html)
        event["event_response"] = metadata
        event["download_candidates"] = [
            link
            for link in links
            if "agenda" in link["text"].casefold()
            or "download" in link["text"].casefold()
            or link["absolute_uri"].lower().endswith(".pdf")
            or "documentcenter" in link["absolute_uri"].casefold()
            or "civicclerk" in link["absolute_uri"].casefold()
        ]
        for link in event["download_candidates"]:
            if "portal.civicclerk.com" not in link["absolute_uri"].casefold():
                continue
            civic_id = _civicclerk_event_id(link["absolute_uri"])
            if civic_id:
                civicclerk_event_ids.add(civic_id)
                if link["absolute_uri"] not in civicclerk_portals:
                    civicclerk_portals.append(link["absolute_uri"])

    ordered_civic_ids = sorted(civicclerk_event_ids, key=int)
    client_contract = None
    api_probe = None
    if civicclerk_portals:
        client_contract = inspect_civicclerk_client(civicclerk_portals[0])
    if ordered_civic_ids:
        api_probe = inspect_civicclerk_api(ordered_civic_ids)

    print(
        json.dumps(
            {
                "event_count": len(events),
                "civicclerk_event_ids": ordered_civic_ids,
                "events": list(events.values()),
                "civicclerk_client": client_contract,
                "civicclerk_api": api_probe,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
