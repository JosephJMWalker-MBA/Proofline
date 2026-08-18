"""Inspect Canton's verified-host calendar for City Council agenda downloads."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen


_BASE = "https://www.cantonohio.gov"
_EVENT_TEXT = "city council regular meeting agenda (pdf)"


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


def fetch(uri: str) -> tuple[str, dict]:
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
        ]

    print(
        json.dumps(
            {
                "event_count": len(events),
                "events": list(events.values()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
