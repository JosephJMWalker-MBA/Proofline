#!/usr/bin/env python3
"""Probe Akron Public Access Committee Meeting Minutes query metadata only."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA = "proofline-akron-t21-committee-minutes-source-contract/v1"
SOURCE_SCHEMA = "proofline-akron-t21-public-access-source-contract-receipt/v1"
QUERY_NAME = "Committee Meeting Minutes"
QUERY_ID = "202"


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_json(value) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def select_minutes_query(source: dict) -> dict:
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected Public Access source-contract receipt schema")
    rows = source.get("custom_queries", {}).get("queries")
    if not isinstance(rows, list):
        raise ValueError("source contract lacks custom query metadata")
    matches = [row for row in rows if row.get("name") == QUERY_NAME]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {QUERY_NAME!r} query; found {len(matches)}")
    query = matches[0]
    if query.get("id") != QUERY_ID:
        raise ValueError("Committee Meeting Minutes query ID diverged from frozen publisher metadata")
    if query.get("type") != "DocumentType":
        raise ValueError("Committee Meeting Minutes must remain a DocumentType query")
    return query


def post_json(url: str, payload: dict, timeout: float = 45.0) -> tuple[dict, bytes]:
    body = stable_json(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={
        "User-Agent": "Proofline/0.1 public-record source-contract probe",
        "Accept": "application/json,*/*;q=0.5",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise RuntimeError("metadata response exceeded 5,000,000 bytes")
            return {"ok": True, "requested_url": url, "final_url": response.geturl(),
                    "status": getattr(response, "status", 200),
                    "content_type": response.headers.get("Content-Type")}, raw
    except HTTPError as exc:
        return {"ok": False, "requested_url": url, "final_url": exc.geturl(),
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type") if exc.headers else None,
                "error": f"HTTP {exc.code}: {exc.reason}"}, exc.read(1_000_000)
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {"ok": False, "requested_url": url, "final_url": url,
                "status": None, "content_type": None, "error": str(exc)}, b""


def parse_keywords(raw: bytes) -> tuple[dict, list[dict]]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Keywords response must be a JSON object")
    rows = payload.get("Data")
    if not isinstance(rows, list):
        raise ValueError("Keywords response must contain a Data array")
    keywords = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Keywords Data rows must be objects")
        keyword_id, name = row.get("ID"), row.get("Name")
        if not isinstance(keyword_id, (int, str)) or not str(keyword_id).strip():
            raise ValueError("keyword row lacks a stable publisher ID")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("keyword row lacks a publisher name")
        keywords.append({
            "id": str(keyword_id), "name": " ".join(name.split()),
            "data_type": row.get("DataType"), "required": row.get("Required"),
            "max_length": row.get("MaxLength"), "dataset": row.get("Dataset"),
            "is_masked": row.get("IsMasked"), "mask": row.get("Mask"),
            "mask_static": row.get("MaskStatic"),
            "mask_full_field_required": row.get("MaskFullFieldRequired"),
        })
    return payload, keywords


def main() -> int:
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-committee-minutes-source-contract")
    output.mkdir(parents=True, exist_ok=True)
    source = load_json(root / "r1_t21_public_access_source_contract_summary.json")
    query = select_minutes_query(source)
    api_root = source.get("configuration", {}).get("api_root")
    if api_root != "https://onlinedocs.akronohio.gov/PublicAccess/api":
        raise ValueError("Public Access API root diverged from frozen source contract")
    endpoint = api_root.rstrip("/") + "/Keywords"
    if urlparse(endpoint).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("Committee minutes keyword endpoint escaped publisher host")
    request_payload = {"QueryID": int(query["id"])}
    response, raw = post_json(endpoint, request_payload)
    (output / "committee-minutes-keywords.json").write_bytes(raw)
    response.update({"byte_length": len(raw), "sha256": sha256_bytes(raw),
                     "same_host": urlparse(response["requested_url"]).hostname == urlparse(response["final_url"]).hostname})
    if not response.get("ok") or not response.get("same_host"):
        raise RuntimeError("publisher Committee Meeting Minutes keyword metadata was unavailable")
    _, keywords = parse_keywords(raw)
    payload = {
        "schema": SCHEMA,
        "stage": "publisher_committee_minutes_query_metadata_only",
        "source_contract": {"schema": source["schema"], "api_root": api_root,
                            "query": query, "query_signature_sha256": sha256_json(query)},
        "keyword_metadata": {"endpoint": endpoint, "request_payload": request_payload,
                             "request_payload_sha256": sha256_json(request_payload),
                             "response": response, "count": len(keywords), "keywords": keywords,
                             "keywords_signature_sha256": sha256_json(keywords)},
        "authority_boundary": {
            "custom_query_metadata_inherited": True, "keyword_metadata_requested": True,
            "document_search_submitted": False, "query_id_guessed": False,
            "keyword_id_guessed": False, "document_token_enumerated": False,
            "returned_document_dereferenced": False, "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False, "causality_assigned": False,
            "detector_authorized": False, "lead_count": None,
        },
        "outcome": {"status": "unknown", "reason": "This stage requests publisher Committee Meeting Minutes query metadata only and does not submit a document search."},
        "non_claims": [
            "Committee Meeting Minutes query metadata does not establish that minutes exist for any particular committee meeting.",
            "No Eastwood Committee Meeting Minutes search is submitted in this stage.",
            "No absence, candidate, committee action, or terminal disposition is inferred from metadata."
        ],
    }
    (output / "committee-minutes-source-contract.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"query_id": query["id"], "query_name": query["name"], "keyword_count": len(keywords)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
