from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proofline.evidence_relationships import build_relationship_graph

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXP / name).read_text(encoding="utf-8"))


def frozen_sources():
    return (
        load("r1_t21_council_minutes_content_audit_summary.json"),
        load("r1_t21_committee_minutes_content_audit_summary.json"),
        load("r1_t21_committee_minutes_date_search_summary.json"),
    )


def test_frozen_relationship_graph_has_expected_nonterminal_shape():
    graph = build_relationship_graph(*frozen_sources())
    assert graph["counts"] == {
        "evidence_node_count": 8,
        "council_evidence_node_count": 6,
        "committee_evidence_node_count": 2,
        "relationship_count": 6,
        "same_target_same_meeting_count": 3,
        "procedural_phase_corroboration_count": 2,
        "explicit_scheduling_count": 1,
        "unpaired_target_evidence_node_count": 3,
    }
    assert graph["outcome"]["status"] == "unknown"
    assert graph["authority_boundary"]["terminal_semantics_authorized"] is False
    assert graph["authority_boundary"]["causality_assigned"] is False


def test_exact_relationship_types_and_phases_are_bounded():
    graph = build_relationship_graph(*frozen_sources())
    relations = graph["relationships"]
    assert [r["type"] for r in relations].count("same_target_same_meeting") == 3
    phase = [r for r in relations if r["type"] == "procedural_phase_corroboration"]
    assert sorted(r["detail"]["shared_procedural_phases"] for r in phase) == [["public_hearing"], ["referral"]]
    schedule = [r for r in relations if r["type"] == "explicit_scheduling"]
    assert len(schedule) == 1
    assert schedule[0]["detail"]["scheduled_date"] == "2026-03-09"
    assert schedule[0]["detail"]["resolved_meeting_id"] == 671


def test_later_council_public_comment_nodes_remain_unpaired_not_negative_evidence():
    graph = build_relationship_graph(*frozen_sources())
    nodes = {n["id"]: n for n in graph["nodes"]}
    unpaired = [nodes[node_id] for node_id in graph["unpaired_target_evidence_node_ids"]]
    assert sorted(n["meeting_id"] for n in unpaired) == [672, 674, 689]
    assert all(n["surface"] == "council_minutes" for n in unpaired)
    assert graph["authority_boundary"]["absence_is_not_disposition"] is True


def test_terminal_candidate_in_upstream_receipt_fails_closed():
    council, committee, dates = frozen_sources()
    changed = copy.deepcopy(council)
    changed["terminal_candidate_blocks"] = [{"meeting_id": 671}]
    with pytest.raises(ValueError, match="terminal candidates"):
        build_relationship_graph(changed, committee, dates)


def test_non_unknown_upstream_outcome_fails_closed():
    council, committee, dates = frozen_sources()
    changed = copy.deepcopy(committee)
    changed["outcome"]["status"] = "approved"
    with pytest.raises(ValueError, match="remain Unknown"):
        build_relationship_graph(council, changed, dates)


def test_same_meeting_without_two_shared_strong_anchors_does_not_corroborate_target():
    council, committee, dates = frozen_sources()
    changed = copy.deepcopy(committee)
    changed["target_block_receipts"][0]["anchor_hits"] = ["exact_address"]
    graph = build_relationship_graph(council, changed, dates)
    meeting_669 = [
        r for r in graph["relationships"]
        if r["type"] == "same_target_same_meeting" and r["detail"]["meeting_id"] == 669
    ]
    assert meeting_669 == []


def test_same_date_never_becomes_causality():
    graph = build_relationship_graph(*frozen_sources())
    assert graph["authority_boundary"]["same_date_is_not_causality"] is True
    assert graph["authority_boundary"]["committee_recommendation_is_not_final_disposition"] is True
    assert graph["authority_boundary"]["time_language_is_not_terminal_disposition"] is True
