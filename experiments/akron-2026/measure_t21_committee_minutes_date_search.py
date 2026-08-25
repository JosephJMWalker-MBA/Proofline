#!/usr/bin/env python3
"""Measure pre-frozen Akron Committee Meeting Minutes searches for T21.

Twenty-two exact Eastwood chronology dates are submitted with the exact publisher
Committee value PLANNING & ECONOMIC DEVELOPMENT. A Year=2026 + Committee request
is a surface-health control only. Public Access opaque IDs are preserved only as
current retrieval handles; stable identity uses publisher-visible metadata. This
stage does not dereference documents or assign legislative disposition.
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

SCHEMA = "proofline-akron-t21-committee-minutes-date-search-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-committee-minutes-date-search-plan/v1"
SOURCE_SCHEMA = "proofline-akron-t21-committee-minutes-source-contract-receipt/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"
SEQUENCE_SCHEMA = "proofline-akron-t21-agenda-status-sequence-receipt/v1"
COMMITTEE_VALUE = "PLANNING & ECONOMIC DEVELOPMENT"


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
    return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")


def validate_inputs(plan: dict, source: dict, target: dict, sequence: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected Committee minutes date-search plan schema")
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected Committee minutes source receipt schema")
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError("unexpected target schema")
    if sequence.get("schema") != SEQUENCE_SCHEMA:
        raise ValueError("unexpected agenda-status sequence schema")

    contract = plan["source_contract"]
    query = source["source_contract"]["query"]
    if contract["api_root"] != source["source_contract"]["api_root"]:
        raise ValueError("API root diverged from frozen Committee minutes source contract")
    if contract["query_id"] != 202 or query["id"] != "202":
        raise ValueError("query ID must remain publisher-issued Committee Meeting Minutes 202")
    if contract["query_name"] != query["name"] or query["name"] != "Committee Meeting Minutes":
        raise ValueError("Committee Meeting Minutes query name diverged")
    if contract["query_limit"] != 0:
        raise ValueError("query limit changed")
    if contract["meeting_date_keyword"] != {
        "id": 124, "name": "Meeting Date", "data_type": "Date", "serialization": "MM/DD/YYYY"
    }:
        raise ValueError("Meeting Date contract changed")
    if contract["year_keyword"] != {"id": 532, "name": "Year", "data_type": "SmallNumeric"}:
        raise ValueError("Year contract changed")
    if contract["committee_keyword"] != {
        "id": 105,
        "name": "Committee",
        "data_type": "AlphaNumericSingleTable",
        "value": COMMITTEE_VALUE,
    }:
        raise ValueError("Committee contract changed")

    metadata = source["keyword_metadata"]
    if metadata["meeting_date"] != {"data_type": "Date", "dataset_is_null": True, "max_length": 27}:
        raise ValueError("frozen Meeting Date metadata changed")
    if metadata["year"]["data_type"] != "SmallNumeric" or metadata["year"]["contains_2026"] is not True:
        raise ValueError("frozen Year metadata no longer establishes 2026")
    committee = metadata["committee"]
    if committee["data_type"] != "AlphaNumericSingleTable":
        raise ValueError("frozen Committee data type changed")
    if committee["planning_economic_development_value"] != COMMITTEE_VALUE:
        raise ValueError("publisher Planning & Economic Development value changed")
    if committee["contains_planning_economic_development"] is not True:
        raise ValueError("publisher Committee dataset no longer contains target committee value")

    control = plan["positive_control"]
    expected_control_keywords = [
        {"ID": 532, "Name": "Year", "Value": "2026", "KeywordOperator": "="},
        {"ID": 105, "Name": "Committee", "Value": COMMITTEE_VALUE, "KeywordOperator": "="},
    ]
    if control["request_id"] != "year_2026_planning_economic_development_control":
        raise ValueError("positive-control ID changed")
    if control["query_id"] != 202 or control["QueryLimit"] != 0:
        raise ValueError("positive control must use query 202 / QueryLimit 0")
    if control["keywords"] != expected_control_keywords:
        raise ValueError("positive-control keywords changed")
    if control["included_in_eastwood_population"] is not False:
        raise ValueError("positive control must be excluded from Eastwood population")

    expected_ids = target["provenance"]["publisher_meeting_ids_with_exact_title"]
    requests = plan.get("eastwood_requests")
    if not isinstance(requests, list) or [row.get("meeting_id") for row in requests] != expected_ids:
        raise ValueError("Committee minutes population must exactly equal frozen exact-title meeting IDs")
    if len(requests) != 22 or len(set(expected_ids)) != 22:
        raise ValueError("expected 22 unique exact-title meeting IDs")

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
    if selection["opaque_tokens_are_not_stable_identity"] is not True:
        raise ValueError("opaque token identity boundary changed")
    if selection["committee_value_is_exact_publisher_dataset_value"] is not True:
        raise ValueError("committee-value provenance boundary changed")


def post_json(url: str, payload: dict, timeout: float = 45.0) -> tuple[dict, bytes]:
    body = stable_json(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "Proofline/0.1 Committee minutes candidate-search measurement",
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
            raise ValueError("returned Committee minutes row lacks publisher document token")
        stable = stable_document_projection(row)
        documents.append({
            "document_token": str(token),
            "stable_projection": stable,
            "stable_projection_sha256": sha256_json(stable),
            "raw_row_sha256": sha256_json(row),
        })
    return documents, bool(payload.get("Truncated")), payload.get("DisplayColumns")


def request_payload(query_id: int, keywords: list[dict], query_limit: int) -> dict:
    return {"QueryID": query_id, "Keywords": keywords, "QueryLimit": query_limit}


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
    stable_by_digest: dict[str, dict] = {}
    for document in documents:
        stable_by_digest.setdefault(document["stable_projection_sha256"], document["stable_projection"])
    stable_unique = [stable_by_digest[key] for key in sorted(stable_by_digest)]
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


def response_population_projection(searches: list[dict]) -> list[dict]:
    return [
        {
            "meeting_id": row["meeting_id"],
            "meeting_date": row["meeting_date"],
            "request_payload_sha256": row["request_payload_sha256"],
            "returned_document_count": row["returned_document_count"],
            "stable_unique_projection_count": row["stable_unique_projection_count"],
            "stable_result_signature_sha256": row["stable_result_signature_sha256"],
            "truncated": row["truncated"],
        }
        for row in searches
    ]


def main() -> int:
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-committee-minutes-date-search")
    output.mkdir(parents=True, exist_ok=True)

    plan = load_json(root / "r1_t21_committee_minutes_date_search_plan.json")
    source = load_json(root / "r1_t21_committee_minutes_source_contract_summary.json")
    target = load_json(root / "r1_t21_terminal_record_target.json")
    sequence = load_json(root / "r1_t21_agenda_status_sequence_summary.json")
    validate_inputs(plan, source, target, sequence)

    endpoint = source["source_contract"]["api_root"].rstrip("/") + "/CustomQuery/KeywordSearch"
    if urlparse(endpoint).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("Committee minutes search endpoint escaped publisher host")

    control_spec = plan["positive_control"]
    control = run_one(
        endpoint,
        control_spec["request_id"],
        request_payload(control_spec["query_id"], control_spec["keywords"], control_spec["QueryLimit"]),
        output,
    )
    control["excluded_from_eastwood_population"] = True
    control["passed"] = bool(
        control["response"]["ok"]
        and control["response"]["same_host"]
        and not control["truncated"]
        and control["returned_document_count"] > 0
    )

    searches = []
    for spec in plan["eastwood_requests"]:
        keywords = [
            {"ID": 124, "Name": "Meeting Date", "Value": spec["keyword_value"], "KeywordOperator": "="},
            {"ID": 105, "Name": "Committee", "Value": COMMITTEE_VALUE, "KeywordOperator": "="},
        ]
        result = run_one(endpoint, spec["request_id"], request_payload(202, keywords, 0), output)
        result["meeting_id"] = spec["meeting_id"]
        result["meeting_date"] = spec["meeting_date"]
        searches.append(result)

    any_failure = (not control["response"]["ok"]) or any(not row["response"]["ok"] for row in searches)
    wrong_host = (not control["response"]["same_host"]) or any(not row["response"]["same_host"] for row in searches)
    any_truncation = control["truncated"] or any(row["truncated"] for row in searches)

    groups = group_stable_candidates(searches)
    stable_signature_rows = stable_group_signature_projection(groups)
    response_rows = response_population_projection(searches)
    raw_token_count = sum(row["returned_document_count"] for row in searches)
    duplicate_groups = sum(1 for group in groups if group["observed_token_count"] > 1)
    with_results = sum(1 for row in searches if row["returned_document_count"] > 0)

    measurement = {
        "schema": SCHEMA,
        "stage": "publisher_committee_minutes_exact_date_and_committee_candidate_search_only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan": {
            "schema": plan["schema"],
            "sha256": sha256_json(plan),
            "eastwood_request_count": len(plan["eastwood_requests"]),
            "committee_value": COMMITTEE_VALUE,
            "post_result_expansion_allowed": False,
        },
        "source_contract": {
            "schema": source["schema"],
            "api_root": source["source_contract"]["api_root"],
            "query_id": "202",
            "query_name": "Committee Meeting Minutes",
            "meeting_date_keyword_id": "124",
            "year_keyword_id": "532",
            "committee_keyword_id": "105",
            "committee_value": COMMITTEE_VALUE,
            "query_limit": 0,
        },
        "endpoint": endpoint,
        "positive_control": control,
        "eastwood_searches": searches,
        "candidate_population": {
            "identity_boundary": "meeting_id_plus_publisher_stable_projection; opaque tokens preserved only as observed retrieval handles",
            "stable_group_count": len(groups),
            "raw_retrieval_token_count": raw_token_count,
            "duplicate_metadata_group_count": duplicate_groups,
            "groups": groups,
            "stable_population_signature_sha256": sha256_json(stable_signature_rows),
            "response_population_signature_sha256": sha256_json(response_rows),
        },
        "counts": {
            "positive_control_returned_document_count": control["returned_document_count"],
            "eastwood_request_count": len(searches),
            "successful_eastwood_request_count": sum(1 for row in searches if row["response"]["ok"] and row["response"]["same_host"]),
            "truncated_eastwood_request_count": sum(1 for row in searches if row["truncated"]),
            "eastwood_dates_with_results": with_results,
            "eastwood_dates_without_results": len(searches) - with_results,
            "eastwood_returned_document_token_count": raw_token_count,
            "eastwood_stable_metadata_group_count": len(groups),
            "eastwood_duplicate_metadata_group_count": duplicate_groups,
        },
        "authority_boundary": {
            "document_search_submitted": True,
            "positive_control_submitted": True,
            "positive_control_excluded_from_eastwood_population": True,
            "only_predeclared_dates_used": True,
            "exact_publisher_committee_value_used": True,
            "post_result_expansion_performed": False,
            "query_id_guessed": False,
            "keyword_id_guessed": False,
            "committee_value_guessed": False,
            "opaque_document_token_treated_as_stable_identity": False,
            "returned_document_dereferenced": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "This stage measures publisher-returned Committee Meeting Minutes retrieval candidates for predeclared Eastwood dates and the exact publisher Planning & Economic Development committee value only. Presence or absence is not disposition.",
        },
    }
    measurement_path = output / "committee-minutes-date-search.json"
    measurement_path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "control_count": control["returned_document_count"],
        "control_passed": control["passed"],
        "eastwood_dates_with_results": with_results,
        "eastwood_dates_without_results": len(searches) - with_results,
        "eastwood_retrieval_handles": raw_token_count,
        "eastwood_stable_groups": len(groups),
        "eastwood_duplicate_groups": duplicate_groups,
        "stable_population_signature_sha256": measurement["candidate_population"]["stable_population_signature_sha256"],
    }, indent=2, sort_keys=True))

    if any_failure or wrong_host or any_truncation or not control["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
