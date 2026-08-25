import hashlib
import json
from pathlib import Path

RECEIPT = Path("experiments/akron-2026/r1_t21_public_access_source_contract_summary.json")


def _canonical_sha(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_public_access_source_contract_receipt_is_bounded_and_non_terminal():
    p = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert p["schema"] == "proofline-akron-t21-public-access-source-contract-receipt/v1"
    assert p["stage"] == "frozen_public_access_source_contract_before_document_search"

    canonical = p["canonical_measurement"]
    assert canonical["workflow_run_id"] == 32801671813
    assert canonical["job_id"] == 97663617611
    assert canonical["head_sha"] == "a9e7458d9eed5ea85a37f3f916e436e77e87cd94"
    assert canonical["artifact_id"] == 9546702225
    assert canonical["artifact_digest"] == "sha256:fab36b8f5ef6a2ded9d75b3e7ec6fc4162ab9583842eb72f7792b0a697a087b9"

    declaration = p["publisher_declaration"]
    assert declaration["anchor_text"] == "Public Access Viewer."
    assert declaration["resolved_url"] == "https://onlinedocs.akronohio.gov/PublicAccess/recordsearch/cq/index.html"
    assert declaration["purpose"] == "Passed Legislation & Meeting Minutes"

    expected_assets = {
        "public-access-index.html": (1963, "ef0bfe36b0b63268f2a8e277bc67d55afc5d50c1f7d28199af7f044a70c3ee72"),
        "script-01.js": (3164248, "41f133a9398193679e218db53d050706c9fa1450d861e592865a03cd03430093"),
        "script-02.js": (796602, "a8eb480873ff4264388bc496108c4c07692c63d81125b1f4f023301fede5069a"),
        "obpa-config.json": (883, "ac69facdc096b762d5bf8c76f42c19336bfed9383f2673d1a77868c5258bcd2e"),
        "custom-queries.json": (1365, "b0a17406648dc959be7430c75a2479e5412dd15b23ca5bc434e87febda95baec"),
        "passed-legislation-keywords.json": (599, "ce1deeb6642a07df781e0f844691dd8f594294fbbee6e0a114cbdbf8a9886f9a"),
    }
    assert set(p["stable_source_assets"]) == set(expected_assets)
    for name, (size, sha) in expected_assets.items():
        assert p["stable_source_assets"][name] == {"byte_length": size, "sha256": sha}

    config = p["configuration"]
    assert config == {
        "api_url": "../../api",
        "api_root": "https://onlinedocs.akronohio.gov/PublicAccess/api",
        "api_root_basis": "source_declared_config",
        "query_limit": 0,
    }

    queries = p["custom_queries"]
    assert queries["count"] == 4
    assert queries["signature_sha256"] == "ad1a89062d3fb4acbda01be6a899fadeb2bad037eab862e58849c4cbda897c74"
    by_name = {row["name"]: row for row in queries["queries"]}
    assert by_name["Passed Legislation"]["id"] == "101"
    assert by_name["Council Meeting Minutes"]["id"] == "175"
    assert by_name["Committee Meeting Minutes"]["id"] == "202"

    passed = p["passed_legislation_query"]
    assert passed["id"] == "101"
    assert passed["name"] == "Passed Legislation"
    assert passed["type"] == "DocumentType"
    assert passed["date_search_option"] == "NoDate"
    assert passed["requires_date_or_keyword"] is True
    assert passed["requires_keyword"] is False
    assert passed["requires_date"] is False
    assert "Title Clause" in passed["instructions"]
    assert "asterisk" in passed["instructions"]
    assert passed["signature_sha256"] == "099bb8d717f7ca8afe59de0296b0bae5ef94d3d38b0c11a15f3b19e1616b8752"

    keywords = p["passed_legislation_keywords"]
    assert keywords["count"] == 3
    assert keywords["signature_sha256"] == "d4f4038d2021653b00eb83870406d4728c7ad0d22180535970d9c908dd234952"
    by_keyword = {row["name"]: row for row in keywords["keywords"]}
    assert by_keyword["Ordinance/Resolution Number"] == {
        "id": "102",
        "name": "Ordinance/Resolution Number",
        "data_type": "AlphaNumericSingleTable",
        "required": False,
        "max_length": 100,
    }
    assert by_keyword["Title Clause"] == {
        "id": "103",
        "name": "Title Clause",
        "data_type": "AlphaNumericSingleTable",
        "required": False,
        "max_length": 250,
    }
    assert by_keyword["Sponsor"]["id"] == "106"

    boundary = dict(p["authority_boundary"])
    signature = boundary.pop("signature_sha256")
    assert _canonical_sha(boundary) == signature
    assert signature == "d7601f2a1977dc45dfdc1747646d13fd9a948d4c90945889c64655849f67fb6e"
    assert boundary["document_search_submitted"] is False
    assert boundary["query_id_guessed"] is False
    assert boundary["document_token_enumerated"] is False
    assert boundary["terminal_outcome_assigned"] is False
    assert boundary["absence_treated_as_disposition"] is False
    assert boundary["detector_authorized"] is False
    assert boundary["lead_count"] is None

    interpretation = p["interpretation"]
    assert interpretation["eastwood_outcome_status"] == "Unknown"
    assert interpretation["source_contract_proven"] is True
    assert interpretation["passed_legislation_query_governed"] is True
    assert interpretation["document_search_performed"] is False
    assert p["receipt_guard"]["agenda_home_bytes_intentionally_not_pinned"] is True
