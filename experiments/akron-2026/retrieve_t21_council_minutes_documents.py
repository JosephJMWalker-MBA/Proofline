#!/usr/bin/env python3
"""Retrieve governed Akron Council Meeting Minutes candidates for T21.

This stage first requires a freshly reproduced #100 exact-date search population.
Only then does it dereference every currently returned opaque document handle
through the publisher-declared Public Access document route. Source bytes and
metadata are preserved. Document content is not interpreted and no disposition
is assigned.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

SEARCH_SCHEMA = "proofline-akron-t21-council-minutes-date-search-measurement/v1"
RECEIPT_SCHEMA = "proofline-akron-t21-council-minutes-date-search-receipt/v1"
SCHEMA = "proofline-akron-t21-council-minutes-document-retrieval/v1"
MAX_METADATA_BYTES = 1_000_000
MAX_DOCUMENT_BYTES = 100_000_000


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def validate_search_against_receipt(search: dict, receipt: dict) -> None:
    if search.get("schema") != SEARCH_SCHEMA:
        raise ValueError("unexpected fresh minutes-search schema")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected frozen minutes-search receipt schema")

    control = search["positive_control"]
    if not control["response"]["ok"] or control["truncated"] or control["returned_document_count"] < 1:
        raise ValueError("Year-2026 control did not establish a healthy minutes search surface")

    expected_dates = receipt["date_receipts"]
    actual_dates = search["eastwood_searches"]
    if len(actual_dates) != len(expected_dates) or len(expected_dates) != 22:
        raise ValueError("fresh search must contain exactly the 22 frozen Eastwood dates")

    actual_by_id = {row["meeting_id"]: row for row in actual_dates}
    if len(actual_by_id) != 22:
        raise ValueError("fresh Eastwood meeting IDs must be unique")

    for expected in expected_dates:
        meeting_id = expected["meeting_id"]
        actual = actual_by_id.get(meeting_id)
        if actual is None:
            raise ValueError(f"fresh search omitted frozen meeting {meeting_id}")
        if actual["meeting_date"] != expected["meeting_date"]:
            raise ValueError(f"meeting {meeting_id} date drifted")
        if not actual["response"]["ok"] or actual["truncated"]:
            raise ValueError(f"meeting {meeting_id} search failed or truncated")
        for key in (
            "request_payload_sha256",
            "returned_document_count",
            "stable_result_signature_sha256",
            "stable_unique_projection_count",
        ):
            if actual[key] != expected[key]:
                raise ValueError(f"meeting {meeting_id} drifted at {key}")

    counts = search["counts"]
    frozen_counts = receipt["counts"]
    pinned = (
        "eastwood_request_count",
        "successful_eastwood_request_count",
        "truncated_eastwood_request_count",
        "eastwood_dates_with_results",
        "eastwood_dates_without_results",
        "eastwood_returned_document_token_count",
        "eastwood_stable_metadata_group_count",
        "eastwood_duplicate_metadata_group_count",
    )
    for key in pinned:
        if counts[key] != frozen_counts[key]:
            raise ValueError(f"fresh search population drifted at count {key}")

    if (
        search["candidate_population"]["stable_signature_sha256"]
        != receipt["stable_candidate_population_signature_sha256"]
    ):
        raise ValueError("stable candidate population drifted")
    if (
        search["eastwood_response_population_signature_sha256"]
        != receipt["eastwood_response_population_signature_sha256"]
    ):
        raise ValueError("Eastwood response population drifted")


def document_base_uri(api_root: str, token: str) -> str:
    parsed = urlparse(api_root)
    if parsed.scheme != "https" or parsed.hostname != "onlinedocs.akronohio.gov":
        raise ValueError("document API root escaped publisher host")
    if not isinstance(token, str) or not token:
        raise ValueError("document token must be a non-empty string")
    return api_root.rstrip("/") + "/Document/" + quote(token, safe="") + "/"


def metadata_request(uri: str, timeout: float = 45.0) -> tuple[dict, bytes]:
    req = Request(
        uri,
        data=b"{}",
        method="POST",
        headers={
            "User-Agent": "Proofline/0.1 public-record minutes retrieval",
            "Accept": "application/json,*/*;q=0.5",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                raise RuntimeError("document metadata exceeded size limit")
            record = {
                "ok": True,
                "requested_url": uri,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
            }
            return record, raw
    except HTTPError as exc:
        return {
            "ok": False,
            "requested_url": uri,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "error": f"HTTP {exc.code}: {exc.reason}",
        }, exc.read(MAX_METADATA_BYTES)
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {
            "ok": False,
            "requested_url": uri,
            "final_url": uri,
            "status": None,
            "content_type": None,
            "error": str(exc),
        }, b""


def parse_document_metadata(raw: bytes) -> dict:
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("document metadata must be a JSON object")
    viewer_mode = value.get("ViewerMode")
    if viewer_mode not in {"PDF", "Native", "NativeOptional"}:
        raise ValueError(f"unsupported publisher ViewerMode: {viewer_mode!r}")
    above = value.get("IsAboveDownloadThreshold")
    if not isinstance(above, bool):
        raise ValueError("document metadata must include boolean IsAboveDownloadThreshold")
    size = value.get("Size")
    if not isinstance(size, (int, float)) or isinstance(size, bool) or size < 0:
        raise ValueError("document metadata must include non-negative numeric Size")
    return {
        "Size": size,
        "ViewerMode": viewer_mode,
        "IsAboveDownloadThreshold": above,
    }


def document_get_uri(base_uri: str, metadata: dict) -> tuple[str, str]:
    viewer = metadata["ViewerMode"]
    above = metadata["IsAboveDownloadThreshold"]
    if viewer == "Native":
        return base_uri + "?ViewerMode=Native&ForceDownload=true", "native"
    if above:
        return base_uri + "?ForceDownload=true", "pdf"
    return base_uri, "pdf"


def document_request(uri: str, timeout: float = 90.0) -> tuple[dict, bytes]:
    req = Request(
        uri,
        method="GET",
        headers={
            "User-Agent": "Proofline/0.1 public-record minutes retrieval",
            "Accept": "application/pdf,application/octet-stream,*/*;q=0.5",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(raw) > MAX_DOCUMENT_BYTES:
                raise RuntimeError("document exceeded size limit")
            record = {
                "ok": True,
                "requested_url": uri,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
                "content_length_header": response.headers.get("Content-Length"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }
            return record, raw
    except HTTPError as exc:
        return {
            "ok": False,
            "requested_url": uri,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "error": f"HTTP {exc.code}: {exc.reason}",
        }, exc.read(1_000_000)
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {
            "ok": False,
            "requested_url": uri,
            "final_url": uri,
            "status": None,
            "content_type": None,
            "error": str(exc),
        }, b""


def retrieve_one(api_root: str, meeting_id: int, handle_index: int, document: dict, output: Path) -> dict:
    token = document["document_token"]
    base_uri = document_base_uri(api_root, token)

    metadata_http, metadata_raw = metadata_request(base_uri)
    if not metadata_http["ok"]:
        raise RuntimeError(f"metadata retrieval failed for meeting {meeting_id} handle {handle_index}")
    if urlparse(metadata_http["final_url"]).hostname != "onlinedocs.akronohio.gov":
        raise RuntimeError("document metadata redirected off publisher host")
    metadata = parse_document_metadata(metadata_raw)

    get_uri, representation = document_get_uri(base_uri, metadata)
    content_http, content = document_request(get_uri)
    if not content_http["ok"]:
        raise RuntimeError(f"document retrieval failed for meeting {meeting_id} handle {handle_index}")
    if urlparse(content_http["final_url"]).hostname != "onlinedocs.akronohio.gov":
        raise RuntimeError("document content redirected off publisher host")
    if not content:
        raise RuntimeError(f"empty document for meeting {meeting_id} handle {handle_index}")
    if representation == "pdf" and not content.startswith(b"%PDF-"):
        raise RuntimeError(f"publisher PDF representation lacked PDF signature for meeting {meeting_id}")

    meeting_dir = output / f"meeting-{meeting_id}"
    meeting_dir.mkdir(parents=True, exist_ok=True)
    prefix = meeting_dir / f"handle-{handle_index:02d}"
    metadata_path = prefix.with_suffix(".metadata.json")
    document_path = prefix.with_suffix(".pdf" if representation == "pdf" else ".native.bin")
    metadata_path.write_bytes(metadata_raw)
    document_path.write_bytes(content)

    return {
        "meeting_id": meeting_id,
        "handle_index": handle_index,
        "opaque_token_sha256": sha256_bytes(token.encode("utf-8")),
        "stable_projection": document["stable_projection"],
        "stable_projection_sha256": document["stable_projection_sha256"],
        "metadata": metadata,
        "metadata_raw_sha256": sha256_bytes(metadata_raw),
        "metadata_raw_byte_length": len(metadata_raw),
        "representation": representation,
        "document_sha256": sha256_bytes(content),
        "document_byte_length": len(content),
        "document_pdf_signature": content.startswith(b"%PDF-"),
        "metadata_filename": str(metadata_path.relative_to(output)),
        "document_filename": str(document_path.relative_to(output)),
        "metadata_http": metadata_http,
        "document_http": content_http,
    }


def group_retrievals(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, str], list[dict]] = {}
    for row in rows:
        key = (row["meeting_id"], row["stable_projection_sha256"])
        grouped.setdefault(key, []).append(row)

    result = []
    for (meeting_id, projection_sha), members in sorted(grouped.items()):
        hashes = sorted({row["document_sha256"] for row in members})
        if len(members) == 1:
            comparison = "single_handle"
        elif len(hashes) == 1:
            comparison = "multiple_handles_identical_retrieved_bytes"
        else:
            comparison = "multiple_handles_distinct_retrieved_bytes"
        result.append(
            {
                "meeting_id": meeting_id,
                "stable_projection_sha256": projection_sha,
                "handle_count": len(members),
                "unique_retrieved_byte_hash_count": len(hashes),
                "retrieved_document_sha256s": hashes,
                "comparison": comparison,
            }
        )
    return result


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: retrieve_t21_council_minutes_documents.py "
            "<fresh-search-measurement.json> <frozen-search-receipt.json> <output-dir>"
        )
    search_path = Path(sys.argv[1])
    receipt_path = Path(sys.argv[2])
    output = Path(sys.argv[3])
    output.mkdir(parents=True, exist_ok=True)

    search = load_json(search_path)
    receipt = load_json(receipt_path)
    validate_search_against_receipt(search, receipt)

    api_root = receipt["source_contract"]["api_root"]
    retrievals = []
    for search_row in search["eastwood_searches"]:
        if not search_row["returned_documents"]:
            continue
        for index, document in enumerate(search_row["returned_documents"], start=1):
            retrievals.append(
                retrieve_one(api_root, search_row["meeting_id"], index, document, output)
            )

    if len(retrievals) != receipt["counts"]["eastwood_returned_document_token_count"]:
        raise RuntimeError("did not retrieve every fresh Eastwood minutes handle")

    groups = group_retrievals(retrievals)
    duplicate_groups = [row for row in groups if row["handle_count"] > 1]
    if len(groups) != receipt["counts"]["eastwood_stable_metadata_group_count"]:
        raise RuntimeError("retrieved stable group count diverged from frozen search receipt")
    if len(duplicate_groups) != receipt["counts"]["eastwood_duplicate_metadata_group_count"]:
        raise RuntimeError("retrieved duplicate group count diverged from frozen search receipt")

    payload = {
        "schema": SCHEMA,
        "stage": "publisher_council_minutes_source_byte_retrieval_before_content_interpretation",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "fresh_search": {
            "measurement_sha256": sha256_bytes(search_path.read_bytes()),
            "frozen_receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
            "population_reproduced_before_dereference": True,
            "returned_handle_count": len(retrievals),
        },
        "retrieval_contract": {
            "api_root": api_root,
            "metadata_method": "POST",
            "metadata_body": "{}",
            "document_method": "GET",
            "publisher_client_route": "/Document/{encodeURIComponent(token)}/",
            "max_metadata_bytes": MAX_METADATA_BYTES,
            "max_document_bytes": MAX_DOCUMENT_BYTES,
        },
        "retrievals": retrievals,
        "stable_groups": groups,
        "counts": {
            "retrieved_handle_count": len(retrievals),
            "stable_group_count": len(groups),
            "duplicate_metadata_group_count": len(duplicate_groups),
            "duplicate_groups_with_identical_retrieved_bytes": sum(
                row["comparison"] == "multiple_handles_identical_retrieved_bytes"
                for row in duplicate_groups
            ),
            "duplicate_groups_with_distinct_retrieved_bytes": sum(
                row["comparison"] == "multiple_handles_distinct_retrieved_bytes"
                for row in duplicate_groups
            ),
            "pdf_retrieval_count": sum(row["representation"] == "pdf" for row in retrievals),
            "native_retrieval_count": sum(row["representation"] == "native" for row in retrievals),
        },
        "authority_boundary": {
            "fresh_candidate_population_reproduced": True,
            "every_current_returned_handle_retrieved": True,
            "opaque_token_treated_as_stable_identity": False,
            "source_bytes_preserved": True,
            "duplicate_group_equivalence_inferred_from_metadata": False,
            "retrieved_byte_equality_recorded_as_observation_only": True,
            "document_content_interpreted": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": (
                "This stage retrieves publisher document bytes for the already governed "
                "minutes candidates. Byte equality/difference resolves only the current "
                "retrieved representations, not legislative disposition."
            ),
        },
    }
    payload["retrieved_byte_population_signature_sha256"] = sha256_json(
        [
            {
                "meeting_id": row["meeting_id"],
                "stable_projection_sha256": row["stable_projection_sha256"],
                "metadata": row["metadata"],
                "representation": row["representation"],
                "document_sha256": row["document_sha256"],
                "document_byte_length": row["document_byte_length"],
            }
            for row in retrievals
        ]
    )
    payload["stable_group_comparison_signature_sha256"] = sha256_json(groups)

    summary = output / "council-minutes-document-retrieval.json"
    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
