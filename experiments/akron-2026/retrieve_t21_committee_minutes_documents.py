#!/usr/bin/env python3
"""Retrieve frozen Akron Planning committee minutes source bytes for T21.

This stage requires a fresh reproduction of the #105 token-independent
Committee Meeting Minutes population before dereferencing any current opaque
Public Access handles. It preserves publisher metadata and source bytes only;
document content is not interpreted and no legislative disposition is assigned.
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

SEARCH_SCHEMA = "proofline-akron-t21-committee-minutes-date-search-measurement/v1"
RECEIPT_SCHEMA = "proofline-akron-t21-committee-minutes-date-search-receipt/v1"
SCHEMA = "proofline-akron-t21-committee-minutes-document-retrieval/v1"
MAX_METADATA_BYTES = 1_000_000
MAX_DOCUMENT_BYTES = 100_000_000
PUBLISHER_HOST = "onlinedocs.akronohio.gov"


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
        raise ValueError("unexpected fresh Committee minutes search schema")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected frozen Committee minutes search receipt schema")

    control = search["positive_control"]
    if (
        not control["response"]["ok"]
        or not control["response"]["same_host"]
        or control["truncated"]
        or control["returned_document_count"] < receipt["positive_control"]["minimum_returned_document_count"]
    ):
        raise ValueError("2026 Planning committee control did not establish a healthy search surface")

    expected_rows = receipt["eastwood_searches"]
    actual_rows = search["eastwood_searches"]
    if len(expected_rows) != 22 or len(actual_rows) != 22:
        raise ValueError("fresh search must contain exactly the 22 frozen Eastwood requests")
    actual_by_id = {row["meeting_id"]: row for row in actual_rows}
    if len(actual_by_id) != 22:
        raise ValueError("fresh Eastwood meeting IDs must remain unique")

    for expected in expected_rows:
        meeting_id = expected["meeting_id"]
        actual = actual_by_id.get(meeting_id)
        if actual is None:
            raise ValueError(f"fresh search omitted frozen meeting {meeting_id}")
        if actual["meeting_date"] != expected["meeting_date"]:
            raise ValueError(f"meeting {meeting_id} date drifted")
        if not actual["response"]["ok"] or not actual["response"]["same_host"] or actual["truncated"]:
            raise ValueError(f"meeting {meeting_id} search failed, redirected, or truncated")
        for key in (
            "request_payload_sha256",
            "returned_document_count",
            "stable_unique_projection_count",
            "stable_result_signature_sha256",
        ):
            if actual[key] != expected[key]:
                raise ValueError(f"meeting {meeting_id} drifted at {key}")

    pinned_counts = (
        "eastwood_request_count",
        "successful_eastwood_request_count",
        "truncated_eastwood_request_count",
        "eastwood_dates_with_results",
        "eastwood_dates_without_results",
        "eastwood_returned_document_token_count",
        "eastwood_stable_metadata_group_count",
        "eastwood_duplicate_metadata_group_count",
    )
    for key in pinned_counts:
        if search["counts"][key] != receipt["counts"][key]:
            raise ValueError(f"fresh Committee minutes population drifted at count {key}")

    candidate = search["candidate_population"]
    frozen_candidate = receipt["candidate_population"]
    if candidate["stable_population_signature_sha256"] != frozen_candidate["stable_population_signature_sha256"]:
        raise ValueError("stable Committee minutes candidate population drifted")
    if candidate["response_population_signature_sha256"] != frozen_candidate["response_population_signature_sha256"]:
        raise ValueError("Committee minutes response population drifted")
    if receipt["counts"]["eastwood_returned_document_token_count"] != 18:
        raise ValueError("frozen Committee minutes receipt must contain exactly 18 handles")
    if receipt["counts"]["eastwood_duplicate_metadata_group_count"] != 0:
        raise ValueError("frozen Committee minutes receipt unexpectedly contains duplicate metadata groups")


def document_base_uri(api_root: str, token: str) -> str:
    parsed = urlparse(api_root)
    if parsed.scheme != "https" or parsed.hostname != PUBLISHER_HOST:
        raise ValueError("document API root escaped publisher host")
    if not isinstance(token, str) or not token:
        raise ValueError("document token must be a non-empty string")
    return api_root.rstrip("/") + "/Document/" + quote(token, safe="") + "/"


def metadata_request(uri: str, timeout: float = 45.0) -> tuple[dict, bytes]:
    request = Request(
        uri,
        data=b"{}",
        method="POST",
        headers={
            "User-Agent": "Proofline/0.1 committee-minutes retrieval",
            "Accept": "application/json,*/*;q=0.5",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                raise RuntimeError("document metadata exceeded size limit")
            return {
                "ok": True,
                "requested_url": uri,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
            }, raw
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
    request = Request(
        uri,
        method="GET",
        headers={
            "User-Agent": "Proofline/0.1 committee-minutes retrieval",
            "Accept": "application/pdf,application/octet-stream,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(raw) > MAX_DOCUMENT_BYTES:
                raise RuntimeError("document exceeded size limit")
            return {
                "ok": True,
                "requested_url": uri,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
                "content_length_header": response.headers.get("Content-Length"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }, raw
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


def retrieve_one(api_root: str, meeting_id: int, document: dict, output: Path) -> dict:
    token = document["document_token"]
    base_uri = document_base_uri(api_root, token)
    metadata_http, metadata_raw = metadata_request(base_uri)
    if not metadata_http["ok"] or urlparse(metadata_http["final_url"]).hostname != PUBLISHER_HOST:
        raise RuntimeError(f"publisher metadata retrieval failed for meeting {meeting_id}")
    metadata = parse_document_metadata(metadata_raw)

    get_uri, representation = document_get_uri(base_uri, metadata)
    document_http, content = document_request(get_uri)
    if not document_http["ok"] or urlparse(document_http["final_url"]).hostname != PUBLISHER_HOST:
        raise RuntimeError(f"publisher document retrieval failed for meeting {meeting_id}")
    if not content:
        raise RuntimeError(f"empty document for meeting {meeting_id}")
    if representation == "pdf" and not content.startswith(b"%PDF-"):
        raise RuntimeError(f"publisher PDF representation lacked PDF signature for meeting {meeting_id}")

    meeting_dir = output / f"meeting-{meeting_id}"
    meeting_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = meeting_dir / "source.metadata.json"
    document_path = meeting_dir / ("source.pdf" if representation == "pdf" else "source.native.bin")
    metadata_path.write_bytes(metadata_raw)
    document_path.write_bytes(content)

    return {
        "meeting_id": meeting_id,
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
        "metadata_size_matches_document_bytes": metadata["Size"] == len(content),
        "metadata_filename": str(metadata_path.relative_to(output)),
        "document_filename": str(document_path.relative_to(output)),
        "metadata_http": metadata_http,
        "document_http": document_http,
    }


def stable_document_receipts(rows: list[dict]) -> list[dict]:
    return [
        {
            "meeting_id": row["meeting_id"],
            "stable_projection_sha256": row["stable_projection_sha256"],
            "representation": row["representation"],
            "document_sha256": row["document_sha256"],
            "document_byte_length": row["document_byte_length"],
            "document_pdf_signature": row["document_pdf_signature"],
            "metadata_size": row["metadata"]["Size"],
            "metadata_size_matches_document_bytes": row["metadata_size_matches_document_bytes"],
            "viewer_mode": row["metadata"]["ViewerMode"],
            "is_above_download_threshold": row["metadata"]["IsAboveDownloadThreshold"],
        }
        for row in sorted(rows, key=lambda item: item["meeting_id"])
    ]


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: retrieve_t21_committee_minutes_documents.py "
            "<fresh-search.json> <frozen-search-receipt.json> <output-dir>"
        )
    search_path = Path(sys.argv[1])
    receipt_path = Path(sys.argv[2])
    output = Path(sys.argv[3])
    output.mkdir(parents=True, exist_ok=True)

    search = load_json(search_path)
    receipt = load_json(receipt_path)
    validate_search_against_receipt(search, receipt)

    api_root = receipt["source_contract"]["api_root"]
    retrievals: list[dict] = []
    for search_row in search["eastwood_searches"]:
        documents = search_row["returned_documents"]
        if not documents:
            continue
        if len(documents) != 1:
            raise RuntimeError(f"meeting {search_row['meeting_id']} unexpectedly has multiple handles")
        retrievals.append(retrieve_one(api_root, search_row["meeting_id"], documents[0], output))

    expected_count = receipt["counts"]["eastwood_returned_document_token_count"]
    if len(retrievals) != expected_count != 18:
        raise RuntimeError("did not retrieve exactly the frozen 18 Committee minutes handles")
    if len({row["meeting_id"] for row in retrievals}) != 18:
        raise RuntimeError("retrieved Committee minutes meeting IDs are not unique")

    stable_receipts = stable_document_receipts(retrievals)
    payload = {
        "schema": SCHEMA,
        "stage": "publisher_committee_minutes_source_bytes_before_content_interpretation",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "fresh_search": {
            "measurement_sha256": sha256_bytes(search_path.read_bytes()),
            "frozen_receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
            "population_reproduced_before_dereference": True,
            "stable_candidate_population_signature_sha256": receipt["candidate_population"]["stable_population_signature_sha256"],
            "response_population_signature_sha256": receipt["candidate_population"]["response_population_signature_sha256"],
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
        "stable_document_receipts": stable_receipts,
        "stable_document_receipt_population_signature_sha256": sha256_json(stable_receipts),
        "counts": {
            "retrieved_handle_count": len(retrievals),
            "stable_group_count": len(stable_receipts),
            "pdf_retrieval_count": sum(row["representation"] == "pdf" for row in retrievals),
            "native_retrieval_count": sum(row["representation"] == "native" for row in retrievals),
            "unique_document_sha256_count": len({row["document_sha256"] for row in retrievals}),
            "metadata_size_match_count": sum(row["metadata_size_matches_document_bytes"] for row in retrievals),
        },
        "authority_boundary": {
            "fresh_candidate_population_reproduced": True,
            "every_current_returned_handle_retrieved": True,
            "source_bytes_preserved": True,
            "document_content_interpreted": False,
            "opaque_token_treated_as_stable_identity": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "Committee minutes source bytes are preserved before any content interpretation or disposition semantics."
        },
        "non_claims": [
            "Retrieved Committee Meeting Minutes bytes do not by themselves establish final Council disposition.",
            "The four frozen Committee-minutes non-finding dates remain bounded non-findings only.",
            "Opaque Public Access tokens are current retrieval handles, not stable document identity.",
            "No Committee minutes content is interpreted in this stage."
        ],
    }
    (output / "committee-minutes-document-retrieval.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"retrieved_handle_count": len(retrievals), "stable_group_count": len(stable_receipts)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
