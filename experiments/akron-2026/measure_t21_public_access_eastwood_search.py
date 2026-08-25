#!/usr/bin/env python3
"""Run the frozen Akron Public Access Eastwood candidate-search plan.

This stage submits only the two predeclared Passed Legislation Title Clause
queries. Returned document identifiers are preserved as retrieval candidates but
are not dereferenced and do not assign any terminal outcome.
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

SCHEMA = "proofline-akron-t21-public-access-eastwood-search-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-public-access-eastwood-search-plan/v1"
SOURCE_SCHEMA = "proofline-akron-t21-public-access-source-contract-receipt/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"
EXPECTED_REQUEST_IDS = (
    "title_clause_address_anchor",
    "title_clause_distinctive_use_anchor",
)
EXPECTED_VALUES = (
    "*1928*Eastwood*Avenue*",
    "*defense*education*training*facility*",
)


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def tokens_appear_in_order(pattern: str, source: str) -> bool:
    tokens = [token for token in pattern.casefold().split("*") if token]
    haystack = source.casefold()
    offset = 0
    for token in tokens:
        index = haystack.find(token, offset)
        if index < 0:
            return False
        offset = index + len(token)
    return True


def validate_inputs(plan: dict, source: dict, target: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected Eastwood search plan schema")
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected Public Access source-contract receipt schema")
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError("unexpected terminal-record target schema")

    contract = plan["source_contract"]
    frozen_query = source["passed_legislation_query"]
    frozen_keywords = source["passed_legislation_keywords"]["keywords"]
    title_keyword = next((row for row in frozen_keywords if row.get("id") == "103"), None)
    if contract != {
        "receipt_schema": SOURCE_SCHEMA,
        "api_root": source["configuration"]["api_root"],
        "query_id": frozen_query["id"],
        "query_name": frozen_query["name"],
        "keyword_id": "103",
        "keyword_name": "Title Clause",
        "keyword_data_type": title_keyword["data_type"] if title_keyword else None,
        "query_limit": source["configuration"]["query_limit"],
        "publisher_wildcard_instruction": True,
    }:
        raise ValueError("search plan does not exactly inherit the frozen Public Access contract")
    if frozen_query["id"] != "101" or frozen_query["name"] != "Passed Legislation":
        raise ValueError("frozen query is not publisher-issued Passed Legislation 101")
    if title_keyword is None or title_keyword["name"] != "Title Clause":
        raise ValueError("frozen Title Clause keyword 103 is unavailable")
    if "asterisk" not in frozen_query["instructions"].casefold():
        raise ValueError("publisher wildcard instruction is not present in frozen contract")

    frozen_title = target["ordinance_title"]
    if plan["target"]["ordinance_title"] != frozen_title:
        raise ValueError("search plan ordinance title diverged from frozen target")
    if plan["target"]["ordinance_title_sha256"] != target["ordinance_title_sha256"]:
        raise ValueError("search plan ordinance title hash diverged from frozen target")
    if plan["target"]["planning_case"] != target["planning_case"]["normalized_key"]:
        raise ValueError("search plan planning case diverged from frozen target")

    requests = plan.get("requests")
    if not isinstance(requests, list) or len(requests) != 2:
        raise ValueError("exactly two frozen requests are required")
    if tuple(row.get("request_id") for row in requests) != EXPECTED_REQUEST_IDS:
        raise ValueError("frozen request IDs changed")
    if tuple(row.get("keyword", {}).get("Value") for row in requests) != EXPECTED_VALUES:
        raise ValueError("frozen Eastwood Title Clause values changed")
    for row in requests:
        keyword = row["keyword"]
        if row.get("query_id") != 101 or row.get("QueryLimit") != 0:
            raise ValueError("request must use publisher query 101 with frozen QueryLimit 0")
        if keyword.get("ID") != 103 or keyword.get("Name") != "Title Clause":
            raise ValueError("request must use publisher Title Clause keyword 103")
        if keyword.get("KeywordOperator") != "=":
            raise ValueError("request keyword operator must remain '='")
        if len(keyword["Value"]) > int(title_keyword["max_length"]):
            raise ValueError("request exceeds publisher Title Clause maximum length")
        if not tokens_appear_in_order(keyword["Value"], frozen_title):
            raise ValueError("request tokens are not ordered anchors from the frozen title")

    selection = plan["selection_rule"]
    if selection.get("post_result_term_expansion_allowed") is not False:
        raise ValueError("post-result term expansion must remain forbidden")
    if selection.get("document_retrieval_in_this_stage") is not False:
        raise ValueError("document retrieval must remain out of scope for this stage")


def post_json(url: str, payload: dict, *, timeout: float = 45.0) -> tuple[dict, bytes]:
    body = stable_json(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "Proofline/0.1 public-record candidate-search measurement",
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


def parse_search_response(raw: bytes) -> tuple[dict, list[dict], bool]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("KeywordSearch response must be a JSON object")
    rows = payload.get("Data")
    if not isinstance(rows, list):
        raise ValueError("KeywordSearch response must contain a Data array")
    documents: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("KeywordSearch Data rows must be objects")
        doc_id = row.get("ID")
        if not isinstance(doc_id, (str, int)) or not str(doc_id).strip():
            raise ValueError("KeywordSearch document row lacks a stable returned ID")
        documents.append(
            {
                "id": str(doc_id),
                "name": row.get("Name"),
                "display_column_values": row.get("DisplayColumnValues"),
                "score": row.get("Score"),
                "summary": row.get("Summary"),
                "raw_row_sha256": sha256_json(row),
            }
        )
    return payload, documents, bool(payload.get("Truncated"))


def main() -> int:
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-public-access-eastwood-search")
    output.mkdir(parents=True, exist_ok=True)

    plan = load_json(root / "r1_t21_public_access_eastwood_search_plan.json")
    source = load_json(root / "r1_t21_public_access_source_contract_summary.json")
    target = load_json(root / "r1_t21_terminal_record_target.json")
    validate_inputs(plan, source, target)

    endpoint = source["configuration"]["api_root"].rstrip("/") + "/CustomQuery/KeywordSearch"
    if urlparse(endpoint).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("KeywordSearch endpoint escaped the frozen publisher host")

    searches: list[dict] = []
    union: dict[str, dict] = {}
    any_failure = False
    any_truncation = False

    for index, spec in enumerate(plan["requests"], start=1):
        request_payload = {
            "QueryID": spec["query_id"],
            "Keywords": [spec["keyword"]],
            "QueryLimit": spec["QueryLimit"],
        }
        response_record, raw = post_json(endpoint, request_payload)
        filename = f"search-{index:02d}-{spec['request_id']}.json"
        (output / filename).write_bytes(raw)
        response_record.update(
            {
                "byte_length": len(raw),
                "sha256": sha256_bytes(raw),
                "same_host": urlparse(response_record["requested_url"]).hostname
                == urlparse(response_record["final_url"]).hostname,
            }
        )
        documents: list[dict] = []
        truncated = False
        if response_record["ok"]:
            _, documents, truncated = parse_search_response(raw)
            for document in documents:
                previous = union.get(document["id"])
                if previous is not None and previous != document:
                    raise ValueError(
                        f"publisher document ID {document['id']} returned conflicting metadata across frozen searches"
                    )
                union[document["id"]] = document
        else:
            any_failure = True
        any_truncation = any_truncation or truncated
        searches.append(
            {
                "request_id": spec["request_id"],
                "request_payload": request_payload,
                "request_payload_sha256": sha256_json(request_payload),
                "response": response_record,
                "truncated": truncated,
                "returned_document_count": len(documents),
                "returned_documents": documents,
            }
        )

    candidates = [union[key] for key in sorted(union)]
    measurement = {
        "schema": SCHEMA,
        "stage": "publisher_passed_legislation_candidate_search_only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan": {
            "schema": plan["schema"],
            "sha256": sha256_json(plan),
            "request_ids": list(EXPECTED_REQUEST_IDS),
            "post_result_term_expansion_allowed": False,
        },
        "source_contract": {
            "schema": source["schema"],
            "query_id": source["passed_legislation_query"]["id"],
            "query_name": source["passed_legislation_query"]["name"],
            "keyword_id": "103",
            "keyword_name": "Title Clause",
            "api_root": source["configuration"]["api_root"],
            "query_limit": source["configuration"]["query_limit"],
        },
        "target": {
            "planning_case": target["planning_case"]["normalized_key"],
            "ordinance_title": target["ordinance_title"],
            "ordinance_title_sha256": target["ordinance_title_sha256"],
        },
        "endpoint": endpoint,
        "searches": searches,
        "candidate_population": {
            "deduplicate_by": "publisher_returned_document_id",
            "count": len(candidates),
            "documents": candidates,
            "signature_sha256": sha256_json(candidates),
        },
        "counts": {
            "frozen_request_count": len(searches),
            "successful_request_count": sum(1 for row in searches if row["response"]["ok"]),
            "truncated_request_count": sum(1 for row in searches if row["truncated"]),
            "unique_returned_document_count": len(candidates),
        },
        "authority_boundary": {
            "document_search_submitted": True,
            "only_predeclared_terms_used": True,
            "post_result_term_expansion_performed": False,
            "query_id_guessed": False,
            "keyword_id_guessed": False,
            "document_token_enumerated": False,
            "returned_document_dereferenced": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "This stage measures publisher-returned retrieval candidates only. Candidate presence or absence is not a terminal disposition.",
        },
        "non_claims": [
            "A zero candidate population does not establish denial, withdrawal, failure, non-passage, abandonment, or any terminal disposition.",
            "A returned Public Access document ID is a retrieval candidate only until the corresponding publisher document is separately acquired and evaluated.",
            "The two predeclared wildcard requests are bounded discovery measurements and are not represented as proof that no differently worded record exists."
        ],
    }
    measurement["response_population_signature_sha256"] = sha256_json(
        [
            {
                "request_id": row["request_id"],
                "request_payload_sha256": row["request_payload_sha256"],
                "response_sha256": row["response"]["sha256"],
                "truncated": row["truncated"],
                "returned_document_count": row["returned_document_count"],
            }
            for row in searches
        ]
    )
    path = output / "eastwood-search-measurement.json"
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(measurement["counts"], indent=2, sort_keys=True))

    if any_failure:
        return 2
    if any_truncation:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
