"""Probe CivicClerk's public API using endpoints declared by its first-party client.

This is an experiment, not a production adapter. It starts from Canton event IDs already
published by the City's calendar and records only public responses needed to establish a
stable event -> file acquisition contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://cantonoh.api.civicclerk.com/v1"
EVENT_IDS = [
    2067, 2069, 2073, 2076, 2078, 2080, 2083, 2085, 2086,
    2090, 2095, 2096, 2097, 2102, 2103, 2105, 2106,
]
USER_AGENT = "Proofline-R0/0.1 (+https://github.com/JosephJMWalker-MBA/Proofline)"


def fetch(uri: str) -> dict[str, Any]:
    request = Request(uri, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            result: dict[str, Any] = {
                "ok": True,
                "status": response.status,
                "final_url": response.geturl(),
                "content_type": content_type,
                "content_length": len(body),
            }
            if "json" in content_type.casefold():
                try:
                    result["json"] = json.loads(body.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    result["body_preview"] = body[:1000].decode("utf-8", errors="replace")
            else:
                result["body_preview"] = body[:500].decode("utf-8", errors="replace")
            return result
    except HTTPError as exc:
        body = exc.read()
        return {
            "ok": False,
            "status": exc.code,
            "final_url": exc.geturl(),
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": len(body),
            "body_preview": body[:1000].decode("utf-8", errors="replace"),
        }
    except URLError as exc:
        return {"ok": False, "error": repr(exc)}


def walk(value: Any, path: str = "$", *, out: list[dict[str, Any]]) -> None:
    """Collect mappings that look like CivicClerk file records without assuming schema."""
    if isinstance(value, Mapping):
        lowered = {str(key).casefold(): key for key in value}
        interesting = {
            "fileid", "filetype", "filename", "file_name", "name", "title",
            "documentid", "document_id", "attachmentid", "attachment_id",
            "agenda", "minutes", "packet", "plainText".casefold(),
        }
        if set(lowered).intersection(interesting):
            compact: dict[str, Any] = {}
            for folded, original in lowered.items():
                if folded in interesting:
                    item = value[original]
                    if isinstance(item, (str, int, float, bool)) or item is None:
                        compact[str(original)] = item
            if compact:
                out.append({"path": path, "fields": compact})
        for key, item in value.items():
            walk(item, f"{path}.{key}", out=out)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            walk(item, f"{path}[{index}]", out=out)


def file_candidates(payload: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    walk(payload, out=found)
    # Deterministic de-dup for readable artifacts.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in found:
        key = json.dumps(item, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def stream_probe(candidate: dict[str, Any]) -> dict[str, Any] | None:
    fields = candidate.get("fields", {})
    folded = {str(key).casefold(): value for key, value in fields.items()}
    file_id = folded.get("fileid")
    file_type = folded.get("filetype")
    if file_id is None or file_type is None:
        return None
    query = f"fileId={file_id},fileType={file_type},plainText=false"
    uri = f"{API_BASE}/Events/GetEventFileStream({query})"
    result = fetch(uri)
    # Preserve the request and metadata; never include full file bytes in this probe.
    result["request_uri"] = uri
    result["candidate"] = candidate
    return result


def main() -> int:
    events: list[dict[str, Any]] = []
    successful_events = 0
    file_candidate_count = 0
    stream_success_count = 0

    for event_id in EVENT_IDS:
        uri = f"{API_BASE}/Events/{event_id}"
        response = fetch(uri)
        event: dict[str, Any] = {"event_id": event_id, "request_uri": uri, "response": response}
        payload = response.get("json")
        candidates = file_candidates(payload) if payload is not None else []
        event["file_candidates"] = candidates
        file_candidate_count += len(candidates)
        if response.get("ok"):
            successful_events += 1

        probes: list[dict[str, Any]] = []
        # Probe only the first few unique fileId/fileType pairs per event to be polite.
        seen_pairs: set[tuple[str, str]] = set()
        for candidate in candidates:
            fields = {str(k).casefold(): v for k, v in candidate.get("fields", {}).items()}
            if "fileid" not in fields or "filetype" not in fields:
                continue
            pair = (str(fields["fileid"]), str(fields["filetype"]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            probe = stream_probe(candidate)
            if probe is not None:
                probes.append(probe)
                if probe.get("ok"):
                    stream_success_count += 1
            if len(probes) >= 3:
                break
        event["stream_probes"] = probes
        events.append(event)

    print(json.dumps({
        "api_base": API_BASE,
        "event_count": len(EVENT_IDS),
        "successful_event_responses": successful_events,
        "file_candidate_count": file_candidate_count,
        "successful_stream_probes": stream_success_count,
        "events": events,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
