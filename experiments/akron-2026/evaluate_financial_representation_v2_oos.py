#!/usr/bin/env python3
"""Blindly evaluate frozen Akron financial-representation v2 on corrected R1.T13b.

T13b is representation evaluation only. The frozen v2 contract may describe context facets,
but this stage never assigns transaction identity, event independence, anomaly, conflict,
suspiciousness, wrongdoing, or investigative leads. Unknown and null outcomes are valid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from financial_representation_v2 import load_contract, represent_money_fact, validate_contract
from proofline.hashing import source_id_from_uri
from proofline.ocr import PyMuPDFTesseractBackend
from proofline.progressive import ProgressiveExtractor
from proofline.relations import RelationStore
from proofline.storage import ProoflineStore
from proofline.structured import StructuredIndex
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-financial-representation-v2-oos-evaluation/v1"
SELECTION_SYNC_SCHEMA = "proofline-akron-t13b-frozen-attachment-sync/v1"
EXPECTED_SOURCES = 32


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


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


def _source_name_context(source_records: list[dict]) -> tuple[str, str, list[str]]:
    """Choose publisher-name context conservatively for one deduplicated artifact.

    If all nonblank selected-source names normalize to the same value, one deterministic
    spelling may be used. If names diverge, omit source-name context rather than choosing an
    arbitrary publisher identity. All original names remain in provenance.
    """

    original_names = sorted(
        {str(item.get("source_name") or "").strip() for item in source_records if str(item.get("source_name") or "").strip()}
    )
    by_normalized: dict[str, list[str]] = defaultdict(list)
    for name in original_names:
        by_normalized[_normalize(name)].append(name)

    if not by_normalized:
        return "", "absent", []
    if len(by_normalized) == 1:
        deterministic = sorted(next(iter(by_normalized.values())))[0]
        return deterministic, "shared_nonblank", original_names
    return "", "divergent_omitted", original_names


def evaluate(
    state_dir: Path,
    *,
    selection_sync: dict,
    contract_path: Path,
    threshold: float,
    run_ocr: bool,
    language: str,
    dpi: int,
) -> dict:
    contract = load_contract(contract_path)
    validate_contract(contract)
    if selection_sync.get("schema") != SELECTION_SYNC_SCHEMA:
        raise ValueError("unexpected T13b frozen attachment sync schema")
    selected_sources = selection_sync.get("selected_sources") or []
    if len(selected_sources) != EXPECTED_SOURCES:
        raise ValueError("T13b requires exactly 32 corrected disjoint attachment sources")

    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    relations = RelationStore(state_dir).list(relation_type="supporting_document_of")
    relations_by_source: dict[str, list] = defaultdict(list)
    for relation in relations:
        relations_by_source[relation.source_uri].append(relation)

    attachments = []
    sources_by_artifact: dict[str, list[dict]] = defaultdict(list)
    artifact_profiles: dict[str, dict] = {}
    for selected in selected_sources:
        source_uri = selected["source_uri"]
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"T13b selected source has no successful artifact: {source_uri}")
        metadata = _artifact_metadata(store, artifact_id)
        if metadata["media_type"] != "application/pdf":
            raise RuntimeError(f"T13b selected attachment is not PDF: {source_uri}")
        if not relations_by_source.get(source_uri):
            raise RuntimeError(f"T13b selected attachment has no publisher-backed relation: {source_uri}")

        native = artifact_profiles.get(artifact_id)
        if native is None:
            native = _page_profile(store, artifact_id, threshold=threshold)
            artifact_profiles[artifact_id] = native

        source_record = {
            "source_uri": source_uri,
            "source_uri_sha256": selected["source_uri_sha256"],
            "source_name": selected.get("source_name"),
        }
        sources_by_artifact[artifact_id].append(source_record)
        attachments.append(
            {
                **source_record,
                "artifact": metadata,
                "native": native,
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

    for artifact_id in sources_by_artifact:
        sources_by_artifact[artifact_id].sort(key=lambda item: item["source_uri"])

    tesseract_version = _tesseract_version()
    ocr_results = {}
    if run_ocr:
        if tesseract_version is None:
            raise RuntimeError("Tesseract is unavailable; cannot run requested T13b OCR")
        extractor = ProgressiveExtractor(state_dir)
        backend = PyMuPDFTesseractBackend(language=language, dpi=dpi)
        for artifact_id in sorted(sources_by_artifact):
            native = artifact_profiles[artifact_id]
            if native["low_quality_page_count"] == 0:
                continue
            result = extractor.run_ocr(artifact_id, backend, threshold=threshold, force=False)
            ocr_results[artifact_id] = result.to_dict()

    structured = StructuredIndex(state_dir)
    build = structured.rebuild()
    if build.parser_version != contract["parser_version"]:
        raise RuntimeError(
            f"T13b structured parser mismatch: {build.parser_version} != {contract['parser_version']}"
        )

    artifact_ids = sorted(sources_by_artifact)
    placeholders = ",".join("?" for _ in artifact_ids)
    if artifact_ids:
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
    else:
        rows = []

    facts = []
    scope_counts = Counter()
    context_counts = Counter()
    amount_counts = Counter()
    source_name_status_counts = Counter()

    for row in rows:
        extraction = _preferred_extraction(store, row["evidence_id"])
        page_text = extraction["extracted_text"] or ""
        if row["char_start"] is None or row["char_end"] is None:
            raise RuntimeError("T13b free-form money fact lost its source character anchors")

        source_records = sources_by_artifact[row["artifact_id"]]
        representation_source_name, name_status, original_source_names = _source_name_context(source_records)
        represented = represent_money_fact(
            contract,
            page_text=page_text,
            char_start=int(row["char_start"]),
            char_end=int(row["char_end"]),
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            source_name=representation_source_name,
        )
        context_text = page_text[represented["context_start"] : represented["context_end"]]
        if _sha256_text(context_text) != represented["context_sha256"]:
            raise RuntimeError("T13b representation context hash is inconsistent")

        source_uris = [item["source_uri"] for item in source_records]
        source_uri_hashes = [item["source_uri_sha256"] for item in source_records]
        scope_counts[represented["scope"]] += 1
        context_counts[represented["context_type"]] += 1
        amount_counts[represented["amount_type"]] += 1
        source_name_status_counts[name_status] += 1

        facts.append(
            {
                "fact_id": row["fact_id"],
                "evidence_id": row["evidence_id"],
                "source_uris": source_uris,
                "source_uri_sha256s": source_uri_hashes,
                "source_names": original_source_names,
                "artifact_id": row["artifact_id"],
                "locator": row["locator"],
                "raw_text": row["raw_text"],
                "normalized_text": row["normalized_text"],
                "numeric_value": row["numeric_value"],
                "unit": row["unit"],
                "char_start": row["char_start"],
                "char_end": row["char_end"],
                "scope": represented["scope"],
                "context_type": represented["context_type"],
                "amount_type": represented["amount_type"],
                "context_rule_id": represented["context_rule_id"],
                "amount_rule_id": represented["amount_rule_id"],
                "context_start": represented["context_start"],
                "context_end": represented["context_end"],
                "context_text": context_text,
                "context_sha256": represented["context_sha256"],
                "page_text_sha256": represented["page_text_sha256"],
                "representation_source_name_status": name_status,
                "representation_source_name_sha256": represented["source_name_sha256"],
                "detector_authorized": represented["detector_authorized"],
                "event_identity_assigned": represented["event_identity_assigned"],
                "independence_assessed": represented["independence_assessed"],
                "extraction_method": extraction["method"],
                "quality_score": extraction["quality_score"],
                "software_version": extraction["software_version"],
                "model_version": extraction["model_version"],
            }
        )

    post_profiles = {
        artifact_id: _page_profile(store, artifact_id, threshold=threshold)
        for artifact_id in artifact_ids
    }
    for item in attachments:
        artifact_id = item["artifact"]["artifact_id"]
        item["ocr"] = ocr_results.get(artifact_id)
        item["post_ocr"] = post_profiles[artifact_id]

    duplicate_artifact_groups = []
    for artifact_id, source_records in sorted(sources_by_artifact.items()):
        if len(source_records) < 2:
            continue
        metadata = _artifact_metadata(store, artifact_id)
        _, name_status, names = _source_name_context(source_records)
        duplicate_artifact_groups.append(
            {
                "artifact_id": artifact_id,
                "artifact_sha256": metadata["sha256"],
                "source_count": len(source_records),
                "source_uris": [item["source_uri"] for item in source_records],
                "source_uri_sha256s": [item["source_uri_sha256"] for item in source_records],
                "source_names": names,
                "source_name_context_status": name_status,
            }
        )

    ocr_attempted = sum(result["attempted"] for result in ocr_results.values())
    ocr_added = sum(result["added"] for result in ocr_results.values())
    ocr_failed = sum(result["failed"] for result in ocr_results.values())
    failures = [failure for result in ocr_results.values() for failure in result["failures"]]
    total_pages = sum(profile["page_count"] for profile in post_profiles.values())
    low_pages = sum(profile["low_quality_page_count"] for profile in post_profiles.values())

    defaults = contract["defaults"]
    fully_unknown = sum(
        fact["scope"] == defaults["scope"]
        and fact["context_type"] == defaults["context_type"]
        and fact["amount_type"] == defaults["amount_type"]
        for fact in facts
    )
    context_known_amount_unknown = sum(
        fact["context_type"] != defaults["context_type"]
        and fact["amount_type"] == defaults["amount_type"]
        for fact in facts
    )
    amount_known = sum(fact["amount_type"] != defaults["amount_type"] for fact in facts)

    return {
        "schema": SCHEMA,
        "stage": "out_of_sample_representation_evaluation_only",
        "execution_label": "R1.T13b",
        "representation_assigned": True,
        "detector_authorized": False,
        "event_identity_assigned": False,
        "independence_assessed": False,
        "lead_count": None,
        "contract": {
            "contract_id": contract["contract_id"],
            "schema": contract["schema"],
            "parser_version": contract["parser_version"],
            "content_sha256": _sha256_file(contract_path),
            "defaults": contract["defaults"],
            "context_rule_ids": [rule["rule_id"] for rule in contract["context_rules"]],
            "amount_rule_ids": [rule["rule_id"] for rule in contract["amount_rules"]],
        },
        "sample": {
            "attachment_count": len(attachments),
            "unique_artifact_count": len(artifact_ids),
            "duplicate_artifact_group_count": len(duplicate_artifact_groups),
            "duplicate_artifact_groups": duplicate_artifact_groups,
            "selected_source_hashes": selection_sync["selection"]["selected_source_hashes"],
            "selected_signature_sha256": selection_sync["selection"]["selected_signature_sha256"],
            "excluded_source_hashes": selection_sync["selection"]["excluded_source_hashes"],
            "excluded_signature_sha256": selection_sync["selection"]["excluded_signature_sha256"],
            "selection_note": (
                "The T13b sources mechanically materialize the predeclared ranks 33-64 rule after "
                "T13 failed closed on an erroneous stored hash list. No document content or source-name "
                "feature was used to correct the identities. Money facts are counted once per unique "
                "Bronze/Silver artifact. Divergent duplicate source names are omitted from classification "
                "context rather than arbitrarily selected."
            ),
        },
        "extraction": {
            "quality_threshold": threshold,
            "unique_artifact_page_count": total_pages,
            "post_ocr_low_quality_page_count": low_pages,
            "ocr_requested": run_ocr,
            "ocr_unique_artifacts_attempted": len(ocr_results),
            "ocr_pages_attempted": ocr_attempted,
            "ocr_extractions_added": ocr_added,
            "ocr_failed": ocr_failed,
            "ocr_failures": failures,
            "tesseract_version": tesseract_version,
        },
        "structured_build": build.to_dict(),
        "money_fact_count": len(facts),
        "fully_unknown_fact_count": fully_unknown,
        "context_known_amount_unknown_fact_count": context_known_amount_unknown,
        "amount_type_known_fact_count": amount_known,
        "scope_counts": dict(sorted(scope_counts.items())),
        "context_type_counts": dict(sorted(context_counts.items())),
        "amount_type_counts": dict(sorted(amount_counts.items())),
        "source_name_context_status_counts": dict(sorted(source_name_status_counts.items())),
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
        contract_path=Path(args.contract),
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
