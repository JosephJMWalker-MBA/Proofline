from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "akron-2026" / "audit_t21_committee_minutes_content.py"
PLAN_PATH = ROOT / "experiments" / "akron-2026" / "r1_t21_committee_minutes_content_audit_plan.json"
SPEC = importlib.util.spec_from_file_location("t21_committee_minutes_content_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def test_literal_phrase_matching_uses_boundaries():
    assert MODULE.literal_phrase_match("Filed as Council Document D-14.", "D-14")
    assert not MODULE.literal_phrase_match("Filed as Council Document D-140.", "D-14")
    assert MODULE.literal_phrase_match("Ayes: 5, Nays: 0", "yea") is False
    assert MODULE.literal_phrase_match("Mid-Year Operating Budget Review", "yea") is False


def test_whitespace_normalization_preserves_multiline_target_anchor():
    text = "ORDINANCE authorizing a Conditional Use to establish a defense education training facility at\n1928 Eastwood Avenue; and declaring an emergency."
    hits = MODULE.anchor_hits(text, PLAN)
    assert "exact_address" in hits
    assert "distinctive_title_phrase" in hits
    assert "training_eastwood_cooccurrence" in hits


def test_paragraph_locality_blocks_unrelated_terminal_language():
    text = """
ORDINANCE authorizing a Conditional Use to establish a defense education training facility at
1928 Eastwood Avenue; and declaring an emergency. Discussion was held.

ORDINANCE authorizing another matter. Motion by Fusco for passage. Said Ordinance was declared passed.
"""
    blocks = MODULE.audit_page_text(text, PLAN)
    assert len(blocks) == 1
    block = blocks[0]
    assert "exact_address" in block["anchor_hits"]
    assert "held" in block["procedural_phrase_hits"]
    assert "motion_for_passage" not in block["procedural_phrase_hits"]
    assert "declared_passed" not in block["procedural_phrase_hits"]


def test_motion_for_passage_requires_both_phrases_in_same_block():
    assert "motion_for_passage" in MODULE.procedural_phrase_hits(
        "Connor made a motion for passage.", PLAN
    )
    assert "motion_for_passage" not in MODULE.procedural_phrase_hits(
        "Connor made a motion to hold the item.", PLAN
    )


def test_split_paragraph_blocks_preserves_line_ranges():
    blocks = MODULE.split_paragraph_blocks("header\nline two\n\nitem\n")
    assert blocks == [
        {"line_start": 1, "line_end": 2, "text": "header\nline two"},
        {"line_start": 4, "line_end": 4, "text": "item"},
    ]
