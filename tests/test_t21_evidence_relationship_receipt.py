from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXP / name).read_text(encoding="utf-8"))


def sha256_file(name: str) -> str:
    return hashlib.sha256((EXP / name).read_bytes()).hexdigest()


def test_relationship_receipt_pins_exact_upstream_files_and_populations():
    receipt = load("r1_t21_evidence_relationship_summary.json")
    assert receipt["schema"] == "proofline-akron-t21-evidence-relationship-receipt/v1"
    sources = receipt["source_receipts"]
    assert sources["council_minutes_content"]["file_sha256"] == sha256_file(
        "r1_t21_council_minutes_content_audit_summary.json"
    )
    assert sources["committee_minutes_content"]["file_sha256"] == sha256_file(
        "r1_t21_committee_minutes_content_audit_summary.json"
    )
    assert sources["committee_minutes_dates"]["file_sha256"] == sha256_file(
        "r1_t21_committee_minutes_date_search_summary.json"
    )
    assert sources["council_minutes_content"]["terminal_candidate_count"] == 0
    assert sources["committee_minutes_content"]["terminal_candidate_count"] == 0


def test_relationship_receipt_exact_graph_shape_and_unpaired_meetings():
    receipt = load("r1_t21_evidence_relationship_summary.json")
    assert receipt["counts"] == {
        "committee_evidence_node_count": 2,
        "council_evidence_node_count": 6,
        "evidence_node_count": 8,
        "explicit_scheduling_count": 1,
        "procedural_phase_corroboration_count": 2,
        "relationship_count": 6,
        "same_target_same_meeting_count": 3,
        "unpaired_target_evidence_node_count": 3,
    }
    nodes = {node["id"]: node for node in receipt["nodes"]}
    unpaired = [nodes[node_id] for node_id in receipt["unpaired_target_evidence_node_ids"]]
    assert sorted(node["meeting_id"] for node in unpaired) == [672, 674, 689]
    assert all(node["surface"] == "council_minutes" for node in unpaired)


def test_relationship_receipt_contains_only_nonterminal_relationship_types():
    receipt = load("r1_t21_evidence_relationship_summary.json")
    allowed = {
        "same_target_same_meeting",
        "procedural_phase_corroboration",
        "explicit_scheduling",
    }
    assert {row["type"] for row in receipt["relationships"]} <= allowed
    boundary = receipt["authority_boundary"]
    assert boundary["relationships_are_provenance_only"] is True
    assert boundary["same_date_is_not_causality"] is True
    assert boundary["committee_recommendation_is_not_final_disposition"] is True
    assert boundary["time_language_is_not_terminal_disposition"] is True
    assert boundary["absence_is_not_disposition"] is True
    assert boundary["terminal_semantics_authorized"] is False
    assert boundary["causality_assigned"] is False
    assert receipt["outcome"]["status"] == "unknown"


def test_relationship_receipt_signatures_are_frozen():
    receipt = load("r1_t21_evidence_relationship_summary.json")
    assert receipt["node_population_signature_sha256"] == "8de7d8bf065f1338121d10a562e4843b66cfdabcd47765b92b0d7b528cc7ff77"
    assert receipt["relationship_population_signature_sha256"] == "906cfa23129ad49dd8dd4c67a29c5076fb4e49eab77d5c7f77a19d18b0b0529b"
    assert receipt["graph_signature_sha256"] == "2d646c748bb4d455b442d4b54eb64e46083410e05870410229b6526b8475bce4"
