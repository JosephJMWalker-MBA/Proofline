"""Probe CivicClerk's public API using publisher-declared event/file URLs.

This is an experiment, not a production adapter. It starts from Canton event IDs already
published by the City's calendar, fetches public event metadata, and then follows only a
small bounded sample of publisher-issued agenda transports. Signed blob query strings are
used in-memory for retrieval but are never written to the probe artifact.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


API_BASE = "https://cantonoh.api.civicclerk.com/v1"
EVENT_IDS = [
    2067, 2069, 2073, 2076, 2078, 2080, 2083, 2085, 2086,
    2090, 2095, 2096, 2097, 2102, 2103, 2105, 2106,
]
USER_AGENT = "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"
_ALLOWED_BLOB_HOST = "civicclerk.blob.core.windows.net"


def redact_query(uri: str) -> str:
    parts = urlsplit(uri)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def fetch(uri: str, *, redact_final_query: bool = False) -> dict[str, Any]:
    request = Request(
        uri,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,application/pdf,*/*"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
            result: dict[str, Any] = {
                "ok": True,
                "status": response.status,
                "final_url": redact_query(final_url) if redact_final_query else final_url,
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
        final_url = exc.geturl()
        return {
            "ok": False,
            "status": exc.code,
            "final_url": redact_query(final_url) if redact_final_query else final_url,
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


def _blob_uri(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("blobUri")
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_BLOB_HOST:
        return None
    if not parsed.path.startswith("/stream/CANTONOH/"):
        return None
    return value


def main() -> int:
    events: list[dict[str, Any]] = []
    successful_events = 0
    published_file_count = 0
    agenda_file_count = 0
    successful_api_envelopes = 0
    successful_blob_downloads = 0
    pdf_blob_downloads = 0
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

                api_response = fetch(download_uri)
                blob_uri = _blob_uri(api_response.get("json"))
                sanitized_api_response = dict(api_response)
                if blob_uri is not None:
                    successful_api_envelopes += 1
                    sanitized_json = dict(api_response.get("json") or {})
                    sanitized_json["blobUri"] = redact_query(blob_uri)
                    sanitized_json["blobUriQueryRedacted"] = True
                    sanitized_api_response["json"] = sanitized_json
                    blob_response = fetch(blob_uri, redact_final_query=True)
                    if blob_response.get("ok"):
                        successful_blob_downloads += 1
                    if blob_response.get("is_pdf_magic"):
                        pdf_blob_downloads += 1
                else:
                    blob_response = None

                event["download_probes"].append(
                    {
                        "published_file": item,
                        "api_response": sanitized_api_response,
                        "blob_response": blob_response,
                    }
                )
                probes_remaining -= 1
                break

        events.append(event)

    print(
        json.dumps(
            {
                "api_base": API_BASE,
                "event_count": len(EVENT_IDS),
                "successful_event_responses": successful_events,
                "published_file_count": published_file_count,
                "agenda_file_count": agenda_file_count,
                "successful_api_envelopes": successful_api_envelopes,
                "successful_blob_downloads": successful_blob_downloads,
                "pdf_blob_downloads": pdf_blob_downloads,
                "events": events,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
