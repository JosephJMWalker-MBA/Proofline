from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofline import Ingestor
from proofline.financial_roles import (
    FinancialRolePolicy,
    FinancialRoleResolver,
    FinancialRoleRule,
    FinancialRoleStatus,
    financial_role_policy_sha256,
    load_financial_role_policy,
)
from proofline.matter_keys import load_matter_key_policy
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


MATTER_POLICY = Path("experiments/canton-2026/matter-key-policy.json")
FINANCIAL_POLICY = Path("experiments/canton-2026/financial-role-policy.json")


def _board_rule() -> SegmentationRule:
    return SegmentationRule(
        name="board-ordinance-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^[ \t]*Ordinance[ \t]+(?P<anchor>(?:TBD(?:/\d{4})?|\d{1,4}/\d{4}))[ \t]*$",
        segment_type="agenda_item",
        min_chars=20,
    )


def _build_state(tmp_path, texts: tuple[tuple[str, str], ...]):
    state = tmp_path / "state"
    for name, text in texts:
        path = tmp_path / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/{name}",
            source_name=f"Board of Control — {name}",
        )
    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(_board_rule(),)))
    StructuredIndex(state).rebuild()
    return state


def test_change_amount_and_resulting_total_are_assigned_but_never_pooled(tmp_path) -> None:
    state = _build_state(
        tmp_path,
        ((
            "one",
            "Ordinance 1/2026\n"
            "Enter into Change Order No. 1 with Example Construction, LLC in the amount of $10.00 "
            "for the Sample Project, GP1001, resulting in a new contract amount of $110.00.\n",
        ),),
    )
    result = FinancialRoleResolver(state).resolve(
        load_matter_key_policy(MATTER_POLICY),
        load_financial_role_policy(FINANCIAL_POLICY),
    )
    assert result.assignment_count == 2
    assert result.assigned_count == 2
    assert result.unknown_count == 0
    assert {item.field_role for item in result.assignments} == {
        "change_amount",
        "resulting_contract_total",
    }
    assert result.repeated_population_count == 0


def test_same_matter_same_role_repeats_but_different_role_is_separate_population(tmp_path) -> None:
    texts = (
        (
            "one",
            "Ordinance 1/2026\n"
            "Enter into Change Order No. 8 with S.E.T., Inc. in the amount of $1,476.56 "
            "for the 11th St Improvements Project, GP1144, resulting in a new contract amount of $500,000.00.\n",
        ),
        (
            "two",
            "Ordinance 2/2026\n"
            "Clarification to Change Order No. 8 with S.E.T., Inc. in the amount of $1,476.56 "
            "for the 11th St Improvements Project, GP1144, resulting in a new contract amount of $500,000.00.\n",
        ),
    )
    state = _build_state(tmp_path, texts)
    result = FinancialRoleResolver(state).resolve(
        load_matter_key_policy(MATTER_POLICY),
        load_financial_role_policy(FINANCIAL_POLICY),
    )
    assert result.repeated_population_count == 2
    assert {group.field_role for group in result.comparison_populations} == {
        "change_amount",
        "resulting_contract_total",
    }
    assert all(group.occurrence_count == 2 for group in result.comparison_populations)
    assert all(len(group.normalized_values) == 1 for group in result.comparison_populations)
    assert len({group.matter_key for group in result.comparison_populations}) == 1


def test_supporting_funding_amounts_remain_unknown_and_outside_populations(tmp_path) -> None:
    texts = (
        (
            "one",
            "Ordinance 1/2026\n"
            "Enter into Change Order No. 3 with Example Construction, LLC in the amount of $25.00 "
            "for the Sample Project, GP1002, funded by $50.00 in Federal Funds, "
            "resulting in a new contract amount of $125.00.\n",
        ),
        (
            "two",
            "Ordinance 2/2026\n"
            "Enter into Change Order No. 3 with Example Construction, LLC in the amount of $25.00 "
            "for the Sample Project, GP1002, funded by $75.00 in Federal Funds, "
            "resulting in a new contract amount of $125.00.\n",
        ),
    )
    state = _build_state(tmp_path, texts)
    result = FinancialRoleResolver(state).resolve(
        load_matter_key_policy(MATTER_POLICY),
        load_financial_role_policy(FINANCIAL_POLICY),
    )
    unknown = [item for item in result.assignments if item.status is FinancialRoleStatus.UNKNOWN]
    assert {item.normalized_value for item in unknown} == {"50.00", "75.00"}
    population_assignments = {
        item.assignment_id
        for population in result.comparison_populations
        for item in population.assignments
    }
    assert all(item.assignment_id not in population_assignments for item in unknown)


