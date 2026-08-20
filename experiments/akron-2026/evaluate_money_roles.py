#!/usr/bin/env python3
"""Evaluate the frozen Akron money-role contract on an exact disjoint attachment set.

The contract is semantic-role only. It emits no anomaly, conflict, suspiciousness,
recurrence, or investigative-lead judgment. Unclassified money and zero money facts are
valid outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from proofline.hashing import source_id_from_uri
from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.storage import ProoflineStore
from proofline.structured import StructuredIndex
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-money-role-oos-evaluation/v1"
CONTRACT_SCHEMA = "proofline-akron-money-role-contract/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-frozen-attachment-sync/v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_contract(contract: dict) -> None:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("unexpected money-role contract schema")
    if contract.get("detector_authorized") is not False:
        raise ValueError("role contract may not authorize a detector")
    if contract.get("parser_version") != "proofline-structured/v2":
        raise ValueError("T11 role contract must require structured parser v2")
    roles = contract.get("roles") or []
    default_role = contract.get("default_role")
    if default_role not in roles or default_role != "unclassified_money":
        raise ValueError("role contract must retain unclassified_money as its default")
    if int(contract.get("context_radius_chars") or 0) < 1:
        raise ValueError("contract context radius must be positive")
    if int(contract.get("left_context_chars") or 0) < 1:
        raise ValueError("contract left-context size must be positive")

    seen = set()
    for rule in contract.get("rules") or []:
        rule_id = rule.get("rule_id")
        role = rule.get("role")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
            raise ValueError("role contract contains an invalid or duplicate rule_id")
        seen.add(rule_id)
        if role not in roles or role == default_role:
            raise ValueError(f"rule {rule_id} has an invalid role")
        if rule.get("left_regex"):
            re.compile(rule["left_regex"])
        for key in ("context_all", "context_any", "context_none", "numeric_in"):
            value = rule.get(key)
            if value is not None and not isinstance(value, list):
                raise ValueError(f"rule {rule_id} field {key} must be a list")


def classify_money_role(
    contract: dict,
    *,
    page_text: str,
    char_start: int,
    char_end: int,
    raw_text: str,
    normalized_text: str,
) -> dict:
    validate_contract(contract)
    if char_start < 0 or char_end <= char_start or char_end > len(page_text):
        raise ValueError("money fact has an invalid source character range")
    if page_text[char_start:char_end] != raw_text:
        raise ValueError("money fact token no longer matches its preferred Silver anchor")

    radius = int(contract["context_radius_chars"])
    left_size = int(contract["left_context_chars"])
    context_start = max(0, char_start - radius)
    context_end = min(len(page_text), char_end + radius)
    left_start = max(0, char_start - left_size)
    context_text = page_text[context_start:context_end]
    left_text = page_text[left_start:char_start]
    normalized_context = _normalize(context_text)
    normalized_left = _normalize(left_text)

    matched = None
    for rule in contract.get("rules") or []:
        if any(term.casefold() not in normalized_context for term in rule.get("context_all") or []):
            continue
        context_any = [term.casefold() for term in rule.get("context_any") or []]
        if context_any and not any(term in normalized_context for term in context_any):
            continue
        if any(term.casefold() in normalized_context for term in rule.get("context_none") or []):
            continue
        numeric_in = rule.get("numeric_in") or []
        if numeric_in and normalized_text not in numeric_in:
            continue
        left_regex = rule.get("left_regex")
        if left_regex and re.search(left_regex, normalized_left) is None:
            continue
        matched = rule
        break

    role = matched["role"] if matched else contract["default_role"]
    return {
        "role": role,
        "rule_id": matched["rule_id"] if matched else None,
        "context_start": context_start,
        "context_end": context_end,
        "context_text": context_text,
        "context_sha256": _sha256_text(context_text),
        "context_normalized_sha256": _sha256_text(normalized_context),
    }


def _artifact_metadata(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT artifact_id, sha256, media_type, byte_size, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"missing attachment artifact: {artifact_id}")
    return dict(row)


def _page_profile(store: ProoflineStore, artifact_id: str, *, threshold: float) -> dict:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT eu.evidence_id, eu.locator, best.method, best.extracted_text,
                   best.quality_score, best.software_version, best.model_version
            FROM evidence_units eu
            JOIN evidence_extractions best
              ON best.extraction_id = (
                SELECT ee.extraction_id
                FROM evidence_extractions ee
                WHERE ee.evidence_id = eu.evidence_id
                ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                         ee.occurred_at DESC,
                         ee.rowid DESC
                LIMIT 1
              )
            WHERE eu.artifact_id = ? AND eu.unit_type = 'page'
            ORDER BY CAST(SUBSTR(eu.locator, 6) AS INTEGER), eu.evidence_id
            """,
            (artifact_id,),
        ).fetchall()
    pages = []
    for row in rows:
        text = row["extracted_text"] or ""
        quality = float(row["quality_score"] or 0.0)
        pages.append(
            {
                "evidence_id": row["evidence_id"],
                "locator": row["locator"],
                "method": row["method"],
                "quality_score": quality,
                "nonblank": bool(text.strip()),
                "meets_quality_floor": quality >= threshold,
                "software_version": row["software_version"],
                "model_version": row["model_version"],
            }
        )
    return {
        "page_count": len(pages),
        "nonblank_page_count": sum(page["nonblank"] for page in pages),
        "low_quality_page_count": sum(not page["meets_quality_floor"] for page in pages),
        "pages": pages,
    }


