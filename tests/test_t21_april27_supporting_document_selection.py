import hashlib
import json
from pathlib import Path


SELECTION = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def _load() -> dict:
    return json.loads(SELECTION.read_text(encoding="utf-8"))


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_t21_april27_selection_is_identity_only_and_complete() -> None:
    selection = _load()
    assert selection["schema"] == "proofline-akron-t21-april27-supporting-document-selection/v1"
    assert selection["stage"] == "post_packet_contextual_audit_pre_supporting_document_acquisition"
    assert selection["selected_document_count"] == 20
    rows = selection["selected_documents"]
    assert len(rows) == 20
    assert all(row["meeting_id"] == 682 for row in rows)
    assert all(row["item_id"] == 47559 for row in rows)
    assert [row["publish_id"] for row in rows] == list(range(102587, 102607))
    assert all(set(row) == {"meeting_id", "item_id", "publish_id", "source_uri_sha256", "link_text_sha256"} for row in rows)
    assert all(len(row["source_uri_sha256"]) == 64 for row in rows)
    assert all(len(row["link_text_sha256"]) == 64 for row in rows)


def test_t21_april27_selection_signature_and_parent_are_frozen() -> None:
    selection = _load()
    rows = selection["selected_documents"]
    assert _sha256_json(rows) == "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
    assert selection["selection_signature_sha256"] == "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
    assert selection["basis"] == {
        "attachment_manifest_sha256": "7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a",
        "contextual_audit_commit": "53509846e148c223ffbae5b411dfa600df897d8c",
        "parent_artifact_sha256": "e798e9a3561189aded6ef784a551cf4782d144e6715107ae04fea4ad643ba4ca",
        "parent_item_id": 47559,
        "parent_meeting_id": 682,
        "parent_source_uri_sha256": "3e45697901d20d589213993acd1f903fca3072df1bfd1434f759d621a1d9e4cc",
        "publisher_declared_relation_count": 20,
    }


def test_t21_april27_selection_preserves_no_outcome_claim() -> None:
    selection = _load()
    assert selection["selection_method"]["content_blind"] is True
    assert selection["selection_method"]["relation_type"] == "supporting_document_of"
    text = json.dumps(selection).lower()
    assert "outcome_assigned" not in text
    assert "lead_count" not in text