def test_competing_role_rules_make_amount_ambiguous(tmp_path) -> None:
    state = _build_state(
        tmp_path,
        ((
            "one",
            "Ordinance 1/2026\n"
            "Enter into Change Order No. 1 with Example Construction, LLC in the amount of $10.00 "
            "for the Sample Project, GP1003.\n",
        ),),
    )
    matter_policy = load_matter_key_policy(MATTER_POLICY)
    base = load_financial_role_policy(FINANCIAL_POLICY)
    change_rule = base.rules[0]
    policy = FinancialRolePolicy(
        name="ambiguous-fixture",
        matter_policy_name=matter_policy.name,
        rules=(
            change_rule,
            FinancialRoleRule(
                name="competing-role",
                field_role="other_amount",
                amount_regex=change_rule.amount_regex,
            ),
        ),
    )
    result = FinancialRoleResolver(state).resolve(matter_policy, policy)
    assert result.assignment_count == 1
    assert result.ambiguous_count == 1
    assert result.assigned_count == 0
    assert result.comparison_populations == ()


def test_different_matters_with_same_role_do_not_share_population(tmp_path) -> None:
    texts = (
        (
            "one",
            "Ordinance 1/2026\nEnter into Change Order No. 1 with Alpha Construction, LLC in the amount of $10.00 "
            "for Project Alpha, GP1004.\n",
        ),
        (
            "two",
            "Ordinance 2/2026\nEnter into Change Order No. 1 with Beta Construction, LLC in the amount of $10.00 "
            "for Project Beta, GP1005.\n",
        ),
    )
    state = _build_state(tmp_path, texts)
    result = FinancialRoleResolver(state).resolve(
        load_matter_key_policy(MATTER_POLICY),
        load_financial_role_policy(FINANCIAL_POLICY),
    )
    assert result.assigned_count == 2
    assert result.repeated_population_count == 0
    assert len({item.matter_key for item in result.assignments}) == 2


def test_assignment_spans_match_structured_money_and_ids_survive_rebuild(tmp_path) -> None:
    texts = (
        (
            "one",
            "Ordinance 1/2026\nEnter into Change Order No. 4 with Arcadis U.S., Inc. in the amount of $126,154.00 "
            "for the W. Tuscarawas Corridor Safety Project, GP1165, resulting in a new contract price of $3,211,678.00.\n",
        ),
        (
            "two",
            "Ordinance 2/2026\nEnter into Change Order No. 4 with Arcadis U.S., Inc. in the amount of $126,154.00 "
            "for the W. Tuscarawas Corridor Safety Project, GP1165, resulting in a new contract price of $3,211,678.00.\n",
        ),
    )
    state = _build_state(tmp_path, texts)
    matter_policy = load_matter_key_policy(MATTER_POLICY)
    financial_policy = load_financial_role_policy(FINANCIAL_POLICY)
    resolver = FinancialRoleResolver(state)
    first = resolver.resolve(matter_policy, financial_policy)
    first_ids = {
        (item.evidence_id, item.char_start, item.char_end, item.normalized_value): item.assignment_id
        for item in first.assignments
    }
    first_populations = {population.population_id for population in first.comparison_populations}

    with resolver.segments.store.connection() as connection:
        evidence_text = {
            row["evidence_id"]: row["extracted_text"]
            for row in connection.execute(
                """
                SELECT eu.evidence_id, best.extracted_text
                FROM evidence_units eu
                JOIN evidence_extractions best ON best.extraction_id = (
                    SELECT ee.extraction_id FROM evidence_extractions ee
                    WHERE ee.evidence_id = eu.evidence_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC, ee.occurred_at DESC, ee.rowid DESC
                    LIMIT 1
                )
                """
            ).fetchall()
        }
    for item in first.assignments:
        assert evidence_text[item.evidence_id][item.char_start:item.char_end] == item.raw_value

    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(_board_rule(),)))
    second = FinancialRoleResolver(state).resolve(matter_policy, financial_policy)
    second_ids = {
        (item.evidence_id, item.char_start, item.char_end, item.normalized_value): item.assignment_id
        for item in second.assignments
    }
    second_populations = {population.population_id for population in second.comparison_populations}

    assert first.structured_build_id != second.structured_build_id
    assert first_ids == second_ids
    assert first_populations == second_populations


def test_financial_policy_is_deterministic_and_requires_amount_group(tmp_path) -> None:
    first = load_financial_role_policy(FINANCIAL_POLICY)
    second = load_financial_role_policy(FINANCIAL_POLICY)
    assert first == second
    assert financial_role_policy_sha256(first) == financial_role_policy_sha256(second)

    payload = json.loads(FINANCIAL_POLICY.read_text(encoding="utf-8"))
    payload["rules"][0]["amount_regex"] = r"(?i)in the amount of \$\d+"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="named group 'amount'"):
        load_financial_role_policy(bad)
