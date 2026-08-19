from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofline import Ingestor
from proofline.matter_keys import (
    MatterKeyPolicy,
    MatterKeyResolver,
    MatterKeyResolverRule,
    MatterKeyStatus,
    load_matter_key_policy,
    matter_key_policy_sha256,
    resolve_segment,
)
from proofline.segments import SegmentHit, SegmentIndex, SegmentationPlan, SegmentationRule


POLICY_PATH = Path("experiments/canton-2026/matter-key-policy.json")


def _hit(text: str, *, segment_id: str, char_start: int = 100) -> SegmentHit:
    return SegmentHit(
        build_id="segments:test",
        segment_id=segment_id,
        evidence_id=f"evidence:{segment_id}",
        artifact_id=f"artifact:{segment_id}",
        locator="page:1",
        rule_name="board-ordinance-items",
        segment_type="agenda_item",
        anchor_text="TBD/2026",
        normalized_anchor="tbd/2026",
        raw_text=text,
        normalized_text=" ".join(text.split()).casefold(),
        text_sha256=f"sha:{segment_id}",
        char_start=char_start,
        char_end=char_start + len(text),
        sources=(
            {
                "source_id": f"source:{segment_id}",
                "source_uri": f"https://example.gov/{segment_id}",
                "source_name": "Board of Control — Fixture",
                "native_identifier": segment_id,
            },
        ),
    )


def test_same_change_order_resolves_to_same_matter_key() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    first = _hit(
        "Ordinance 71/2026\n"
        "Clarification to Change Order No. 8 with S.E.T., Inc. for the 11th St. Improvements "
        "Project, GP1144, which resulted in a net reduction in the amount of $1,476.56.",
        segment_id="first",
    )
    second = _hit(
        "Ordinance 69/2022\n"
        "Enter into Change Order No. 8 with S.E.T., Inc. for a cost reduction in the amount of "
        "$1,476.56 for the 11th St. SE Improvements Project, GP1144, resulting in a new contract amount.",
        segment_id="second",
    )

    first_result = resolve_segment(first, policy)
    second_result = resolve_segment(second, policy)

    assert first_result.status is MatterKeyStatus.RESOLVED
    assert second_result.status is MatterKeyStatus.RESOLVED
    assert first_result.matter_key == second_result.matter_key
    assert first_result.matter_key is not None
    assert first_result.component("project_id").normalized_value == "1144"
    assert first_result.component("change_order_number").normalized_value == "8"
    assert first_result.component("counterparty").normalized_value == "set inc"


def test_same_project_and_change_order_with_different_counterparties_do_not_join() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    northstar = _hit(
        "Ordinance TBD/2026\n"
        "Enter into Change Order No. 1 with Northstar Asphalt, Inc. in the amount of $172,509.75 "
        "for the Cleveland Ave. NW Paving Project, GP1283 due to casting adjustments.",
        segment_id="northstar",
    )
    omnipro = _hit(
        "Ordinance TBD/2026\n"
        "Enter into Change Order No. 1 with Omnipro Services, LLC in the amount of $14,989.00 "
        "for the Cleveland Ave. NW Paving Project, GP1283 due to an extended project duration.",
        segment_id="omnipro",
    )

    first = resolve_segment(northstar, policy)
    second = resolve_segment(omnipro, policy)
    assert first.status is MatterKeyStatus.RESOLVED
    assert second.status is MatterKeyStatus.RESOLVED
    assert first.matter_key != second.matter_key
    assert first.component("project_id").normalized_value == second.component("project_id").normalized_value == "1283"
    assert first.component("change_order_number").normalized_value == second.component("change_order_number").normalized_value == "1"
    assert first.component("counterparty").normalized_value != second.component("counterparty").normalized_value


def test_change_order_number_is_part_of_identity() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    one = _hit(
        "Ordinance 21/2025\nEnter into Change Order No. 1 with Clell Construction, LLC in the amount "
        "of $69,836.40 for the Fresh Mark Sanitary Sewer Replacement Project, GP1358.",
        segment_id="one",
    )
    two = _hit(
        "Ordinance 46/2026\nEnter into Change Order No. 2 & Final with Clell Construction, LLC in the amount "
        "of $30,350.00 for the Fresh Mark Sanitary Sewer Replacement Project, GP1358.",
        segment_id="two",
    )
    first = resolve_segment(one, policy)
    second = resolve_segment(two, policy)
    assert first.status is MatterKeyStatus.RESOLVED
    assert second.status is MatterKeyStatus.RESOLVED
    assert first.matter_key != second.matter_key


