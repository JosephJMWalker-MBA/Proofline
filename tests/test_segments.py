from __future__ import annotations

import json

import pytest

from proofline import Ingestor
from proofline.segments import (
    SegmentIndex,
    SegmentationPlan,
    SegmentationRule,
    load_segmentation_plan,
    segment_text,
    segmentation_plan_sha256,
)


_BOARD_RULE = SegmentationRule(
    name="ordinance-items",
    source_name_regex=r"^Board of Control",
    anchor_regex=r"(?i)^[ \t]*Ordinance[ \t]+(?P<anchor>(?:TBD(?:/\d{4})?|\d{1,4}/\d{4}))[ \t]*$",
    segment_type="agenda_item",
    min_chars=20,
)


def test_segment_text_preserves_exact_evidence_spans() -> None:
    text = (
        "AGENDA HEADER\n"
        "Ordinance 3/2026\n"
        "Award a contract for $100.00.\n\n"
        "Ordinance 52/2026\n"
        "Enter into a professional services agreement for $57,000.00.\n"
    )
    segments = segment_text(text, _BOARD_RULE)
    assert len(segments) == 2

    first, second = segments
    assert first.anchor_text == "3/2026"
    assert first.normalized_anchor == "3/2026"
    assert first.raw_text == text[first.char_start : first.char_end]
    assert first.raw_text.startswith("Ordinance 3/2026")
    assert "AGENDA HEADER" not in first.raw_text
    assert second.raw_text == text[second.char_start : second.char_end]
    assert second.raw_text.startswith("Ordinance 52/2026")
    assert first.text_sha256 != second.text_sha256


def test_segment_text_ignores_too_short_anchor_blocks() -> None:
    rule = SegmentationRule(
        name="numbered",
        source_name_regex=r"^City Council",
        anchor_regex=r"^[ \t]*(?P<anchor>\d{1,3})\.[ \t]*$",
        segment_type="agenda_item",
        min_chars=25,
    )
    text = "1.\nOK\n2.\nA sufficiently descriptive council agenda item for testing.\n"
    segments = segment_text(text, rule)
    assert len(segments) == 1
    assert segments[0].anchor_text == "2"


def test_plan_requires_named_anchor_group_and_deterministic_hash(tmp_path) -> None:
    path = tmp_path / "plan.json"
    payload = {
        "schema": "proofline-segmentation-plan/v1",
        "name": "fixture",
        "rules": [
            {
                "name": "board",
                "source_name_regex": "^Board of Control",
                "anchor_regex": r"(?i)^Ordinance (?P<anchor>\d+/\d{4})$",
                "segment_type": "agenda_item",
                "min_chars": 20,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    first = load_segmentation_plan(path)
    second = load_segmentation_plan(path)
    assert first == second
    assert segmentation_plan_sha256(first) == segmentation_plan_sha256(second)

    payload["rules"][0]["anchor_regex"] = r"(?i)^Ordinance \d+/\d{4}$"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="named group 'anchor'"):
        load_segmentation_plan(path)


def test_segment_index_finds_exact_repeats_across_artifacts_only(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)
    shared = (
        "Ordinance 3/2026\n"
        "Award and enter into a five-year contract with Example Systems for public services.\n"
    )
    first_text = shared + "Ordinance 52/2026\nFirst document unique item text.\n"
    second_text = shared + "Ordinance 86/2026\nSecond document unique item text.\n"
    ignored_text = shared

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    ignored = tmp_path / "ignored.txt"
    first.write_text(first_text, encoding="utf-8")
    second.write_text(second_text, encoding="utf-8")
    ignored.write_text(ignored_text, encoding="utf-8")

    ingestor.ingest(
        first,
        source_uri="https://example.gov/board/1",
        source_name="Board of Control — Meeting One",
    )
    ingestor.ingest(
        second,
        source_uri="https://example.gov/board/2",
        source_name="Board of Control — Meeting Two",
    )
    ingestor.ingest(
        ignored,
        source_uri="https://example.gov/other/1",
        source_name="Planning Commission — Meeting One",
    )

    plan = SegmentationPlan(name="fixture", rules=(_BOARD_RULE,))
    index = SegmentIndex(state)
    result = index.rebuild(plan)
    assert result.rule_count == 1
    assert result.evidence_count == 2
    assert result.segment_count == 4

    anchor_hits = index.anchor("3/2026", segment_type="agenda_item")
    assert len(anchor_hits) == 2
    assert {hit.anchor_text for hit in anchor_hits} == {"3/2026"}
    assert all(hit.raw_text.startswith("Ordinance 3/2026") for hit in anchor_hits)

    repeats = index.repeated(min_artifacts=2)
    assert len(repeats) == 1
    repeat = repeats[0]
    assert repeat.artifact_count == 2
    assert repeat.occurrence_count == 2
    assert len(repeat.occurrences) == 2
    assert all(item.evidence_id for item in repeat.occurrences)
    assert all(item.sources for item in repeat.occurrences)
    assert "example systems" in repeat.normalized_text


def test_repeated_requires_distinct_artifacts(tmp_path) -> None:
    state = tmp_path / "state"
    source = tmp_path / "one.txt"
    source.write_text(
        "Ordinance 3/2026\nRepeated body text for the same artifact.\n"
        "Ordinance 3/2026\nRepeated body text for the same artifact.\n",
        encoding="utf-8",
    )
    Ingestor(state).ingest(
        source,
        source_uri="https://example.gov/board/one",
        source_name="Board of Control — One artifact",
    )
    index = SegmentIndex(state)
    index.rebuild(SegmentationPlan(name="fixture", rules=(_BOARD_RULE,)))
    assert index.repeated(min_artifacts=2) == []
