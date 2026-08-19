from __future__ import annotations

from proofline.detectors.financial_conflict import (
    detect_financial_conflicts,
    evaluate_financial_population,
)
from proofline.financial_roles import (
    FinancialComparisonPopulation,
    FinancialFieldAssignment,
    FinancialRoleResult,
    FinancialRoleStatus,
)


def _assignment(
    name: str,
    *,
    matter_key: str = "matter:one",
    field_role: str = "change_amount",
    value: str = "10.00",
    offset: int = 10,
) -> FinancialFieldAssignment:
    return FinancialFieldAssignment(
        assignment_id=f"assignment:{name}",
        policy_name="financial-policy",
        policy_sha256="policy-sha",
        status=FinancialRoleStatus.ASSIGNED,
        field_role=field_role,
        matched_rule_names=("fixture-rule",),
        matter_key=matter_key,
        matter_candidate_id=f"matter-candidate:{name}",
        evidence_id=f"evidence:{name}",
        artifact_id=f"artifact:{name}",
        locator="page:1",
        segment_id=f"segment:{name}",
        raw_value=f"${value}",
        normalized_value=value,
        numeric_value=float(value),
        unit="USD",
        char_start=offset,
        char_end=offset + len(value) + 1,
        reasons=(),
        sources=(
            {
                "source_id": f"source:{name}",
                "source_uri": f"https://example.gov/{name}",
                "source_name": f"Fixture {name}",
                "native_identifier": name,
            },
        ),
    )


def _population(
    *assignments: FinancialFieldAssignment,
    population_id: str = "population:one",
    matter_key: str = "matter:one",
    field_role: str = "change_amount",
) -> FinancialComparisonPopulation:
    return FinancialComparisonPopulation(
        population_id=population_id,
        matter_key=matter_key,
        field_role=field_role,
        occurrence_count=len(assignments),
        evidence_count=len({item.evidence_id for item in assignments}),
        artifact_count=len({item.artifact_id for item in assignments}),
        normalized_values=tuple(sorted({item.normalized_value for item in assignments})),
        assignments=tuple(assignments),
    )


def _result(*populations: FinancialComparisonPopulation) -> FinancialRoleResult:
    assignments = tuple(item for population in populations for item in population.assignments)
    return FinancialRoleResult(
        method="proofline-financial-role/v1",
        policy_name="financial-policy",
        policy_sha256="policy-sha",
        matter_policy_name="matter-policy",
        structured_build_id="structured:fixture",
        assignment_count=len(assignments),
        assigned_count=len(assignments),
        ambiguous_count=0,
        unknown_count=0,
        role_counts=(("change_amount", len(assignments)),),
        repeated_population_count=len(populations),
        assignments=assignments,
        comparison_populations=tuple(populations),
        limitations=(),
    )


def test_same_matter_same_role_with_different_values_emits_candidate() -> None:
    population = _population(
        _assignment("a", value="10.00"),
        _assignment("b", value="12.00", offset=30),
    )
    candidate = evaluate_financial_population(population)
    assert candidate is not None
    assert candidate.matter_key == "matter:one"
    assert candidate.field_role == "change_amount"
    assert candidate.normalized_values == ("10.00", "12.00")
    assert candidate.population == population
    assert candidate.occurrence_count == 2
    assert candidate.evidence_count == 2
    assert candidate.artifact_count == 2
    assert candidate.possible_ordinary_explanations
    assert candidate.questions_worth_asking
    assert candidate.limitations
    assert "does not infer chronology" in " ".join(candidate.limitations)


def test_equal_repeated_values_emit_no_candidate() -> None:
    population = _population(
        _assignment("a", value="10.00"),
        _assignment("b", value="10.00", offset=30),
    )
    assert evaluate_financial_population(population) is None
    result = detect_financial_conflicts(_result(population))
    assert result.inspected_population_count == 1
    assert result.candidate_count == 0
    assert result.candidates == ()


def test_detector_never_crosses_matter_or_field_population_boundaries() -> None:
    first = _population(
        _assignment("a1", matter_key="matter:a", value="10.00"),
        _assignment("a2", matter_key="matter:a", value="10.00", offset=30),
        population_id="population:a",
        matter_key="matter:a",
    )
    second = _population(
        _assignment(
            "b1",
            matter_key="matter:b",
            field_role="resulting_contract_total",
            value="12.00",
        ),
        _assignment(
            "b2",
            matter_key="matter:b",
            field_role="resulting_contract_total",
            value="12.00",
            offset=30,
        ),
        population_id="population:b",
        matter_key="matter:b",
        field_role="resulting_contract_total",
    )
    result = detect_financial_conflicts(_result(first, second))
    assert result.inspected_population_count == 2
    assert result.candidate_count == 0


def test_candidate_identity_is_stable_for_same_evidence_set_regardless_of_order() -> None:
    a = _assignment("a", value="10.00")
    b = _assignment("b", value="12.00", offset=30)
    first = evaluate_financial_population(_population(a, b))
    second = evaluate_financial_population(_population(b, a))
    assert first is not None and second is not None
    assert first.candidate_id == second.candidate_id
    assert first.normalized_values == second.normalized_values


def test_candidate_identity_changes_when_population_evidence_changes() -> None:
    a = _assignment("a", value="10.00")
    b = _assignment("b", value="12.00", offset=30)
    c = _assignment("c", value="12.00", offset=50)
    first = evaluate_financial_population(_population(a, b))
    second = evaluate_financial_population(_population(a, b, c))
    assert first is not None and second is not None
    assert first.candidate_id != second.candidate_id


def test_result_retains_complete_authorized_population_and_no_scalar_score() -> None:
    population = _population(
        _assignment("a", value="100.00"),
        _assignment("b", value="125.00", offset=40),
    )
    result = detect_financial_conflicts(_result(population))
    payload = result.to_dict()
    assert payload["candidate_count"] == 1
    candidate = payload["candidates"][0]
    assert candidate["population"]["population_id"] == population.population_id
    assert len(candidate["population"]["assignments"]) == 2
    assert "score" not in candidate
    assert "suspicious" not in candidate["description"].casefold()
    assert "wrongdoing" in " ".join(candidate["limitations"]).casefold()