def _preferred_extraction(store: ProoflineStore, evidence_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT method, extracted_text, quality_score, software_version, model_version
            FROM evidence_extractions
            WHERE evidence_id = ?
            ORDER BY COALESCE(quality_score, -1.0) DESC, occurred_at DESC, rowid DESC
            LIMIT 1
            """,
            (evidence_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"evidence unit has no extraction: {evidence_id}")
    return dict(row)


def _tesseract_version() -> str | None:
    try:
        completed = subprocess.run(
            ["tesseract", "--version"], check=True, capture_output=True, text=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    lines = (completed.stdout or completed.stderr).splitlines()
    return lines[0].strip() if lines else None


def evaluate(
    state_dir: Path,
    *,
    selection_sync: dict,
    contract: dict,
    threshold: float,
    run_ocr: bool,
    language: str,
    dpi: int,
) -> dict:
    validate_contract(contract)
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected frozen attachment sync schema")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != 24:
        raise ValueError("T11 requires exactly 24 frozen disjoint attachment sources")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type="supporting_document_of")
    relations_by_source: dict[str, list] = defaultdict(list)
    for relation in relations:
        relations_by_source[relation.source_uri].append(relation)

    attachments = []
    source_by_artifact: dict[str, str] = {}
    for selected in selected_sources:
        source_uri = selected["source_uri"]
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"selected source has no successful artifact: {source_uri}")
        metadata = _artifact_metadata(store, artifact_id)
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"selected attachment is not PDF: {source_uri}")
        if not relations_by_source.get(source_uri):
            raise RuntimeError(f"selected attachment has no publisher-backed relation: {source_uri}")
        source_by_artifact[artifact_id] = source_uri
        attachments.append(
            {
                "source_uri": source_uri,
                "source_uri_sha256": selected["source_uri_sha256"],
                "source_name": selected.get("source_name"),
                "artifact": metadata,
                "native": _page_profile(store, artifact_id, threshold=threshold),
                "relations": [
                    {
                        "parent_source_uri": relation.related_source_uri,
                        "parent_evidence_artifact_id": relation.evidence_artifact_id,
                        "details": relation.details,
                    }
                    for relation in relations_by_source[source_uri]
                ],
            }
        )

    tesseract_version = _tesseract_version()
    ocr_results = {}
    if run_ocr:
        if tesseract_version is None:
            raise RuntimeError("Tesseract is unavailable; cannot run requested T11 OCR")
        extractor = ProgressiveExtractor(state_dir)
        backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
        for item in attachments:
            if item["native"]["low_quality_page_count"] == 0:
                continue
            artifact_id = item["artifact"]["artifact_id"]
            result = extractor.run_ocr(artifact_id, backend, threshold=threshold, force=False)
            ocr_results[artifact_id] = result.to_dict()

    structured = StructuredIndex(state_dir)
    build = structured.rebuild()
    if build.parser_version != contract["parser_version"]:
        raise RuntimeError(
            f"T11 structured parser mismatch: {build.parser_version} != {contract['parser_version']}"
        )

    artifact_ids = [item["artifact"]["artifact_id"] for item in attachments]
    placeholders = ",".join("?" for _ in artifact_ids)
    with store.connection() as connection:
        rows = connection.execute(
            f"""
            SELECT fact_id, evidence_id, artifact_id, locator, raw_text, normalized_text,
                   numeric_value, unit, char_start, char_end
            FROM evidence_facts
            WHERE build_id = ? AND fact_type = 'money' AND artifact_id IN ({placeholders})
            ORDER BY artifact_id, locator, char_start, fact_id
            """,
            [build.build_id, *artifact_ids],
        ).fetchall()

    facts = []
    role_counts = Counter()
    source_role_counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        extraction = _preferred_extraction(store, row["evidence_id"])
        page_text = extraction["extracted_text"] or ""
        if row["char_start"] is None or row["char_end"] is None:
            raise RuntimeError("free-form money fact lost its source character anchors")
        classified = classify_money_role(
            contract,
            page_text=page_text,
            char_start=int(row["char_start"]),
            char_end=int(row["char_end"]),
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
        )
        source_uri = source_by_artifact[row["artifact_id"]]
        role_counts[classified["role"]] += 1
        source_role_counts[source_uri][classified["role"]] += 1
        facts.append(
            {
                "fact_id": row["fact_id"],
                "evidence_id": row["evidence_id"],
                "source_uri": source_uri,
                "artifact_id": row["artifact_id"],
                "locator": row["locator"],
                "raw_text": row["raw_text"],
                "normalized_text": row["normalized_text"],
                "numeric_value": row["numeric_value"],
                "unit": row["unit"],
                "char_start": row["char_start"],
                "char_end": row["char_end"],
                "role": classified["role"],
                "rule_id": classified["rule_id"],
                "context_start": classified["context_start"],
                "context_end": classified["context_end"],
                "context_text": classified["context_text"],
                "context_sha256": classified["context_sha256"],
                "context_normalized_sha256": classified["context_normalized_sha256"],
                "page_text_sha256": _sha256_text(page_text),
                "extraction_method": extraction["method"],
                "quality_score": extraction["quality_score"],
                "software_version": extraction["software_version"],
                "model_version": extraction["model_version"],
            }
        )

    for item in attachments:
        artifact_id = item["artifact"]["artifact_id"]
        item["ocr"] = ocr_results.get(artifact_id)
        item["post_ocr"] = _page_profile(store, artifact_id, threshold=threshold)
        item["role_counts"] = dict(sorted(source_role_counts[item["source_uri"]].items()))

    ocr_attempted = sum(result["attempted"] for result in ocr_results.values())
    ocr_added = sum(result["added"] for result in ocr_results.values())
    ocr_failed = sum(result["failed"] for result in ocr_results.values())
    failures = [failure for result in ocr_results.values() for failure in result["failures"]]
    total_pages = sum(item["post_ocr"]["page_count"] for item in attachments)
    low_pages = sum(item["post_ocr"]["low_quality_page_count"] for item in attachments)
    default_role = contract["default_role"]
    unclassified = role_counts.get(default_role, 0)

    return {
        "schema": SCHEMA,
        "stage": "out_of_sample_role_evaluation_only",
        "semantic_roles_assigned": True,
        "detector_authorized": False,
        "lead_count": None,
        "contract": {
            "contract_id": contract["contract_id"],
            "schema": contract["schema"],
            "parser_version": contract["parser_version"],
            "default_role": default_role,
            "rule_ids": [rule["rule_id"] for rule in contract["rules"]],
        },
        "sample": {
            "attachment_count": len(attachments),
            "selected_source_hashes": selection_sync["selection"]["selected_source_hashes"],
            "selected_signature_sha256": selection_sync["selection"]["selected_signature_sha256"],
            "excluded_source_hashes": selection_sync["selection"]["excluded_source_hashes"],
            "excluded_signature_sha256": selection_sync["selection"]["excluded_signature_sha256"],
            "selection_note": (
                "The 24 evaluation sources were frozen from source identity only before document content "
                "was evaluated and explicitly exclude the eight T8 derivation sources."
            ),
        },
        "extraction": {
            "quality_threshold": threshold,
            "page_count": total_pages,
            "post_ocr_low_quality_page_count": low_pages,
            "ocr_requested": run_ocr,
            "ocr_documents_attempted": len(ocr_results),
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
            "ocr_failures": failures,
            "tesseract_version": tesseract_version,
        },
        "structured_build": build.to_dict(),
        "money_fact_count": len(facts),
        "classified_fact_count": len(facts) - unclassified,
        "unclassified_fact_count": unclassified,
        "role_counts": dict(sorted(role_counts.items())),
        "facts": facts,
        "attachments": attachments,
        "non_claims": contract.get("non_claims") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--selection-sync", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--language", default="eng")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()
    if not 0.0 <= args.threshold <= 1.0:
        raise SystemExit("--threshold must be between 0 and 1")
    if args.dpi < 72:
        raise SystemExit("--dpi must be at least 72")

    profile = evaluate(
        Path(args.state_dir),
        selection_sync=_load(args.selection_sync),
        contract=_load(args.contract),
        threshold=args.threshold,
        run_ocr=args.ocr,
        language=args.language,
        dpi=args.dpi,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
