from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "retrieve_t21_committee_minutes_documents.py"
SPEC = importlib.util.spec_from_file_location("t21_committee_retrieval", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load_receipt() -> dict:
    return json.loads((EXPERIMENT / "r1_t21_committee_minutes_date_search_summary.json").read_text(encoding="utf-8"))


def matching_search(receipt: dict) -> dict:
    rows = []
    for expected in receipt["eastwood_searches"]:
        rows.append({
            **expected,
            "response": {"ok": True, "same_host": True},
            "returned_documents": [],
        })
    return {
        "schema": MODULE.SEARCH_SCHEMA,
        "positive_control": {
            "response": {"ok": True, "same_host": True},
            "truncated": False,
            "returned_document_count": 1,
        },
        "eastwood_searches": rows,
        "counts": dict(receipt["counts"]),
        "candidate_population": dict(receipt["candidate_population"]),
    }


def test_document_base_uri_encodes_opaque_token_and_stays_on_publisher():
    uri = MODULE.document_base_uri(
        "https://onlinedocs.akronohio.gov/PublicAccess/api", "abc+/=É"
    )
    assert uri.endswith("/Document/abc%2B%2F%3D%C3%89/")


def test_document_base_uri_rejects_other_host():
    with pytest.raises(ValueError, match="publisher host"):
        MODULE.document_base_uri("https://example.com/api", "abc")


@pytest.mark.parametrize(
    ("metadata", "suffix", "kind"),
    [
        ({"ViewerMode": "PDF", "IsAboveDownloadThreshold": False}, "/", "pdf"),
        ({"ViewerMode": "PDF", "IsAboveDownloadThreshold": True}, "/?ForceDownload=true", "pdf"),
        ({"ViewerMode": "NativeOptional", "IsAboveDownloadThreshold": False}, "/", "pdf"),
        ({"ViewerMode": "Native", "IsAboveDownloadThreshold": False}, "/?ViewerMode=Native&ForceDownload=true", "native"),
    ],
)
def test_document_get_uri_matches_frozen_public_access_client(metadata, suffix, kind):
    uri, representation = MODULE.document_get_uri("https://host/Document/token/", metadata)
    assert uri.endswith(suffix)
    assert representation == kind


def test_parse_document_metadata_fails_closed():
    with pytest.raises(ValueError, match="ViewerMode"):
        MODULE.parse_document_metadata(b'{"Size":10,"ViewerMode":"Other","IsAboveDownloadThreshold":false}')
    with pytest.raises(ValueError, match="IsAboveDownloadThreshold"):
        MODULE.parse_document_metadata(b'{"Size":10,"ViewerMode":"PDF"}')
    with pytest.raises(ValueError, match="Size"):
        MODULE.parse_document_metadata(b'{"Size":"10","ViewerMode":"PDF","IsAboveDownloadThreshold":false}')


def test_frozen_search_receipt_accepts_token_independent_reproduction():
    receipt = load_receipt()
    search = matching_search(receipt)
    MODULE.validate_search_against_receipt(search, receipt)


def test_frozen_search_receipt_rejects_population_drift():
    receipt = load_receipt()
    search = matching_search(receipt)
    search["counts"]["eastwood_returned_document_token_count"] = 17
    with pytest.raises(ValueError, match="population drifted"):
        MODULE.validate_search_against_receipt(search, receipt)


def test_frozen_search_receipt_rejects_result_signature_drift():
    receipt = load_receipt()
    search = matching_search(receipt)
    search["eastwood_searches"][2]["stable_result_signature_sha256"] = "drift"
    with pytest.raises(ValueError, match="drifted at stable_result_signature_sha256"):
        MODULE.validate_search_against_receipt(search, receipt)


def test_stable_document_receipts_exclude_opaque_tokens_and_http_headers():
    rows = [{
        "meeting_id": 671,
        "stable_projection_sha256": "projection",
        "representation": "pdf",
        "document_sha256": "document",
        "document_byte_length": 123,
        "document_pdf_signature": True,
        "metadata_size_matches_document_bytes": True,
        "metadata": {"Size": 123, "ViewerMode": "PDF", "IsAboveDownloadThreshold": False},
        "opaque_token_sha256": "must-not-appear",
        "document_http": {"etag": "must-not-appear"},
    }]
    receipt = MODULE.stable_document_receipts(rows)
    assert receipt == [{
        "meeting_id": 671,
        "stable_projection_sha256": "projection",
        "representation": "pdf",
        "document_sha256": "document",
        "document_byte_length": 123,
        "document_pdf_signature": True,
        "metadata_size": 123,
        "metadata_size_matches_document_bytes": True,
        "viewer_mode": "PDF",
        "is_above_download_threshold": False,
    }]
    assert "must-not-appear" not in json.dumps(receipt)
