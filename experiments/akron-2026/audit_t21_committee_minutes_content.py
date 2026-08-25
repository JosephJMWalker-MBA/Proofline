#!/usr/bin/env python3
"""Audit frozen Planning committee-minutes PDFs for target-local T21 evidence.

The source-byte population must match the frozen #106 receipt before text is
extracted. Selection uses only the predeclared audit plan. Text-layer evidence
is preserved page-locally and paragraph/block-locally. Procedural language from
another paragraph or agenda item on the same page is never borrowed into the
target block. No terminal legislative outcome is assigned.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import fitz

SCHEMA = "proofline-akron-t21-committee-minutes-content-audit-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-committee-minutes-content-audit-plan/v1"
RECEIPT_SCHEMA = "proofline-akron-t21-committee-minutes-document-retrieval-receipt/v1"


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def load_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def normalize(text: str) -> str:
    return " ".join(text.split())


def literal_phrase_match(text: str, phrase: str) -> bool:
    """Case-insensitive normalized literal phrase with alphanumeric boundaries."""
    haystack = normalize(text).lower()
    needle = normalize(phrase).lower()
    escaped = re.escape(needle).replace(r"\ ", r"\s+")
    pattern = rf"(?<![0-9a-z]){escaped}(?![0-9a-z])"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


def anchor_hits(text: str, plan: dict) -> list[str]:
    hits: list[str] = []
    for definition in plan["target_anchors"]:
        if "pattern" in definition:
            if literal_phrase_match(text, definition["pattern"]):
                hits.append(definition["id"])
        else:
            required = definition.get("requires", [])
            if required and all(literal_phrase_match(text, phrase) for phrase in required):
                hits.append(definition["id"])
    return hits


def procedural_phrase_hits(text: str, plan: dict) -> list[str]:
    hits: list[str] = []
    for definition in plan["procedural_phrases"]:
        if not literal_phrase_match(text, definition["pattern"]):
            continue
        required = definition.get("requires_same_block_all", [])
        if all(literal_phrase_match(text, phrase) for phrase in required):
            hits.append(definition["id"])
    return hits


def split_paragraph_blocks(text: str) -> list[dict]:
    """Split PyMuPDF text into contiguous nonblank paragraph/agenda-item blocks."""
    lines = text.splitlines()
    blocks: list[dict] = []
    start: int | None = None
    buffer: list[str] = []
    for line_no, line in enumerate(lines, start=1):
        if line.strip():
            if start is None:
                start = line_no
            buffer.append(line)
            continue
        if buffer:
            blocks.append(
                {
                    "line_start": start,
                    "line_end": line_no - 1,
                    "text": "\n".join(buffer).strip(),
                }
            )
            start = None
            buffer = []
    if buffer:
        blocks.append(
            {
                "line_start": start,
                "line_end": len(lines),
                "text": "\n".join(buffer).strip(),
            }
        )
    return blocks


def validate_source_population(retrieval: dict, receipt: dict, retrieval_root: Path) -> None:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected Committee minutes retrieval receipt schema")
    expected_rows = receipt.get("stable_document_receipts")
    if not isinstance(expected_rows, list) or len(expected_rows) != 18:
        raise ValueError("frozen Committee minutes receipt must contain 18 source documents")

    expected = {
        (
            row["meeting_id"],
            row["stable_projection_sha256"],
            row["document_sha256"],
            row["document_byte_length"],
        )
        for row in expected_rows
    }
    actual = set()
    retrieval_rows = retrieval.get("retrievals")
    if not isinstance(retrieval_rows, list) or len(retrieval_rows) != 18:
        raise ValueError("fresh Committee minutes retrieval must contain exactly 18 documents")

    for row in retrieval_rows:
        path = retrieval_root / row["document_filename"]
        body = path.read_bytes()
        if not body.startswith(b"%PDF-"):
            raise ValueError(f"source document is not a PDF: {path}")
        if sha256_bytes(body) != row["document_sha256"]:
            raise ValueError(f"source PDF hash drift: {path}")
        if len(body) != row["document_byte_length"]:
            raise ValueError(f"source PDF length drift: {path}")
        actual.add(
            (
                row["meeting_id"],
                row["stable_projection_sha256"],
                row["document_sha256"],
                row["document_byte_length"],
            )
        )

    if actual != expected:
        raise ValueError("fresh source PDF population diverged from frozen #106 receipt")


def stable_page_projection(pages: list[dict]) -> list[dict]:
    return [
        {
            "meeting_id": row["meeting_id"],
            "document_sha256": row["document_sha256"],
            "page": row["page"],
            "anchor_hits": row["anchor_hits"],
            "page_text_sha256": row["page_text_sha256"],
        }
        for row in pages
    ]


def stable_block_projection(blocks: list[dict]) -> list[dict]:
    return [
        {
            "meeting_id": row["meeting_id"],
            "document_sha256": row["document_sha256"],
            "page": row["page"],
            "paragraph_index": row["paragraph_index"],
            "line_start": row["line_start"],
            "line_end": row["line_end"],
            "anchor_hits": row["anchor_hits"],
            "procedural_phrase_hits": row["procedural_phrase_hits"],
            "block_text_sha256": row["block_text_sha256"],
        }
        for row in blocks
    ]


def audit_page_text(text: str, plan: dict) -> list[dict]:
    """Return only target-local paragraph blocks from one extracted page."""
    result: list[dict] = []
    for index, block in enumerate(split_paragraph_blocks(text), start=1):
        hits = anchor_hits(block["text"], plan)
        if not hits:
            continue
        result.append(
            {
                "paragraph_index": index,
                "line_start": block["line_start"],
                "line_end": block["line_end"],
                "anchor_hits": hits,
                "procedural_phrase_hits": procedural_phrase_hits(block["text"], plan),
                "block_text_sha256": sha256_bytes(block["text"].encode("utf-8")),
                "block_text": block["text"],
                "block_boundary_confidence": "paragraph_local",
            }
        )
    return result


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: audit_t21_committee_minutes_content.py "
            "<retrieval.json> <retrieval-dir> <frozen-retrieval-receipt.json> "
            "<audit-plan.json> <output-dir>"
        )

    retrieval_path = Path(sys.argv[1])
    retrieval_root = Path(sys.argv[2])
    receipt_path = Path(sys.argv[3])
    plan_path = Path(sys.argv[4])
    output = Path(sys.argv[5])
    output.mkdir(parents=True, exist_ok=True)

    retrieval = load_json(retrieval_path)
    receipt = load_json(receipt_path)
    plan = load_json(plan_path)
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unexpected Committee minutes content-audit plan schema")
    if plan["text_extraction"]["ocr_allowed"] is not False:
        raise ValueError("OCR must remain disabled")
    if plan["selection_rule"]["post_observation_anchor_expansion_allowed"] is not False:
        raise ValueError("post-observation anchor expansion must remain forbidden")

    validate_source_population(retrieval, receipt, retrieval_root)

    matched_page_dir = output / "matched-pages"
    matched_page_dir.mkdir(exist_ok=True)
    documents: list[dict] = []
    target_pages: list[dict] = []
    target_blocks: list[dict] = []
    terminal_candidates: list[dict] = []
    total_pages = 0

    for source in sorted(retrieval["retrievals"], key=lambda row: row["meeting_id"]):
        pdf_path = retrieval_root / source["document_filename"]
        document = fitz.open(pdf_path)
        total_pages += len(document)
        document_matches: list[dict] = []

        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text")
            page_hits = anchor_hits(text, plan)
            if not page_hits:
                continue

            page_bytes = text.encode("utf-8")
            page_text_sha256 = sha256_bytes(page_bytes)
            page_filename = f"{source['document_sha256']}-p{page_index:03d}.txt"
            (matched_page_dir / page_filename).write_bytes(page_bytes)

            blocks = audit_page_text(text, plan)
            page_entry = {
                "meeting_id": source["meeting_id"],
                "document_sha256": source["document_sha256"],
                "stable_projection_sha256": source["stable_projection_sha256"],
                "page": page_index,
                "anchor_hits": page_hits,
                "page_text_sha256": page_text_sha256,
                "page_text_byte_length": len(page_bytes),
                "page_text_file": f"matched-pages/{page_filename}",
                "target_blocks": blocks,
            }
            target_pages.append(page_entry)
            document_matches.append(page_entry)

            for block in blocks:
                entry = {
                    "meeting_id": source["meeting_id"],
                    "document_sha256": source["document_sha256"],
                    "page": page_index,
                    **block,
                }
                target_blocks.append(entry)
                terminal_ids = [
                    phrase_id
                    for phrase_id in block["procedural_phrase_hits"]
                    if phrase_id in plan["terminal_candidate_phrase_ids"]
                ]
                if terminal_ids:
                    terminal_candidates.append(
                        {
                            "meeting_id": source["meeting_id"],
                            "document_sha256": source["document_sha256"],
                            "page": page_index,
                            "paragraph_index": block["paragraph_index"],
                            "phrase_ids": terminal_ids,
                        }
                    )

        documents.append(
            {
                "meeting_id": source["meeting_id"],
                "document_sha256": source["document_sha256"],
                "page_count": len(document),
                "matched_page_count": len(document_matches),
                "matched_pages": document_matches,
            }
        )

    target_pages.sort(key=lambda row: (row["meeting_id"], row["page"]))
    target_blocks.sort(key=lambda row: (row["meeting_id"], row["page"], row["paragraph_index"]))
    terminal_candidates.sort(key=lambda row: (row["meeting_id"], row["page"], row["paragraph_index"]))

    anchor_counts = {
        definition["id"]: sum(definition["id"] in row["anchor_hits"] for row in target_blocks)
        for definition in plan["target_anchors"]
    }
    procedural_counts = {
        definition["id"]: sum(
            definition["id"] in row["procedural_phrase_hits"] for row in target_blocks
        )
        for definition in plan["procedural_phrases"]
    }

    measurement = {
        "schema": SCHEMA,
        "stage": "frozen_committee_minutes_source_bytes_text_layer_page_and_target_block_audit",
        "text_extraction": {
            "engine": "PyMuPDF",
            "version": fitz.VersionBind,
            "ocr_used": False,
            "literal_pattern_matching": "case-insensitive normalized whole phrase with alphanumeric boundaries",
        },
        "source_receipt": {
            "schema": receipt["schema"],
            "stable_document_receipt_population_signature_sha256": receipt[
                "stable_document_receipt_population_signature_sha256"
            ],
            "document_count": len(receipt["stable_document_receipts"]),
            "source_receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
        },
        "plan": {
            "schema": plan["schema"],
            "sha256": sha256_json(plan),
        },
        "counts": {
            "document_count": len(documents),
            "page_count": total_pages,
            "documents_with_target_pages": sum(1 for row in documents if row["matched_page_count"]),
            "target_page_count": len(target_pages),
            "target_block_count": len(target_blocks),
            "terminal_candidate_block_count": len(terminal_candidates),
        },
        "anchor_block_counts": anchor_counts,
        "procedural_phrase_block_counts": procedural_counts,
        "documents": documents,
        "target_pages": target_pages,
        "target_blocks": target_blocks,
        "terminal_candidate_blocks": terminal_candidates,
        "target_page_population_signature_sha256": sha256_json(stable_page_projection(target_pages)),
        "target_block_population_signature_sha256": sha256_json(stable_block_projection(target_blocks)),
        "terminal_candidate_population_signature_sha256": sha256_json(terminal_candidates),
        "authority_boundary": {
            "source_pdf_population_verified": True,
            "ocr_used": False,
            "page_text_extracted": True,
            "target_block_locality_enforced": True,
            "procedural_phrase_hits_are_observations_only": True,
            "committee_recommendation_treated_as_final_council_disposition": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "This audit preserves target-local Committee minutes text and procedural phrase observations only. No terminal Council outcome is assigned.",
        },
    }

    output_path = output / "committee-minutes-content-audit.json"
    output_path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(measurement["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
