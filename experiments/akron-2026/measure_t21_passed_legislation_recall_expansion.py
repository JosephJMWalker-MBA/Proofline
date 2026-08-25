#!/usr/bin/env python3
"""Run the pre-frozen Akron Passed Legislation recall expansion for T21.

Four broad Title Clause queries are fixed in the committed plan before observation.
Opaque Public Access IDs are retained only as current retrieval handles; stable
candidate identity uses publisher-visible metadata. This stage never dereferences
returned documents or assigns legislative disposition.
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

SCHEMA = "proofline-akron-t21-passed-legislation-recall-expansion-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-passed-legislation-recall-expansion-plan/v1"
SOURCE_SCHEMA = "proofline-akron-t21-public-access-source-contract-receipt/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"
PRIOR_SCHEMA = "proofline-akron-t21-public-access-eastwood-search-receipt/v1"
MINUTES_SCHEMA = "proofline-akron-t21-council-minutes-content-audit-receipt/v1"
EXPECTED_REQUESTS = (
    ("title_clause_location_token", "*Eastwood*"),
    ("title_clause_street_number_token", "*1928*"),
    ("title_clause_use_pair", "*training*facility*"),
    ("title_clause_action_pair", "*conditional*use*"),
)


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


def ordered_tokens(pattern: str) -> list[str]:
    return [token for token in pattern.casefold().split("*") if token]


def tokens_appear_in_order(pattern: str, source: str) -> bool:
    offset = 0
    haystack = source.casefold()
    for token in ordered_tokens(pattern):
        index = haystack.find(token, offset)
        if index < 0:
            return False
        offset = index + len(token)
    return True


def validate_inputs(plan: dict, source: dict, target: dict, prior: dict, minutes: dict) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected recall-expansion plan schema")
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected Public Access source receipt schema")
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError("unexpected target schema")
    if prior.get("schema") != PRIOR_SCHEMA:
        raise ValueError("unexpected prior Passed Legislation search receipt schema")
    if minutes.get("schema") != MINUTES_SCHEMA:
        raise ValueError("unexpected minutes content-audit receipt schema")
    if prior["candidate_population"]["count"] != 0 or prior["outcome"]["status"] != "unknown":
        raise ValueError("recall expansion requires the frozen #98 zero-candidate non-terminal result")
    if minutes["counts"]["terminal_candidate_block_count"] != 0 or minutes["outcome"]["status"] != "unknown":
        raise ValueError("recall expansion requires the frozen #102 zero-terminal-candidate minutes result")

    frozen_query = source["passed_legislation_query"]
    keywords = {row["id"]: row for row in source["passed_legislation_keywords"]["keywords"]}
    contract = plan["source_contract"]
    if frozen_query["id"] != "101" or frozen_query["name"] != "Passed Legislation":
        raise ValueError("publisher Passed Legislation query 101 is not frozen")
    if contract["api_root"] != source["configuration"]["api_root"] or contract["query_id"] != 101:
        raise ValueError("plan diverged from frozen Public Access API/query")
    if contract["keyword_id"] != 103 or keywords["103"]["name"] != "Title Clause":
        raise ValueError("publisher Title Clause keyword 103 is unavailable")
    if contract["query_limit"] != source["configuration"]["query_limit"] != 0:
        raise ValueError("query limit changed")
    if "asterisk" not in frozen_query["instructions"].casefold():
        raise ValueError("publisher wildcard instruction is not frozen")

    frozen_title = target["ordinance_title"]
    if plan["target"]["ordinance_title"] != frozen_title:
        raise ValueError("plan title diverged from frozen target")
    if plan["target"]["ordinance_title_sha256"] != target["ordinance_title_sha256"]:
        raise ValueError("plan title hash diverged from frozen target")
    if plan["target"]["planning_case"] != target["planning_case"]["normalized_key"]:
        raise ValueError("plan case key diverged from frozen target")

    requests = plan.get("requests")
    actual = tuple((row.get("request_id"), row.get("keyword", {}).get("Value")) for row in requests or [])
    if actual != EXPECTED_REQUESTS:
        raise ValueError("recall expansion request vocabulary changed")
    for row in requests:
        keyword = row["keyword"]
        if row["query_id"] != 101 or row["QueryLimit"] != 0:
            raise ValueError("all expansion requests must use query 101 with QueryLimit 0")
        if keyword["ID"] != 103 or keyword["Name"] != "Title Clause" or keyword["KeywordOperator"] != "=":
            raise ValueError("all expansion requests must use Title Clause keyword 103 with '='")
        if not tokens_appear_in_order(keyword["Value"], frozen_title):
            raise ValueError("expansion tokens must be ordered tokens from the frozen title")
        if len(keyword["Value"]) > int(keywords["103"]["max_length"]):
            raise ValueError("expansion request exceeds publisher maximum length")

    selection = plan["selection_rule"]
    if selection["post_result_term_expansion_allowed"] is not False:
        raise ValueError("post-result expansion must remain forbidden")
    if selection["document_retrieval_in_this_stage"] is not False:
        raise ValueError("document retrieval must remain outside this stage")
    if selection["opaque_tokens_are_not_stable_identity"] is not True:
        raise ValueError("opaque token identity boundary changed")


def post_json(url: str, payload: dict, timeout: float = 45.0) -> tuple[dict, bytes]:
    body = stable_json(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={
        "User-Agent": "Proofline/0.1 Passed Legislation recall measurement",
        "Accept": "application/json,*/*;q=0.5",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(25_000_001)
            if len(raw) > 25_000_000:
                raise RuntimeError("response exceeded 25,000,000 bytes")
            return {"ok": True, "requested_url": url, "final_url": response.geturl(),
                    "status": getattr(response, "status", 200), "content_type": response.headers.get("Content-Type")}, raw
    except HTTPError as exc:
        return {"ok": False, "requested_url": url, "final_url": exc.geturl(), "status": exc.code,
                "content_type": exc.headers.get("Content-Type") if exc.headers else None,
                "error": f"HTTP {exc.code}: {exc.reason}"}, exc.read(1_000_000)
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {"ok": False, "requested_url": url, "final_url": url, "status": None,
                "content_type": None, "error": str(exc)}, b""


def stable_document_projection(row: dict) -> dict:
    return {"name": row.get("Name"), "display_column_values": row.get("DisplayColumnValues"),
            "score": row.get("Score"), "summary": row.get("Summary")}


def parse_response(raw: bytes) -> tuple[list[dict], bool, object]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), list):
        raise ValueError("KeywordSearch response must be an object with a Data array")
    documents = []
    for row in payload["Data"]:
        if not isinstance(row, dict):
            raise ValueError("KeywordSearch row must be an object")
        token = row.get("ID")
        if not isinstance(token, (str, int)) or not str(token).strip():
            raise ValueError("KeywordSearch row lacks an opaque document token")
        stable = stable_document_projection(row)
        documents.append({"document_token": str(token), "stable_projection": stable,
                          "stable_projection_sha256": sha256_json(stable), "raw_row_sha256": sha256_json(row)})
    return documents, bool(payload.get("Truncated")), payload.get("DisplayColumns")


def request_payload(spec: dict) -> dict:
    return {"QueryID": spec["query_id"], "Keywords": [spec["keyword"]], "QueryLimit": spec["QueryLimit"]}


def run_one(endpoint: str, spec: dict, output: Path) -> dict:
    payload = request_payload(spec)
    response, raw = post_json(endpoint, payload)
    filename = f"{spec.get('request_id', spec.get('control_id'))}.json"
    (output / filename).write_bytes(raw)
    response.update({"byte_length": len(raw), "sha256": sha256_bytes(raw),
                     "same_host": urlparse(response["requested_url"]).hostname == urlparse(response["final_url"]).hostname})
    documents, truncated, display_columns = ([], False, None)
    if response["ok"]:
        documents, truncated, display_columns = parse_response(raw)
    unique = {doc["stable_projection_sha256"]: doc["stable_projection"] for doc in documents}
    return {"request_payload": payload, "request_payload_sha256": sha256_json(payload), "response": response,
            "truncated": truncated, "returned_document_count": len(documents), "returned_documents": documents,
            "stable_unique_projection_count": len(unique),
            "stable_result_signature_sha256": sha256_json([unique[key] for key in sorted(unique)]),
            "display_columns": display_columns, "raw_filename": filename}


def screening_hits(projection: dict) -> list[str]:
    text = stable_json(projection).casefold()
    hits = []
    if "1928" in text and "eastwood" in text:
        hits.append("street_number_and_location")
    if all(token in text for token in ("defense", "education", "training", "facility")):
        hits.append("distinctive_use_tokens")
    if all(token in text for token in ("training", "facility", "eastwood")):
        hits.append("use_and_location")
    if all(token in text for token in ("conditional", "use", "eastwood")):
        hits.append("action_and_location")
    return hits


def group_candidates(searches: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for search in searches:
        for document in search["returned_documents"]:
            digest = document["stable_projection_sha256"]
            group = grouped.setdefault(digest, {
                "stable_projection": document["stable_projection"], "stable_projection_sha256": digest,
                "matched_request_ids": [], "observed_document_tokens": [], "observed_raw_row_sha256": []})
            group["matched_request_ids"].append(search["request_id"])
            group["observed_document_tokens"].append(document["document_token"])
            group["observed_raw_row_sha256"].append(document["raw_row_sha256"])
    result = []
    for digest in sorted(grouped):
        group = grouped[digest]
        group["matched_request_ids"] = sorted(set(group["matched_request_ids"]))
        group["observed_token_count"] = len(group["observed_document_tokens"])
        group["screening_hits"] = screening_hits(group["stable_projection"])
        group["target_screened"] = bool(group["screening_hits"])
        result.append(group)
    return result


def stable_group_projection(group: dict) -> dict:
    return {"stable_projection": group["stable_projection"], "stable_projection_sha256": group["stable_projection_sha256"],
            "matched_request_ids": group["matched_request_ids"], "screening_hits": group["screening_hits"],
            "target_screened": group["target_screened"]}


def main() -> int:
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-passed-legislation-recall-expansion")
    output.mkdir(parents=True, exist_ok=True)
    plan = load_json(root / "r1_t21_passed_legislation_recall_expansion_plan.json")
    source = load_json(root / "r1_t21_public_access_source_contract_summary.json")
    target = load_json(root / "r1_t21_terminal_record_target.json")
    prior = load_json(root / "r1_t21_public_access_eastwood_search_summary.json")
    minutes = load_json(root / "r1_t21_council_minutes_content_audit_summary.json")
    validate_inputs(plan, source, target, prior, minutes)

    endpoint = source["configuration"]["api_root"].rstrip("/") + "/CustomQuery/KeywordSearch"
    if urlparse(endpoint).hostname != "onlinedocs.akronohio.gov":
        raise ValueError("Passed Legislation endpoint escaped publisher host")

    control_spec = plan["positive_control"]
    control = run_one(endpoint, control_spec, output)
    control["control_id"] = control_spec["control_id"]
    control["excluded_from_candidate_population"] = True
    control["specific_known_record_returned"] = any(
        str(doc["stable_projection"].get("name") or "").startswith(control_spec["required_document_name_prefix"])
        for doc in control["returned_documents"])
    control["passed"] = (control["response"]["ok"] and control["response"]["same_host"] and
                         not control["truncated"] and control["specific_known_record_returned"])

    searches = []
    for spec in plan["requests"]:
        result = run_one(endpoint, spec, output)
        result["request_id"] = spec["request_id"]
        result["value"] = spec["keyword"]["Value"]
        searches.append(result)

    groups = group_candidates(searches)
    stable_groups = [stable_group_projection(group) for group in groups]
    screened = [row for row in stable_groups if row["target_screened"]]
    any_failure = (not control["passed"]) or any(not row["response"]["ok"] or not row["response"]["same_host"] for row in searches)
    any_truncation = control["truncated"] or any(row["truncated"] for row in searches)
    raw_handle_count = sum(row["returned_document_count"] for row in searches)

    measurement = {
        "schema": SCHEMA,
        "stage": "publisher_passed_legislation_predeclared_recall_expansion_only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan": {"schema": plan["schema"], "sha256": sha256_json(plan),
                 "request_ids": [row[0] for row in EXPECTED_REQUESTS], "post_result_term_expansion_allowed": False},
        "preconditions": {"prior_passed_legislation_candidate_count": prior["candidate_population"]["count"],
                          "minutes_terminal_candidate_block_count": minutes["counts"]["terminal_candidate_block_count"],
                          "prior_outcome_status": prior["outcome"]["status"], "minutes_outcome_status": minutes["outcome"]["status"]},
        "source_contract": {"schema": source["schema"], "api_root": source["configuration"]["api_root"],
                            "query_id": "101", "query_name": "Passed Legislation",
                            "title_clause_keyword_id": "103", "ordinance_number_keyword_id": "102", "query_limit": 0},
        "target": {"planning_case": target["planning_case"]["normalized_key"], "ordinance_title": target["ordinance_title"],
                   "ordinance_title_sha256": target["ordinance_title_sha256"]},
        "endpoint": endpoint,
        "positive_control": control,
        "searches": searches,
        "candidate_population": {
            "identity_boundary": "publisher-visible metadata projection; opaque tokens are current retrieval handles only",
            "raw_retrieval_handle_count": raw_handle_count,
            "stable_group_count": len(groups),
            "target_screened_group_count": len(screened),
            "groups": groups,
            "stable_population_signature_sha256": sha256_json(stable_groups),
            "target_screened_population_signature_sha256": sha256_json(screened),
        },
        "counts": {"request_count": len(searches), "successful_request_count": sum(1 for row in searches if row["response"]["ok"]),
                   "truncated_request_count": sum(1 for row in searches if row["truncated"]),
                   "returned_retrieval_handle_count": raw_handle_count, "stable_candidate_group_count": len(groups),
                   "target_screened_candidate_group_count": len(screened)},
        "authority_boundary": {"only_predeclared_expansion_terms_used": True, "post_result_term_expansion_performed": False,
                               "positive_control_excluded_from_candidate_population": True,
                               "opaque_document_token_treated_as_stable_identity": False,
                               "returned_document_dereferenced": False, "terminal_outcome_assigned": False,
                               "absence_treated_as_disposition": False, "causality_assigned": False,
                               "detector_authorized": False, "lead_count": None},
        "outcome": {"status": "unknown", "reason": "This stage broadens Passed Legislation candidate recall with four terms frozen before observation. Returned or absent candidates do not establish terminal disposition."},
    }
    path = output / "passed-legislation-recall-expansion.json"
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(measurement["counts"], indent=2, sort_keys=True))
    if any_failure:
        raise SystemExit("Passed Legislation recall expansion failed a source/control request")
    if any_truncation:
        raise SystemExit("Passed Legislation recall expansion returned truncated results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
