"""Validate first-party CivicClerk published file metadata and streams for Canton.

The event IDs come from Canton's official Calendar -> CivicClerk event links.
The file IDs/types come only from each event's public `publishedFileCollection`.
No file identifiers are guessed or brute-forced.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://cantonoh.api.civicclerk.com/v1"
EVENT_IDS = [
    2067, 2068, 2069, 2070, 2071, 2072, 2073, 2075, 2076,
    2077, 2078, 2080, 2081, 2082, 2083, 2084, 2095,
]


def _request(uri: str) -> tuple[bytes, dict]:
    request = Request(
        uri,
        headers={
            "User-Agent": "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        return body, {
            "status": response.status,
            "final_url": response.geturl(),
            "content_type": response.headers.get("Content-Type"),
            "content_disposition": response.headers.get("Content-Disposition"),
            "content_length": len(body),
        }


def _json(uri: str) -> tuple[object, dict]:
    body, metadata = _request(uri)
    return json.loads(body.decode("utf-8")), metadata


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _primitive_metadata(value: dict) -> dict:
    return {
        str(key): item
        for key, item in value.items()
        if item is None or isinstance(item, (str, int, float, bool))
    }


def _file_candidates(value: object, path: str = "$") -> list[dict]:
    """Find exact fileId/fileType pairs published in the JSON tree."""
    found: list[dict] = []
    if isinstance(value, dict):
        normalized = {_normalized_key(key): (str(key), item) for key, item in value.items()}
        file_id = normalized.get("fileid")
        file_type = normalized.get("filetype") or normalized.get("filetypeid")
        if (
            file_id is not None
            and file_type is not None
            and isinstance(file_id[1], int)
            and isinstance(file_type[1], int)
        ):
            found.append(
                {
                    "path": path,
                    "file_id": file_id[1],
                    "file_type": file_type[1],
                    "published_metadata": _primitive_metadata(value),
                }
            )
        for key, item in value.items():
            found.extend(_file_candidates(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value[:1000]):
            found.extend(_file_candidates(item, f"{path}[{index}]"))
    return found


def _magic(body: bytes) -> str:
    if body.startswith(b"%PDF"):
        return "pdf"
    if body.startswith(b"PK\x03\x04"):
        return "zip_container"
    if body.startswith(b"\x89PNG"):
        return "png"
    if body.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return "other"


def main() -> int:
    events: list[dict] = []
    stream_results: list[dict] = []
    seen_streams: set[tuple[int, int]] = set()

    for event_id in EVENT_IDS:
        event_uri = f"{API_BASE}/Events/{event_id}"
        try:
            payload, response = _json(event_uri)
        except Exception as exc:
            events.append(
                {
                    "event_id": event_id,
                    "event_uri": event_uri,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        if not isinstance(payload, dict):
            events.append(
                {
                    "event_id": event_id,
                    "event_uri": event_uri,
                    "response": response,
                    "error": f"unexpected payload type: {type(payload).__name__}",
                }
            )
            continue

        collection = payload.get("publishedFileCollection")
        candidates = _file_candidates(collection)
        events.append(
            {
                "event_id": event_id,
                "event_uri": event_uri,
                "event_name": payload.get("eventName"),
                "event_date": payload.get("eventDate"),
                "response": response,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

        for candidate in candidates:
            identity = (candidate["file_id"], candidate["file_type"])
            if identity in seen_streams:
                continue
            seen_streams.add(identity)
            params = urlencode(
                {
                    "fileId": candidate["file_id"],
                    "fileType": candidate["file_type"],
                    "plainText": "false",
                }
            )
            stream_uri = f"{API_BASE}/Events/GetEventFileStream?{params}"
            try:
                body, stream_response = _request(stream_uri)
                stream_results.append(
                    {
                        "event_id": event_id,
                        **candidate,
                        "stream_uri": stream_uri,
                        "response": stream_response,
                        "magic": _magic(body),
                        "first_16_hex": body[:16].hex(),
                    }
                )
            except Exception as exc:
                stream_results.append(
                    {
                        "event_id": event_id,
                        **candidate,
                        "stream_uri": stream_uri,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    output = {
        "api_base": API_BASE,
        "event_count": len(events),
        "published_candidate_count": sum(event.get("candidate_count", 0) for event in events),
        "unique_stream_count": len(stream_results),
        "stream_magic_counts": dict(Counter(item.get("magic", "error") for item in stream_results)),
        "events": events,
        "streams": stream_results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))

    successful_events = {
        item["event_id"]
        for item in stream_results
        if item.get("magic") == "pdf" and (item.get("response") or {}).get("status") == 200
    }
    return 0 if successful_events else 1


if __name__ == "__main__":
    raise SystemExit(main())
