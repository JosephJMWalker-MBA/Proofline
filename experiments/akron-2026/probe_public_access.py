#!/usr/bin/env python3
"""Probe Akron's publisher-declared Public Access Viewer source contract.

The probe starts from the official Agenda Online home page, follows only its
publisher-declared Public Access Viewer link, preserves the viewer HTML/scripts,
then follows source-declared configuration and CustomQuery metadata routes.
It never submits a document search, guesses a query ID, enumerates document
tokens, or assigns a terminal outcome.
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
CONFIG_LITERAL = "./obpa-config.json"

_ROUTE_TOKEN_RE = re.compile(
    r"(?i)(?:https?://[^\"'\s)]+|/[^\"'\s)]*(?:api|recordsearch|customquery|cq)[^\"'\s)]*)"
)
_INTERESTING_MARKERS = (
    "api.url",
    "obpa-config.json",
    "customquery",
    "queryid",
    "keywords",
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
    candidate = candidate.strip()
    if not candidate or len(candidate) > 500:
        return None
    lowered = candidate.casefold()
    if "base64," in lowered or lowered.startswith("data:"):
        return None
    if not candidate.startswith(("/", "http://", "https://", "./", "../")):
        return None
    absolute = urljoin(base, candidate)
    parsed = urlparse(absolute)
    if parsed.hostname != urlparse(base).hostname:
        return None
    if not parsed.path.startswith("/PublicAccess/"):
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


def _nested(payload: dict, dotted: str):
    value = payload
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _parse_custom_queries(raw: bytes) -> tuple[dict, list[dict]]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CustomQuery response must be a JSON object")
    rows = payload.get("Data")
    if not isinstance(rows, list):
        raise ValueError("CustomQuery response must contain a Data array")
    queries: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        query_id = row.get("ID")
        name = row.get("Name")
        if not isinstance(query_id, (int, str)) or not str(query_id).strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        queries.append(
            {
                "id": str(query_id),
                "name": " ".join(name.split()),
                "type": row.get("Type"),
                "instructions": row.get("Instructions"),
                "date_search_option": row.get("DateSearchOption"),
                "requires_date_or_keyword": row.get("RequiresDateOrKeyword"),
                "requires_keyword": row.get("RequiresKeyword"),
                "requires_date": row.get("RequiresDate"),
            }
        )
    return payload, queries


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
    if not viewer_record.get("ok") or not viewer_record.get("same_host"):
        raise RuntimeError("publisher-declared Public Access Viewer was unavailable or redirected off host")

    asset_parser = AssetParser()
    asset_parser.feed(viewer_html)

    script_urls: list[str] = []
    for src in asset_parser.scripts:
        absolute = _safe_same_host(public_access_url, src)
        if absolute is not None and absolute not in script_urls:
            script_urls.append(absolute)

    script_records = []
    successful_sources: list[str] = []
    route_candidates: set[str] = set(_route_tokens(viewer_html, base=public_access_url))
    interesting = {"public-access-index.html": _interesting_strings(viewer_html)}

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
        successful_sources.append(source)
        filename = f"script-{index:02d}.js"
        (output / filename).write_text(source, encoding="utf-8")
        interesting[filename] = _interesting_strings(source)
        route_candidates.update(_route_tokens(source, base=public_access_url))

    combined_scripts = "\n".join(successful_sources)
    client_contract = {
        "config_literal": CONFIG_LITERAL if CONFIG_LITERAL in combined_scripts else None,
        "custom_query_get_declared": 'this.URI+"/CustomQuery"' in combined_scripts,
        "keywords_post_declared": 'this.URI+"/Keywords"' in combined_scripts,
        "keyword_search_post_declared": 'this.URI+"/CustomQuery/KeywordSearch"' in combined_scripts,
        "document_uri_declared": 'this.URI+"/Document/"' in combined_scripts,
        "api_url_config_key_declared": 'config.get("api.url")' in combined_scripts,
    }
    if not all(
        client_contract[key]
        for key in (
            "config_literal",
            "custom_query_get_declared",
            "keywords_post_declared",
            "keyword_search_post_declared",
            "document_uri_declared",
            "api_url_config_key_declared",
        )
    ):
        raise ValueError("Public Access client did not expose the expected source-declared query contract")

    config_url = urljoin(viewer_record["final_url"], CONFIG_LITERAL)
    if not config_url.startswith(EXPECTED_PUBLIC_ACCESS_ROOT):
        raise ValueError("source-declared config escaped Public Access root")
    config_result = fetch(config_url)
    config_body: bytes = config_result.pop("body")
    config_record = _response_record(config_result, config_body)
    if not config_record.get("ok") or not config_record.get("same_host"):
        raise RuntimeError("source-declared Public Access configuration was unavailable")
    config_payload = json.loads(config_body.decode("utf-8"))
    if not isinstance(config_payload, dict):
        raise ValueError("Public Access configuration must be a JSON object")
    (output / "obpa-config.json").write_bytes(config_body)

    configured_api = _nested(config_payload, "api.url")
    if configured_api is None:
        configured_api = "/api"
        api_root_basis = "client_declared_default"
    elif isinstance(configured_api, str) and configured_api.strip():
        configured_api = configured_api.strip()
        api_root_basis = "source_declared_config"
    else:
        raise ValueError("api.url must be absent or a non-empty string")
    api_root = urljoin(viewer_record["final_url"], configured_api)
    if urlparse(api_root).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("resolved Public Access API root escaped publisher host")

    custom_query_url = api_root.rstrip("/") + "/CustomQuery"
    custom_query_result = fetch(custom_query_url)
    custom_query_body: bytes = custom_query_result.pop("body")
    custom_query_record = _response_record(custom_query_result, custom_query_body)
    if not custom_query_record.get("ok") or not custom_query_record.get("same_host"):
        raise RuntimeError("source-declared CustomQuery metadata endpoint was unavailable")
    _, custom_queries = _parse_custom_queries(custom_query_body)
    (output / "custom-queries.json").write_bytes(custom_query_body)

    route_candidates.add(config_url)
    route_candidates.add(api_root)
    route_candidates.add(custom_query_url)

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
        "client_contract": client_contract,
        "configuration": {
            "record": config_record,
            "api_url": configured_api,
            "api_root": api_root,
            "api_root_basis": api_root_basis,
            "query_limit": _nested(config_payload, "query.limit"),
        },
        "custom_query_metadata": {
            "record": custom_query_record,
            "endpoint": custom_query_url,
            "queries": custom_queries,
        },
        "route_candidates": sorted(route_candidates),
        "interesting_source_snippets": interesting,
        "counts": {
            "declared_script_count": len(script_urls),
            "successful_script_count": sum(1 for row in script_records if row.get("ok")),
            "route_candidate_count": len(route_candidates),
            "interesting_snippet_count": sum(len(rows) for rows in interesting.values()),
            "publisher_custom_query_count": len(custom_queries),
        },
        "authority_boundary": {
            "custom_query_metadata_requested": True,
            "document_search_submitted": False,
            "keyword_metadata_requested": False,
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
            "CustomQuery metadata identifies publisher-issued search definitions; it is not a document search result.",
            "No query ID is guessed: every recorded query ID comes from the source-declared CustomQuery metadata endpoint.",
            "No absence, search result, vote, or terminal outcome is evaluated in this probe.",
        ],
    }
    (output / "public-access-probe.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["counts"], indent=2, sort_keys=True))

    if not custom_query_record.get("ok"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
