"""Probe CivicClerk's public API using publisher-declared event/file URLs.

This is an experiment, not a production adapter. It starts from Canton event IDs already
published by the City's calendar, fetches the public event metadata, and then probes only
a small bounded sample of the exact file URLs returned in `publishedFiles`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = "https://cantonoh.api.civicclerk.com/v1"
EVENT_IDS = [
    2067, 2069, 2073, 2076, 2078, 2080, 2083, 2085, 2086,
    2090, 2095, 2096, 2097, 2102, 2103, 2105, 2106,
]
USER_AGENT = "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"


def fetch(uri: str) -> dict[str, Any]:
    request = Request(uri, headers={"User-Agent": USER_AGENT, "Accept": "application/json,application/pdf,*/*"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            result: dict[str, Any] = {
                "ok": True,
                "status": response.status,
                "final_url": response.geturl(),
                "content_type": content_type,
                "content_disposition": response.headers.get("Content-Disposition"),
                "content_length": len(body),
                "magic_hex": body[:16].hex(),
                "is_pdf_magic": body.startswith(b"%PDF"),
            }
            if "json" in content_type.casefold():
                try:
                    result["json"] = json.loads(body.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    result["body_preview"] = body[:1000].decode("utf-8", errors="replace")
            elif body and not result["is_pdf_magic"]:
                result["body_preview"] = body[:500].decode("utf-8", errors="replace")
            return result
    except HTTPError as exc:
        body = exc.read()
        return {
            "ok": False,
            "status": exc.code,
            "final_url": exc.geturl(),
            "content_type": exc.headers.get("Content-Type", ""),
            "content_disposition": exc.headers.get("Content-Disposition"),
            "content_length": len(body),
            "magic_hex": body[:16].hex(),
            "is_pdf_magic": body.startswith(b"%PDF"),
            "body_preview": body[:1000].decode("utf-8", errors="replace"),
        }
    except URLError as exc:
        return {"ok": False, "error": repr(exc)}


def published_files(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    value = payload.get("publishedFiles")
    if not isinstance(value, list):
        return []
    files: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        files.append(
            {
                key: item.get(key)
                for key in (
                    "fileId",
                    "fileType",
                    "name",
                    "type",
                    "publishOn",
                    "url",
                    "streamUrl",
                )
            }
        )
    return files


def main() -> int:
    events: list[dict[str, Any]] = []
    successful_events = 0
    published_file_count = 0
    agenda_file_count = 0
    successful_download_probes = 0
    pdf_download_probes = 0
    probes_remaining = 3

    for event_id in EVENT_IDS:
        uri = f"{API_BASE}/Events/{event_id}"
        response = fetch(uri)
        payload = response.get("json")
        files = published_files(payload)
        event: dict[str, Any] = {
            "event_id": event_id,
            "request_uri": uri,
            "response": response,
            "published_files": files,
            "download_probes": [],
        }
        if response.get("ok"):
            successful_events += 1
        published_file_count += len(files)
        agenda_file_count += sum(str(item.get("type") or "").casefold() == "agenda" for item in files)

        if probes_remaining > 0:
            for item in files:
                if str(item.get("type") or "").casefold() != "agenda":
                    continue
                download_uri = item.get("url")
                if not isinstance(download_uri, str) or not download_uri.startswith("https://"):
                    continue
                probe = fetch(download_uri)
                event["download_probes"].append({"published_file": item, "response": probe})
                probes_remaining -= 1
                if probe.get("ok"):
                    successful_download_probes += 1
                if probe.get("is_pdf_magic"):
                    pdf_download_probes += 1
                break

        events.append(event)

    print(json.dumps({
        "api_base": API_BASE,
        "event_count": len(EVENT_IDS),
        "successful_event_responses": successful_events,
        "published_file_count": published_file_count,
        "agenda_file_count": agenda_file_count,
        "successful_download_probes": successful_download_probes,
        "pdf_download_probes": pdf_download_probes,
        "events": events,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
