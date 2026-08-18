"""Capture bounded link structure from Canton's official City Council archive pages."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PAGES = {
    "agendas": "https://app.cantonohio.gov/council/?pg=agendas",
    "minutes": "https://app.cantonohio.gov/council/?pg=minutes",
}


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


def main() -> int:
    output: dict[str, dict] = {}
    for name, uri in PAGES.items():
        html, metadata = fetch(uri)
        parser = LinkParser(uri)
        parser.feed(html)
        parser.close()
        output[name] = {
            "source_uri": uri,
            "response": metadata,
            "links": parser.links,
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
