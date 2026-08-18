"""Inspect Canton's verified-host calendar and its linked CivicClerk client contract."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
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
    r".{0,120}(?:GetMeetingFileStream|meetingFile|agendaFile|eventFiles|api\.civicclerk|apiBase|baseURL).{0,180}",
    re.IGNORECASE,
)


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

    client_contract = None
    if civicclerk_portals:
        client_contract = inspect_civicclerk_client(civicclerk_portals[0])

    print(
        json.dumps(
            {
                "event_count": len(events),
                "civicclerk_event_ids": sorted(civicclerk_event_ids, key=int),
                "events": list(events.values()),
                "civicclerk_client": client_contract,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
