from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import urllib.request
from urllib.parse import urlparse

import fitz

from proofline.section38_notices import (
    classify_document,
    stable_json,
    validate_direct_url,
    validate_inputs,
    validate_positive_control_text,
)

EXPECTED_MEASUREMENT_SCHEMA = "proofline-akron-t21-section38-positive-search-measurement/v1"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_pdf(url: str, plan: dict) -> tuple[bytes, str, str]:
    validate_direct_url(url, plan)
    request = urllib.request.Request(url, headers={"User-Agent": "Proofline-T21/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        raw = response.read()
    validate_direct_url(final_url, plan)
    if content_type != plan["publisher_source"]["accepted_content_type"]:
        raise ValueError(f"unexpected Section 38 content type: {content_type!r}")
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Section 38 direct source did not return PDF bytes")
    return raw, final_url, content_type


def extract_pdf_text(raw: bytes) -> tuple[str, int]:
    document = fitz.open(stream=raw, filetype="pdf")
    try:
        pages = [page.get_text("text") for page in document]
        return "\n".join(pages), document.page_count
    finally:
        document.close()


def direct_document_receipt(url: str, plan: dict) -> dict:
    raw, final_url, content_type = fetch_pdf(url, plan)
    text, page_count = extract_pdf_text(raw)
    if not text.strip():
        raise ValueError("Section 38 direct source PDF has no extractable text layer")
    classification = classify_document(text, plan)
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "byte_length": len(raw),
        "sha256": sha256_bytes(raw),
        "page_count": page_count,
        "text_length": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "classification": classification,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("inventory_receipt")
    parser.add_argument("discovery_observation")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    plan_path = pathlib.Path(args.plan)
    inventory_path = pathlib.Path(args.inventory_receipt)
    discovery_path = pathlib.Path(args.discovery_observation)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = json.loads(plan_path.read_text())
    inventory = json.loads(inventory_path.read_text())
    discovery = json.loads(discovery_path.read_text())
    validate_inputs(plan, inventory, discovery)

    control_raw, control_final, control_content_type = fetch_pdf(plan["positive_control"]["url"], plan)
    control_text, control_page_count = extract_pdf_text(control_raw)
    validate_positive_control_text(control_text, plan)
    control_classification = classify_document(control_text, plan)
    positive_control = {
        "id": plan["positive_control"]["id"],
        "requested_url": plan["positive_control"]["url"],
        "final_url": control_final,
        "content_type": control_content_type,
        "byte_length": len(control_raw),
        "sha256": sha256_bytes(control_raw),
        "page_count": control_page_count,
        "text_length": len(control_text),
        "text_sha256": hashlib.sha256(control_text.encode("utf-8")).hexdigest(),
        "classification": control_classification,
        "excluded_from_target_population": True,
    }

    candidates = [
        direct_document_receipt(url, plan)
        for url in discovery.get("unique_candidate_urls", [])
    ]
    candidates.sort(key=lambda row: row["requested_url"])
    terminal_positive_candidates = [
        row for row in candidates if row["classification"]["terminal_positive"]
    ]

    if terminal_positive_candidates:
        outcome = {
            "status": "passed_by_council",
            "reason": "At least one directly retrieved official Council-hosted document satisfies the frozen Section 38 passage markers and Eastwood identity contract.",
        }
        next_stage = "Preserve the direct Section 38 passage source and separately govern any effective-date or implementation question; do not infer those semantics here."
    else:
        outcome = {
            "status": "unknown",
            "reason": "The frozen external discovery produced no directly retrieved Section 38 passage summary satisfying the Eastwood identity contract. Search-index nonfindings and notice-surface absence are non-terminal by design.",
        }
        next_stage = "Use the official Clerk public-record request path for the Eastwood ordinance disposition rather than expanding discovery terms or inferring non-passage."

    measurement = {
        "schema": EXPECTED_MEASUREMENT_SCHEMA,
        "source_receipts": {
            "plan": {
                "path": plan_path.name,
                "file_sha256": sha256_bytes(plan_path.read_bytes()),
                "pre_observation_commit": discovery["pre_observation_plan_commit"],
            },
            "inventory": {
                "path": inventory_path.name,
                "file_sha256": sha256_bytes(inventory_path.read_bytes()),
                "surface_population_signature_sha256": inventory["surface_population_signature_sha256"],
                "inventory_signature_sha256": inventory["inventory_signature_sha256"],
            },
            "discovery": {
                "path": discovery_path.name,
                "file_sha256": sha256_bytes(discovery_path.read_bytes()),
                "observed_at_utc": discovery["observed_at_utc"],
                "query_count": len(discovery["queries"]),
                "unique_candidate_url_count": len(discovery["unique_candidate_urls"]),
                "post_observation_query_expansion_performed": discovery["observation_boundary"]["post_observation_query_expansion_performed"],
            },
        },
        "positive_control": positive_control,
        "target_candidates": candidates,
        "counts": {
            "frozen_discovery_query_count": len(discovery["queries"]),
            "unique_discovered_candidate_count": len(candidates),
            "direct_candidate_retrieval_count": len(candidates),
            "target_identity_candidate_count": sum(bool(row["classification"]["identity_hits"]) for row in candidates),
            "section38_terminal_positive_candidate_count": len(terminal_positive_candidates),
        },
        "candidate_population_signature_sha256": hashlib.sha256(stable_json(candidates).encode("utf-8")).hexdigest(),
        "authority_boundary": {
            "external_discovery_is_non_authoritative": True,
            "search_engine_nonfinding_is_disposition_evidence": False,
            "direct_same_host_pdf_required_for_positive_outcome": True,
            "notice_absence_is_non_passage": False,
            "post_observation_query_expansion_performed": False,
            "approval_or_effective_date_inference_authorized": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": outcome,
        "next_stage": next_stage,
    }
    measurement["measurement_signature_sha256"] = hashlib.sha256(
        stable_json({
            "source_receipts": measurement["source_receipts"],
            "positive_control": positive_control,
            "target_candidates": candidates,
            "counts": measurement["counts"],
            "authority_boundary": measurement["authority_boundary"],
            "outcome": outcome,
            "next_stage": next_stage,
        }).encode("utf-8")
    ).hexdigest()

    output_path = output_dir / "section38-positive-search-measurement.json"
    output_path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "unique_discovered_candidate_count": measurement["counts"]["unique_discovered_candidate_count"],
        "section38_terminal_positive_candidate_count": measurement["counts"]["section38_terminal_positive_candidate_count"],
        "outcome": outcome["status"],
        "measurement_signature_sha256": measurement["measurement_signature_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
