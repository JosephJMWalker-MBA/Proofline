"""Inspect CivicClerk published file metadata for Canton Council events.

The event IDs were discovered from Canton's official Calendar → CivicClerk links
by `inspect_canton_calendar_agendas.py`. This probe reads only the first-party
`publishedFileCollection` returned by CivicClerk's public Events API.
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen


API_BASE = "https://cantonoh.api.civicclerk.com/v1"
EVENT_IDS = [
    2067, 2068, 2069, 2070, 2071, 2072, 2073, 2075, 2076,
    2077, 2078, 2080, 2081, 2082, 2083, 2084, 2095,
]


def fetch_json(uri: str) -> tuple[object, dict]:
    request = Request(
        uri,
        headers={
            "User-Agent": "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        return json.loads(body.decode("utf-8")), {
            "status": response.status,
            "final_url": response.geturl(),
            "content_type": response.headers.get("Content-Type"),
            "content_length": len(body),
        }


def primitive_projection(value: object, *, depth: int = 0) -> object:
    """Retain public metadata shape while avoiding unrelated nested payloads."""
    if depth > 8:
        return "<depth-limit>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [primitive_projection(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, dict):
        return {
            str(key): primitive_projection(item, depth=depth + 1)
            for key, item in value.items()
            if not str(key).casefold().endswith("html")
            and str(key).casefold() not in {"description", "body", "content"}
        }
    return repr(value)


def collect_candidate_dicts(value: object, path: str = "$", *, depth: int = 0) -> list[dict]:
    if depth > 10:
        return []
    found: list[dict] = []
    if isinstance(value, dict):
        keys = {str(key).casefold() for key in value}
        if any("file" in key or "document" in key or "agenda" in key for key in keys) or (
            "id" in keys and ("name" in keys or "title" in keys or "type" in keys)
        ):
            projected = primitive_projection(value)
            if isinstance(projected, dict):
                found.append({"path": path, "values": projected})
        for key, item in value.items():
            found.extend(collect_candidate_dicts(item, f"{path}.{key}", depth=depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value[:500]):
            found.extend(collect_candidate_dicts(item, f"{path}[{index}]", depth=depth + 1))
    return found


def main() -> int:
    events: list[dict] = []
    for event_id in EVENT_IDS:
        uri = f"{API_BASE}/Events/{event_id}"
        try:
            payload, response = fetch_json(uri)
        except Exception as exc:
            events.append(
                {
                    "event_id": event_id,
                    "uri": uri,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        if not isinstance(payload, dict):
            events.append(
                {
                    "event_id": event_id,
                    "uri": uri,
                    "response": response,
                    "payload_type": type(payload).__name__,
                }
            )
            continue

        collection = payload.get("publishedFileCollection")
        events.append(
            {
                "event_id": event_id,
                "uri": uri,
                "response": response,
                "event_name": payload.get("eventName"),
                "event_date": payload.get("eventDate"),
                "published_file_collection": primitive_projection(collection),
                "file_candidates": collect_candidate_dicts(collection),
            }
        )

    print(
        json.dumps(
            {
                "api_base": API_BASE,
                "event_count": len(events),
                "events": events,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
