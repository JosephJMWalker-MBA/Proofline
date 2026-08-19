"""Deterministic conflicting-value candidates over authorized financial populations.

This detector never compares raw money facts directly. It consumes comparison populations that
have already passed both matter-identity and financial-role gates. A candidate means only that
one authorized population contains more than one normalized value.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..financial_roles import FinancialComparisonPopulation, FinancialRoleResult
from ..hashing import stable_id

_METHOD = "same_matter_financial_value_conflict/v1"


@dataclass(frozen=True, slots=True)
class FinancialConflictCandidate:
    candidate_id: str
    method: str
    population_id: str
    matter_key: str
    field_role: str
    occurrence_count: int
    evidence_count: int
    artifact_count: int
    normalized_values: tuple[str, ...]
    population: FinancialComparisonPopulation
    description: str
    possible_ordinary_explanations: tuple[str, ...]
    questions_worth_asking: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["normalized_values"] = list(self.normalized_values)
        payload["population"] = self.population.to_dict()
        payload["possible_ordinary_explanations"] = list(self.possible_ordinary_explanations)
        payload["questions_worth_asking"] = list(self.questions_worth_asking)
        payload["limitations"] = list(self.limitations)
        return payload


@dataclass(frozen=True, slots=True)
class FinancialConflictResult:
    method: str
    inspected_population_count: int
    candidate_count: int
    candidates: tuple[FinancialConflictCandidate, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "inspected_population_count": self.inspected_population_count,
            "candidate_count": self.candidate_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "limitations": list(self.limitations),
        }


def evaluate_financial_population(
    population: FinancialComparisonPopulation,
) -> FinancialConflictCandidate | None:
    """Return a descriptive candidate only when one authorized population has distinct values."""
    if population.occurrence_count < 2:
        return None
    values = tuple(sorted({assignment.normalized_value for assignment in population.assignments}))
    if len(values) < 2:
        return None

    assignment_ids = tuple(sorted(assignment.assignment_id for assignment in population.assignments))
    candidate_id = stable_id(
        "financial-conflict-candidate",
        _METHOD,
        population.population_id,
        *assignment_ids,
        *values,
    )
    return FinancialConflictCandidate(
        candidate_id=candidate_id,
        method=_METHOD,
        population_id=population.population_id,
        matter_key=population.matter_key,
        field_role=population.field_role,
        occurrence_count=population.occurrence_count,
        evidence_count=population.evidence_count,
        artifact_count=population.artifact_count,
        normalized_values=values,
        population=population,
        description=(
            f"The same resolved matter and financial role ({population.field_role}) contain "
            f"{len(values)} distinct normalized USD values across {population.occurrence_count} "
            "evidence-bound occurrences."
        ),
        possible_ordinary_explanations=(
            "A later record may amend, correct, or supersede an earlier amount.",
            "The records may reflect different publication times or administrative stages even though the current matter/role policy groups them.",
            "The source may contain a transcription, formatting, or extraction discrepancy that should be checked against the original pages.",
            "The active matter or field-role policy may be too coarse for this specific record pattern and may need refinement.",
        ),
        questions_worth_asking=(
            "Do publisher chronology or version relations establish which record came first?",
            "Does the surrounding source language confirm that each value has the same semantic field role?",
            "Is there an amendment, correction, change authorization, or other record that explains the difference?",
            "Do the original source pages visually confirm both monetary values?",
        ),
        limitations=(
            "Different values do not establish that either value is erroneous.",
            "This detector does not infer chronology, increase/decrease direction, suspiciousness, intent, or wrongdoing.",
            "The candidate remains bounded to the exact matter key, financial role, and evidence assignments in the comparison population.",
        ),
    )


def detect_financial_conflicts(result: FinancialRoleResult) -> FinancialConflictResult:
    candidates = tuple(
        candidate
        for population in result.comparison_populations
        if (candidate := evaluate_financial_population(population)) is not None
    )
    return FinancialConflictResult(
        method=_METHOD,
        inspected_population_count=len(result.comparison_populations),
        candidate_count=len(candidates),
        candidates=candidates,
        limitations=(
            "Only repeated populations already authorized by matter-key and financial-role policies are inspected.",
            "Equal repeated values intentionally produce no candidate.",
            "Unknown and ambiguous financial facts are absent because they are never admitted to comparison populations.",
            "A candidate is a discrepancy for human investigation, not a conclusion about error or wrongdoing.",
        ),
    )