def test_multiple_project_ids_are_ambiguous_not_forced_into_a_key() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    segment = _hit(
        "Ordinance 121/2024\nEnter into a Change Order No. 1 with MKSK, Inc. in the amount of $7,650.00 "
        "for design services for the 6th St NW Utilities, GP1473 and Streetscape Projects, GP1445, "
        "due to additional surveying services.",
        segment_id="multi-project",
    )
    result = resolve_segment(segment, policy)
    assert result.status is MatterKeyStatus.AMBIGUOUS
    assert result.matter_key is None
    assert "multiple_project_ids" in result.reasons


def test_missing_project_id_is_insufficient_not_inferred() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    segment = _hit(
        "Ordinance TBD/2026\nEnter into Change Order No. 10 with Standard Plumbing and Heating in the amount "
        "of $10,796.67 for the Civic Center Infrastructure Project due to additional lighting.",
        segment_id="no-project-id",
    )
    result = resolve_segment(segment, policy)
    assert result.status is MatterKeyStatus.INSUFFICIENT_IDENTITY
    assert result.matter_key is None
    assert "missing_project_id" in result.reasons


def test_every_resolved_component_retains_exact_evidence_span() -> None:
    policy = load_matter_key_policy(POLICY_PATH)
    segment = _hit(
        "Ordinance 52/2026\nEnter into Change Order No. 4 with Arcadis U.S., Inc. in the amount of $126,154.00 "
        "for the W. Tuscarawas Corridor Safety Project, Phase 1, GP1165 for final design plans.",
        segment_id="spans",
        char_start=321,
    )
    result = resolve_segment(segment, policy)
    assert result.status is MatterKeyStatus.RESOLVED
    for component in result.components:
        relative_start = component.char_start - segment.char_start
        relative_end = component.char_end - segment.char_start
        assert segment.raw_text[relative_start:relative_end].strip() == component.raw_value
        assert segment.char_start <= component.char_start < component.char_end <= segment.char_end
        assert component.evidence_id == segment.evidence_id
        assert component.segment_id == segment.segment_id


def test_policy_contract_is_deterministic_and_validates_named_groups(tmp_path) -> None:
    first = load_matter_key_policy(POLICY_PATH)
    second = load_matter_key_policy(POLICY_PATH)
    assert first == second
    assert matter_key_policy_sha256(first) == matter_key_policy_sha256(second)

    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["project_id_regex"] = r"(?i)\bGP\s*\d{3,5}\b"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="named group 'project_id'"):
        load_matter_key_policy(bad)


def test_resolver_groups_only_fully_resolved_keys(tmp_path) -> None:
    state = tmp_path / "state"
    texts = (
        (
            "one",
            "Ordinance 71/2026\nClarification to Change Order No. 8 with S.E.T., Inc. for the "
            "11th St. Improvements Project, GP1144, which resulted in a net reduction.\n",
        ),
        (
            "two",
            "Ordinance 69/2022\nEnter into Change Order No. 8 with S.E.T., Inc. for a cost reduction in the "
            "amount of $1,476.56 for the 11th St. SE Improvements Project, GP1144.\n",
        ),
        (
            "three",
            "Ordinance 121/2024\nEnter into a Change Order No. 1 with MKSK, Inc. in the amount of $7,650.00 "
            "for utilities, GP1473 and streetscape, GP1445.\n",
        ),
    )
    for name, text in texts:
        path = tmp_path / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/{name}",
            source_name=f"Board of Control — {name}",
        )

    rule = SegmentationRule(
        name="board-ordinance-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^[ \t]*Ordinance[ \t]+(?P<anchor>(?:TBD(?:/\d{4})?|\d{1,4}/\d{4}))[ \t]*$",
        segment_type="agenda_item",
        min_chars=20,
    )
    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(rule,)))
    result = MatterKeyResolver(state).resolve(load_matter_key_policy(POLICY_PATH))

    assert result.candidate_count == 3
    assert result.resolved_count == 2
    assert result.ambiguous_count == 1
    assert result.insufficient_identity_count == 0
    assert result.repeated_group_count == 1
    assert result.repeated_groups[0].occurrence_count == 2
    assert all(candidate.status is MatterKeyStatus.RESOLVED for candidate in result.repeated_groups[0].candidates)
    assert "must not be joined" in " ".join(result.limitations)
