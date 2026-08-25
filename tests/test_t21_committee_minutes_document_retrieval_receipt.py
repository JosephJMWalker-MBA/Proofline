from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
RECEIPT = EXPERIMENT / "r1_t21_committee_minutes_document_retrieval_summary.json"
SEARCH_RECEIPT = EXPERIMENT / "r1_t21_committee_minutes_date_search_summary.json"


def test_committee_minutes_document_retrieval_receipt_is_bounded_and_nonterminal() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    search = json.loads(SEARCH_RECEIPT.read_text(encoding="utf-8"))

    assert receipt["schema"] == "proofline-akron-t21-committee-minutes-document-retrieval-receipt/v1"
    assert receipt["stage"] == "frozen_publisher_committee_minutes_source_bytes_before_content_interpretation"
    assert receipt["fresh_search"]["stable_candidate_population_signature_sha256"] == search["candidate_population"]["stable_population_signature_sha256"]
    assert receipt["fresh_search"]["response_population_signature_sha256"] == search["candidate_population"]["response_population_signature_sha256"]
    assert receipt["fresh_search"]["returned_handle_count"] == 18

    counts = receipt["counts"]
    assert counts == {
        "metadata_size_match_count": 18,
        "native_retrieval_count": 0,
        "pdf_retrieval_count": 18,
        "retrieved_handle_count": 18,
        "stable_group_count": 18,
        "unique_document_sha256_count": 18,
    }

    rows = receipt["stable_document_receipts"]
    assert len(rows) == 18
    assert len({row["meeting_id"] for row in rows}) == 18
    assert len({row["document_sha256"] for row in rows}) == 18
    assert all(row["representation"] == "pdf" for row in rows)
    assert all(row["viewer_mode"] == "PDF" for row in rows)
    assert all(row["document_pdf_signature"] is True for row in rows)
    assert all(row["metadata_size_matches_document_bytes"] is True for row in rows)
    assert all(row["metadata_size"] == row["document_byte_length"] for row in rows)
    assert all(row["is_above_download_threshold"] is False for row in rows)

    stable = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert hashlib.sha256(stable).hexdigest() == receipt["stable_document_receipt_population_signature_sha256"]

    guards = receipt["receipt_guards"]
    assert guards["document_bytes_pinned_by_sha256_and_length"] is True
    assert guards["opaque_token_hashes_not_pinned"] is True
    assert guards["http_headers_not_pinned"] is True
    assert guards["raw_metadata_bytes_not_pinned"] is True
    assert guards["document_content_interpreted"] is False

    authority = receipt["authority_boundary"]
    assert authority["fresh_candidate_population_reproduced"] is True
    assert authority["every_current_returned_handle_retrieved"] is True
    assert authority["source_bytes_preserved"] is True
    assert authority["document_content_interpreted"] is False
    assert authority["opaque_token_treated_as_stable_identity"] is False
    assert authority["terminal_outcome_assigned"] is False
    assert authority["absence_treated_as_disposition"] is False
    assert receipt["outcome"]["status"] == "unknown"
    assert receipt["interpretation"]["eastwood_outcome_status"] == "Unknown"
