from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_council_minutes_document_retrieval_summary.json"
)


def stable_sha(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_frozen_council_minutes_document_retrieval_receipt():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == (
        "proofline-akron-t21-council-minutes-document-retrieval-receipt/v1"
    )
    assert receipt["stage"] == (
        "frozen_publisher_council_minutes_source_bytes_before_content_interpretation"
    )

    canonical = receipt["canonical_measurement"]
    assert canonical["workflow_run_id"] == 32807585295
    assert canonical["job_id"] == 97680595723
    assert canonical["head_sha"] == "763b7d0206ed3760372cb11ac2d0d4e9ac61c00c"
    assert canonical["artifact_id"] == 9548671521

    counts = receipt["counts"]
    assert counts == {
        "duplicate_groups_with_distinct_retrieved_bytes": 5,
        "duplicate_groups_with_identical_retrieved_bytes": 0,
        "duplicate_metadata_group_count": 5,
        "native_retrieval_count": 0,
        "pdf_retrieval_count": 26,
        "retrieved_handle_count": 26,
        "stable_group_count": 21,
    }

    docs = receipt["document_receipts"]
    assert len(docs) == 26
    assert len({row["document_sha256"] for row in docs}) == 26
    assert stable_sha(docs) == receipt["document_receipts_signature_sha256"]
    for row in docs:
        assert row["representation"] == "pdf"
        assert row["viewer_mode"] == "PDF"
        assert row["metadata_size"] == row["document_byte_length"] > 0
        assert len(row["document_sha256"]) == 64
        assert len(row["stable_projection_sha256"]) == 64

    duplicates = receipt["duplicate_group_results"]
    assert [row["meeting_id"] for row in duplicates] == [671, 676, 686, 690, 694]
    for row in duplicates:
        assert row["handle_count"] == 2
        assert row["unique_retrieved_byte_hash_count"] == 2
        assert row["comparison"] == "multiple_handles_distinct_retrieved_bytes"
        assert len(set(row["retrieved_document_sha256s"])) == 2

    boundary = receipt["authority_boundary"]
    assert boundary["document_content_interpreted"] is False
    assert boundary["terminal_outcome_assigned"] is False
    assert boundary["opaque_token_treated_as_stable_identity"] is False
    assert receipt["interpretation"]["eastwood_outcome_status"] == "Unknown"
    assert receipt["receipt_guards"]["opaque_token_hashes_not_pinned"] is True
    assert receipt["receipt_guards"]["http_headers_not_pinned"] is True
