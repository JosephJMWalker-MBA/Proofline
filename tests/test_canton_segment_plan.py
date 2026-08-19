from __future__ import annotations

import re
from pathlib import Path

from proofline.segments import load_segmentation_plan, segment_text


def _board_rule():
    plan = load_segmentation_plan(Path("experiments/canton-2026/segment-plan.json"))
    return next(rule for rule in plan.rules if rule.name == "board-ordinance-items")


def test_board_rule_splits_singular_plural_and_compound_ordinance_headings() -> None:
    text = """Header ignored before first agenda item.
Ordinance 52/2026
Enter into Change Order No. 4 with Arcadis U.S., Inc. for Project GP1165.
Ordinance 21/2025 & 5/2026
Award and enter into a construction contract with Wenger Excavating, Inc. for Project GP1472.
Ordinances 106/2025 & 5/2026
Enter into Change Order No. 2 with Example Contractor for Project GP1400.
Ordinance TBD/2026
Enter into a professional services agreement with Example Engineers for Project GP1500.
"""
    segments = segment_text(text, _board_rule())
    assert [segment.anchor_text for segment in segments] == [
        "52/2026",
        "21/2025 & 5/2026",
        "106/2025 & 5/2026",
        "TBD/2026",
    ]
    assert "GP1165" in segments[0].raw_text
    assert "GP1472" not in segments[0].raw_text
    assert "GP1472" in segments[1].raw_text
    assert "GP1400" not in segments[1].raw_text


def test_each_board_segment_contains_only_its_own_ordinance_heading() -> None:
    text = """Ordinance 52/2026
First substantive agenda item with enough text to meet the segmentation minimum character rule.
Ordinances 51/2026 & 93/2026
Second substantive agenda item with enough text to meet the segmentation minimum character rule.
Ordinance TBD
Third substantive agenda item with enough text to meet the segmentation minimum character rule.
"""
    segments = segment_text(text, _board_rule())
    heading = re.compile(r"(?im)^[ \t]*Ordinances?[ \t]+")
    assert len(segments) == 3
    for segment in segments:
        assert len(heading.findall(segment.raw_text)) == 1
