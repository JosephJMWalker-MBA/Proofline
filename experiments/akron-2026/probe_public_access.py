#!/usr/bin/env python3
"""Probe Akron's publisher-declared Public Access Viewer source contract.

This experiment starts from the official Agenda Online home page, follows only the
publisher-declared "Public Access Viewer" link, preserves the viewer HTML and
same-host script assets, and reports route/configuration strings declared by those
assets. It does not submit a document search, guess query IDs, enumerate document
tokens, or assign any terminal outcome.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from probe_onbase import PageParser, fetch

AGENDA_HOME = "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/"
EXPECTED_PUBLIC_ACCESS_ROOT = "https://onlinedocs.akronohio.gov/PublicAccess/"
SCHEMA = "proofline-akron-t21-public-access-source-contract-probe/v1"

_ROUTE_TOKEN_RE = re.compile(
    r"(?i)(?:https?://[^\"'\s)]+|/[^\"'\s)]*(?:api|recordsearch|customquery|cq)[^\"'\s)]*)"
)
_INTERESTING_MARKERS = (
    "api/",
    "customquery",
    "cqid",
    "obkey__",
    "recordsearch",
    "api/document",
)


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self.links: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {key: value for key, value in attrs}
        if tag.casefold() == "script":
            src = attributes.get("src")
            if isinstance(src, str) and src.strip():
                self.scripts.append(src.strip())
        elif tag.casefold() == "link":
            self.links.append(
                {
                    "href": attributes.get("href"),
                    "rel": attributes.get("rel"),
                    "type": attributes.get("type"),
                }
            )


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _safe_same_host(base: str, candidate: str) -> str | None:
    absolute = urljoin(base, candidate)
    if urlparse(absolute).hostname != urlparse(base).hostname:
        return None
    return absolute


def _response_record(result: dict, body: bytes) -> dict:
    record = {key: value for key, value in result.items() if key != "body"}
    record["byte_length"] = len(body)
    record["sha256"] = _sha256(body)
    record["same_host"] = (
        urlparse(record["requested_url"]).hostname
        == urlparse(record["final_url"]).hostname
    )
    return record


def _declared_public_access_link(home_html: str) -> tuple[str, dict]:
    parser = PageParser()
    parser.feed(home_html)
    candidates = []
    for anchor in parser.anchors:
        text = str(anchor.get("text") or "")
        href = anchor.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        if "public access viewer" not in text.casefold():
            continue
        absolute = urljoin(AGENDA_HOME, href)
        candidates.append((absolute, anchor))
    if len(candidates) != 1:
        raise ValueError(
            "expected exactly one publisher-declared Public Access Viewer link; "
            f"found {len(candidates)}"
        )
    url, anchor = candidates[0]
    if not url.startswith(EXPECTED_PUBLIC_ACCESS_ROOT):
        raise ValueError(f"publisher Public Access link escaped expected Akron root: {url}")
    return url, anchor


def _interesting_strings(source: str) -> list[str]:
    found: set[str] = set()
    lowered = source.casefold()
    for marker in _INTERESTING_MARKERS:
        start = 0
        needle = marker.casefold()
        while True:
            index = lowered.find(needle, start)
            if index < 0:
                break
            left = max(0, index - 180)
            right = min(len(source), index + len(marker) + 260)
            snippet = " ".join(source[left:right].split())
            if snippet:
                found.add(snippet)
            start = index + len(needle)
    return sorted(found)


def _route_tokens(source: str, *, base: str) -> list[str]:
    routes: set[str] = set()
    for match in _ROUTE_TOKEN_RE.finditer(source):
        token = match.group(0).rstrip(".,;]")
        absolute = _safe_same_host(base, token)
        if absolute is not None:
            routes.add(absolute)
    return sorted(routes)


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-public-access-probe")
    output.mkdir(parents=True, exist_ok=True)

    home_result = fetch(AGENDA_HOME)
    home_body: bytes = home_result.pop("body")
    home_record = _response_record(home_result, home_body)
    home_html = home_body.decode("utf-8", errors="replace")
    (output / "agenda-home.html").write_text(home_html, encoding="utf-8")
    if not home_record.get("ok"):
        raise RuntimeError("official Agenda Online home page was unavailable")

    public_access_url, declared_anchor = _declared_public_access_link(home_html)

    viewer_result = fetch(public_access_url)
    viewer_body: bytes = viewer_result.pop("body")
    viewer_record = _response_record(viewer_result, viewer_body)
    viewer_html = viewer_body.decode("utf-8", errors="replace")
    (output / "public-access-index.html").write_text(viewer_html, encoding="utf-8")
    if not viewer_record.get("ok"):
        raise RuntimeError("publisher-declared Public Access Viewer was unavailable")
    if not viewer_record.get("same_host"):
        raise RuntimeError("Public Access Viewer redirected off publisher host")

    asset_parser = AssetParser()
    asset_parser.feed(viewer_html)

    script_urls: list[str] = []
    for src in asset_parser.scripts:
        absolute = _safe_same_host(public_access_url, src)
        if absolute is not None and absolute not in script_urls:
            script_urls.append(absolute)

    script_records = []
    route_candidates: set[str] = set(_route_tokens(viewer_html, base=public_access_url))
    interesting = {
        "public-access-index.html": _interesting_strings(viewer_html),
    }

    for index, script_url in enumerate(script_urls, start=1):
        result = fetch(script_url, maximum_bytes=10_000_000)
        body: bytes = result.pop("body")
        record = _response_record(result, body)
        record["script_url"] = script_url
        record["asset_index"] = index
        script_records.append(record)
        if not record.get("ok"):
            continue
        source = body.decode("utf-8", errors="replace")
        filename = f"script-{index:02d}.js"
        (output / filename).write_text(source, encoding="utf-8")
        interesting[filename] = _interesting_strings(source)
        route_candidates.update(_route_tokens(source, base=public_access_url))

    payload = {
        "schema": SCHEMA,
        "stage": "publisher_declared_public_access_source_contract_only",
        "agenda_home": home_record,
        "publisher_declaration": {
            "anchor_text": declared_anchor.get("text"),
            "href": declared_anchor.get("href"),
            "resolved_url": public_access_url,
            "passed_legislation_and_meeting_minutes_claimed_by_publisher": True,
        },
        "public_access_viewer": viewer_record,
        "declared_assets": {
            "script_urls": script_urls,
            "link_elements": asset_parser.links,
        },
        "script_records": script_records,
        "route_candidates": sorted(route_candidates),
        "interesting_source_snippets": interesting,
        "counts": {
            "declared_script_count": len(script_urls),
            "successful_script_count": sum(1 for row in script_records if row.get("ok")),
            "route_candidate_count": len(route_candidates),
            "interesting_snippet_count": sum(len(rows) for rows in interesting.values()),
        },
        "authority_boundary": {
            "document_search_submitted": False,
            "query_id_guessed": False,
            "document_token_enumerated": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "A publisher-declared Public Access Viewer link establishes only the intended official surface, not the existence or disposition of any particular Eastwood record.",
            "Route/configuration strings are source-contract evidence only and are not document search results.",
            "No absence, search result, vote, or terminal outcome is evaluated in this probe.",
        ],
    }
    (output / "public-access-probe.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["counts"], indent=2, sort_keys=True))

    if not payload["publisher_declaration"]["passed_legislation_and_meeting_minutes_claimed_by_publisher"]:
        return 2
    if not viewer_record.get("ok"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
