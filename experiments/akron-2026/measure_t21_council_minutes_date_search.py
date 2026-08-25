#!/usr/bin/env python3
"""Measure frozen Akron Council Meeting Minutes searches for Eastwood-linked dates.

The plan is fixed before observation. A Year=2026 request is a surface-health
control only. Twenty-two exact Meeting Date requests come from the frozen
Eastwood exact-title chronology. Returned document tokens are preserved for
future retrieval but excluded from stable identity because Public Access tokens
have already been observed to rotate. This stage assigns no disposition.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA = "proofline-akron-t21-council-minutes-date-search-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-council-minutes-date-search-plan/v1"
SOURCE_SCHEMA = "proofline-akron-t21-council-minutes-source-contract-receipt/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"
SEQUENCE_SCHEMA = "proofline-akron-t21-agenda-status-sequence-receipt/v1"


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


def iso_to_display_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.strftime("%m/%d/%Y")


def validate_inputs(plan: dict, source: dict, target: dict, sequence: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected minutes date-search plan schema")
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected Council minutes source receipt schema")
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError("unexpected target schema")
    if sequence.get("schema") != SEQUENCE_SCHEMA:
        raise ValueError("unexpected agenda-status sequence schema")

    contract = plan["source_contract"]
    frozen_query = source["source_contract"]["query"]
    frozen_keywords = {row["id"]: row for row in source["keyword_metadata"]["keywords"]}
    if contract["api_root"] != source["source_contract"]["api_root"]:
        raise ValueError("API root diverged from frozen minutes source contract")
    if contract["query_id"] != 175 or str(contract["query_id"]) != frozen_query["id"]:
        raise ValueError("query ID must be publisher-issued Council Meeting Minutes 175")
    if contract["query_name"] != frozen_query["name"] != "Council Meeting Minutes":
        raise ValueError("query name diverged")
    if contract["query_limit"] != 0:
        raise ValueError("query limit changed")
    if contract["meeting_date_keyword"] != {
        "id": 124,
        "name": "Meeting Date",
        "data_type": "Date",
        "serialization": "MM/DD/YYYY",
    }:
        raise ValueError("Meeting Date contract changed")
    if frozen_keywords["124"]["name"] != "Meeting Date" or frozen_keywords["124"]["data_type"] != "Date":
        raise ValueError("frozen publisher Meeting Date keyword unavailable")
    if contract["year_keyword"] != {"id": 532, "name": "Year", "data_type": "SmallNumeric"}:
        raise ValueError("Year control contract changed")
    if frozen_keywords["532"]["name"] != "Year" or frozen_keywords["532"]["data_type"] != "SmallNumeric":
        raise ValueError("frozen publisher Year keyword unavailable")
    if not frozen_keywords["532"]["dataset_summary"]["contains_2026"]:
        raise ValueError("frozen publisher Year dataset no longer establishes 2026 control basis")

    control = plan["positive_control"]
    if control != {
        "request_id": "year_2026_control",
        "query_id": 175,
        "keyword": {"ID": 532, "Name": "Year", "Value": "2026", "KeywordOperator": "="},
        "QueryLimit": 0,
        "included_in_eastwood_population": False,
        "basis": control["basis"],
    }:
        raise ValueError("positive control changed")

    expected_ids = target["provenance"]["publisher_meeting_ids_with_exact_title"]
    requests = plan.get("eastwood_requests")
    if not isinstance(requests, list) or [row.get("meeting_id") for row in requests] != expected_ids:
        raise ValueError("minutes search population must exactly equal frozen exact-title meeting IDs")
    if len(requests) != 22 or len(set(expected_ids)) != 22:
        raise ValueError("expected 22 unique exact-title meetings")

    sequence_rows = {row[0]: row for row in sequence["sequence_rows"]}
    for row in requests:
        meeting_id = row["meeting_id"]
        if meeting_id not in sequence_rows:
            raise ValueError(f"meeting {meeting_id} missing from frozen chronology")
        sequence_row = sequence_rows[meeting_id]
        if sequence_row[2] != "at_or_before_observation":
            raise ValueError(f"meeting {meeting_id} is outside frozen observation boundary")
        iso_date = sequence_row[1][:10]
        if row["meeting_date"] != iso_date:
            raise ValueError(f"meeting {meeting_id} date diverged from frozen chronology")
        if row["keyword_value"] != iso_to_display_date(iso_date):
            raise ValueError(f"meeting {meeting_id} keyword date is not MM/DD/YYYY serialization")
        if row["request_id"] != f"meeting_{meeting_id}_{iso_date.replace('-', '_')}":
            raise ValueError(f"meeting {meeting_id} request ID changed")

    selection = plan["selection_rule"]
    if selection["post_result_date_or_term_expansion_allowed"] is not False:
        raise ValueError("post-result expansion must remain forbidden")
    if selection["returned_documents_dereferenced_in_this_stage"] is not False:
        raise ValueError("document dereference must remain forbidden")


def post_json(url: str, payload: dict, *, timeout: float = 45.0) -> tuple[dict, bytes]:
    body = stable_json(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "Proofline/0.1 public-record minutes measurement",
            "Accept": "application/json,*/*;q=0.5",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(25_000_001)
            if len(raw) > 25_000_000:
                raise RuntimeError("response exceeded 25,000,000 bytes")
            return {
                "ok": True,
                "requested_url": url,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
            }, raw
    except HTTPError as exc:
        return {
            "ok": False,
            "requested_url": url,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "error": f"HTTP {exc.code}: {exc.reason}",
        }, exc.read(1_000_000)
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {
            "ok": False,
            "requested_url": url,
            "final_url": url,
            "status": None,
            "content_type": None,
            "error": str(exc),
        }, b""


def stable_document_projection(row: dict) -> dict:
    return {
        "name": row.get("Name"),
        "display_column_values": row.get("DisplayColumnValues"),
        "score": row.get("Score"),
        "summary": row.get("Summary"),
    }


def parse_search_response(raw: bytes) -> tuple[list[dict], bool, object]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("KeywordSearch response must be an object")
    rows = payload.get("Data")
    if not isinstance(rows, list):
        raise ValueError("KeywordSearch response must contain a Data array")
    documents = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("KeywordSearch rows must be objects")
        token = row.get("ID")
        if not isinstance(token, (str, int)) or not str(token).strip():
            raise ValueError("returned minutes row lacks publisher document token")
        stable = stable_document_projection(row)
        documents.append({
            "document_token": str(token),
            "stable_projection": stable,
            "stable_projection_sha256": sha256_json(stable),
            "raw_row_sha256": sha256_json(row),
        })
    return documents, bool(payload.get("Truncated")), payload.get("DisplayColumns")


def request_payload(query_id: int, keyword: dict, query_limit: int) -> dict:
    return {"QueryID": query_id, "Keywords": [keyword], "QueryLimit": query_limit}


def run_one(endpoint: str, request_id: str, payload: dict, output: Path) -> dict:
    response, raw = post_json(endpoint, payload)
    filename = f"{request_id}.json"
    (output / filename).write_bytes(raw)
    response.update({
        "byte_length": len(raw),
        "sha256": sha256_bytes(raw),
        "same_host": urlparse(response["requested_url"]).hostname == urlparse(response["final_url"]).hostname,
    })
    documents = []
    truncated = False
    display_columns = None
    if response["ok"]:
        documents, truncated, display_columns = parse_search_response(raw)
    stable_rows = [d["stable_projection"] for d in documents]
    stable_unique = []
    seen = set()
    for stable in stable_rows:
        digest = sha256_json(stable)
        if digest not in seen:
            seen.add(digest)
            stable_unique.append(stable)
    return {
        "request_id": request_id,
        "request_payload": payload,
        "request_payload_sha256": sha256_json(payload),
        "response": response,
        "truncated": truncated,
        "returned_document_count": len(documents),
        "returned_documents": documents,
        "stable_unique_projection_count": len(stable_unique),
        "stable_result_signature_sha256": sha256_json(stable_unique),
        "display_columns": display_columns,
        "raw_filename": filename,
    }


def group_stable_candidates(searches: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, str], dict] = {}
    for search in searches:
        for document in search["returned_documents"]:
            key = (search["meeting_id"], document["stable_projection_sha256"])
            group = grouped.get(key)
            if group is None:
                group = {
                    "meeting_id": search["meeting_id"],
                    "meeting_date": search["meeting_date"],
                    "stable_projection": document["stable_projection"],
                    "stable_projection_sha256": document["stable_projection_sha256"],
                    "observed_document_tokens": [],
                    "observed_raw_row_sha256": [],
                }
                grouped[key] = group
            group["observed_document_tokens"].append(document["document_token"])
            group["observed_raw_row_sha256"].append(document["raw_row_sha256"])

    result = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1])):
        group = grouped[key]
        group["observed_token_count"] = len(group["observed_document_tokens"])
        result.append(group)
    return result


def stable_group_signature_projection(groups: list[dict]) -> list[dict]:
    return [
        {
            "meeting_id": group["meeting_id"],
            "meeting_date": group["meeting_date"],
            "stable_projection": group["stable_projection"],
            "stable_projection_sha256": group["stable_projection_sha256"],
        }
        for group in groups
    ]


def main() -> int:
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-council-minutes-date-search")
    output.mkdir(parents=True, exist_ok=True)

    plan = load_json(root / "r1_t21_council_minutes_date_search_plan.json")
    source = load_json(root / "r1_t21_council_minutes_source_contract_summary.json")
    target = load_json(root / "r1_t21_terminal_record_target.json")
    sequence = load_json(root / "r1_t21_agenda_status_sequence_summary.json")
    validate_inputs(plan, source, target, sequence)

    endpoint = source["source_contract"]["api_root"].rstrip("/") + "/CustomQuery/KeywordSearch"
    if urlparse(endpoint).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("minutes search endpoint escaped publisher host")

    control_spec = plan["positive_control"]
    control = run_one(
        endpoint,
        control_spec["request_id"],
        request_payload(control_spec["query_id"], control_spec["keyword"], control_spec["QueryLimit"]),
        output,
    )

    searches = []
    for spec in plan["eastwood_requests"]:
        keyword = {
            "ID": 124,
            "Name": "Meeting Date",
            "Value": spec["keyword_value"],
            "KeywordOperator": "=",
        }
        result = run_one(endpoint, spec["request_id"], request_payload(175, keyword, 0), output)
        result["meeting_id"] = spec["meeting_id"]
        result["meeting_date"] = spec["meeting_date"]
        searches.append(result)

    any_failure = (not control["response"]["ok"]) or any(not row["response"]["ok"] for row in searches)
    any_truncation = control["truncated"] or any(row["truncated"] for row in searches)

    stable_groups = group_stable_candidates(searches)
    stable_signature_rows = stable_group_signature_projection(stable_groups)
    raw_token_count = sum(row["returned_document_count"] for row in searches)
    duplicate_groups = sum(1 for group in stable_groups if group["observed_token_count"] > 1)

    measurement = {
        "schema": SCHEMA,
        "stage": "publisher_council_minutes_exact_date_candidate_search_only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan": {
            "schema": plan["schema"],
            "sha256": sha256_json(plan),
            "eastwood_request_count": len(plan["eastwood_requests"]),
            "post_result_expansion_allowed": False,
        },
        "source_contract": {
            "schema": source["schema"],
            "api_root": source["source_contract"]["api_root"],
            "query_id": "175",
            "query_name": "Council Meeting Minutes",
            "meeting_date_keyword_id": "124",
            "year_keyword_id": "532",
            "query_limit": 0,
        },
        "endpoint": endpoint,
        "positive_control": control,
        "eastwood_searches": searches,
        "candidate_population": {
            "identity_boundary": "meeting_id_plus_publisher_stable_projection; opaque tokens preserved only as observed retrieval handles",
            "stable_group_count": len(stable_groups),
            "raw_retrieval_token_count": raw_token_count,
            "duplicate_metadata_group_count": duplicate_groups,
            "groups": stable_groups,
            "stable_signature_sha256": sha256_json(stable_signature_rows),
        },
        "counts": {
            "positive_control_returned_document_count": control["returned_document_count"],
            "eastwood_request_count": len(searches),
            "successful_eastwood_request_count": sum(1 for row in searches if row["response"]["ok"]),
            "truncated_eastwood_request_count": sum(1 for row in searches if row["truncated"]),
            "eastwood_dates_with_results": sum(1 for row in searches if row["returned_document_count"] > 0),
            "eastwood_dates_without_results": sum(1 for row in searches if row["returned_document_count"] == 0),
            "eastwood_returned_document_token_count": raw_token_count,
            "eastwood_stable_metadata_group_count": len(stable_groups),
            "eastwood_duplicate_metadata_group_count": duplicate_groups,
        },
        "authority_boundary": {
            "document_search_submitted": True,
            "only_predeclared_dates_used": True,
            "post_result_expansion_performed": False,
            "positive_control_excluded_from_eastwood_population": True,
            "query_id_guessed": False,
            "keyword_id_guessed": False,
            "opaque_document_token_treated_as_stable_identity": False,
            "identical_visible_metadata_assumed_same_document": False,
            "identical_visible_metadata_assumed_distinct_documents": False,
            "returned_document_dereferenced": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "This stage measures publisher-returned Council Meeting Minutes retrieval candidates for predeclared dates only. Presence, absence, and duplicate visible metadata are not disposition.",
        },
        "non_claims": plan["non_claims"] + [
            "Two different opaque tokens with identical visible metadata are not assumed to be either the same underlying document or distinct underlying documents until separately retrieved."
        ],
    }
    measurement["eastwood_response_population_signature_sha256"] = sha256_json([
        {
            "meeting_id": row["meeting_id"],
            "request_payload_sha256": row["request_payload_sha256"],
            "truncated": row["truncated"],
            "returned_document_count": row["returned_document_count"],
            "stable_unique_projection_count": row["stable_unique_projection_count"],
            "stable_result_signature_sha256": row["stable_result_signature_sha256"],
        }
        for row in searches
    ])
    path = output / "council-minutes-date-search-measurement.json"
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(measurement["counts"], indent=2, sort_keys=True))

    if any_failure:
        return 2
    if any_truncation:
        return 3
    if control["returned_document_count"] < 1:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
