import json
from pathlib import Path

AUDIT = Path("experiments/akron-2026/r1_t21_april27_contextual_audit.json")
REPORT = Path("experiments/akron-2026/R1_T21_APRIL27_CONTEXTUAL_AUDIT.md")


def test_contextual_audit_preserves_authority_boundaries():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["schema"] == "proofline-akron-t21-april27-human-contextual-audit/v1"
    assert audit["stage"] == "post_freeze_human_contextual_audit"
    assert audit["authority"] == {
        "community_representativeness_assigned": False,
        "cross_document_causality_assigned": False,
        "detector_authorized": False,
        "document_statements_are_not_automatically_treated_as_true": True,
        "final_outcome_assigned": False,
        "human_contextual_interpretation_performed": True,
        "lead_count": None,
    }
    assert audit["outcome"]["status"] == "unknown"


def test_contextual_audit_covers_complete_frozen_family_without_semantic_reselection():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rows = audit["document_audits"]
    assert len(rows) == 20
    assert [row["publish_id"] for row in rows] == list(range(102587, 102607))
    assert audit["corpus"]["document_count"] == 20
    assert audit["corpus"]["page_count"] == 88
    assert audit["corpus"]["reading_corpus_json_sha256"] == "ca6d2ff970d713346ee5a7592008567ba4dc08bdbd48d504c84b7475ff1a2459"


def test_contextual_audit_keeps_known_representation_gaps_explicit():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    by_id = {row["publish_id"]: row for row in audit["document_audits"]}
    assert by_id[102593]["stance_or_function"] == "unresolved"
    assert by_id[102597]["stance_or_function"] == "partially_unresolved"
    obligations = audit["unresolved_evidence_obligations"]
    assert all(item["status"] == "unresolved" for item in obligations)
    assert any("final ordinance disposition" in item["obligation"].lower() for item in obligations)
    assert any("photographs" in item["obligation"].lower() for item in obligations)


def test_contextual_report_explicitly_rejects_causal_and_outcome_overclaiming():
    report = REPORT.read_text(encoding="utf-8")
    assert "public opposition caused the March 9 amendment" in report
    assert "public opposition caused Council to keep the matter under `TIME`" in report
    assert "Outcome remains `Unknown`" in report
    assert "It is **not evidence of why** Council added the hours condition" in report
    assert "A causal statement" in report
