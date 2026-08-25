from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "akron-2026" / "retrieve_t21_council_minutes_documents.py"
SPEC = importlib.util.spec_from_file_location("t21_minutes_retrieval", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_document_base_uri_encodes_opaque_token_and_stays_on_publisher():
    uri = MODULE.document_base_uri(
        "https://onlinedocs.akronohio.gov/PublicAccess/api",
        "abc+/=É",
    )
    assert uri == (
        "https://onlinedocs.akronohio.gov/PublicAccess/api/Document/"
        "abc%2B%2F%3D%C3%89/"
    )


def test_document_base_uri_rejects_other_host():
    with pytest.raises(ValueError, match="publisher host"):
        MODULE.document_base_uri("https://example.com/api", "abc")


@pytest.mark.parametrize(
    ("metadata", "suffix", "representation"),
    [
        (
            {"ViewerMode": "PDF", "IsAboveDownloadThreshold": False},
            "/",
            "pdf",
        ),
        (
            {"ViewerMode": "PDF", "IsAboveDownloadThreshold": True},
            "/?ForceDownload=true",
            "pdf",
        ),
        (
            {"ViewerMode": "NativeOptional", "IsAboveDownloadThreshold": False},
            "/",
            "pdf",
        ),
        (
            {"ViewerMode": "Native", "IsAboveDownloadThreshold": False},
            "/?ViewerMode=Native&ForceDownload=true",
            "native",
        ),
    ],
)
def test_document_get_uri_mirrors_public_access_client(metadata, suffix, representation):
    uri, kind = MODULE.document_get_uri("https://host/Document/token/", metadata)
    assert uri.endswith(suffix)
    assert kind == representation


def test_parse_document_metadata_fails_closed():
    with pytest.raises(ValueError, match="ViewerMode"):
        MODULE.parse_document_metadata(
            b'{"Size":10,"ViewerMode":"Other","IsAboveDownloadThreshold":false}'
        )
    with pytest.raises(ValueError, match="IsAboveDownloadThreshold"):
        MODULE.parse_document_metadata(b'{"Size":10,"ViewerMode":"PDF"}')
    with pytest.raises(ValueError, match="Size"):
        MODULE.parse_document_metadata(
            b'{"Size":"10","ViewerMode":"PDF","IsAboveDownloadThreshold":false}'
        )


def test_group_retrievals_resolves_only_current_retrieved_bytes():
    rows = [
        {
            "meeting_id": 671,
            "stable_projection_sha256": "p",
            "document_sha256": "same",
        },
        {
            "meeting_id": 671,
            "stable_projection_sha256": "p",
            "document_sha256": "same",
        },
        {
            "meeting_id": 676,
            "stable_projection_sha256": "q",
            "document_sha256": "a",
        },
        {
            "meeting_id": 676,
            "stable_projection_sha256": "q",
            "document_sha256": "b",
        },
        {
            "meeting_id": 669,
            "stable_projection_sha256": "r",
            "document_sha256": "single",
        },
    ]
    groups = MODULE.group_retrievals(rows)
    by_meeting = {row["meeting_id"]: row for row in groups}
    assert by_meeting[671]["comparison"] == "multiple_handles_identical_retrieved_bytes"
    assert by_meeting[671]["unique_retrieved_byte_hash_count"] == 1
    assert by_meeting[676]["comparison"] == "multiple_handles_distinct_retrieved_bytes"
    assert by_meeting[676]["unique_retrieved_byte_hash_count"] == 2
    assert by_meeting[669]["comparison"] == "single_handle"
