"""Deterministic financial field-role assignment for comparable numeric populations.

Matter identity is necessary but not sufficient for numeric comparison. This module assigns
semantic roles only when a policy rule matches the exact structured-money span inside a resolved
matter segment. Unknown or ambiguous values remain outside comparison populations.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from .hashing import sha256_text, stable_id
from .matter_keys import MatterKeyCandidate, MatterKeyPolicy, MatterKeyResolver, MatterKeyStatus
from .segments import SegmentHit, SegmentIndex
from .structured import StructuredIndex

_POLICY_SCHEMA = "proofline-financial-role-policy/v1"
_METHOD = "proofline-financial-role/v1"


class FinancialRoleStatus(str, Enum):
    ASSIGNED = "assigned"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FinancialRoleRule:
    name: str
    field_role: str
    amount_regex: str


@dataclass(frozen=True, slots=True)
class FinancialRolePolicy:
    name: str
    matter_policy_name: str
    rules: tuple[FinancialRoleRule, ...]
    schema: str = _POLICY_SCHEMA


@dataclass(frozen=True, slots=True)
class FinancialFieldAssignment:
    assignment_id: str
    policy_name: str
    policy_sha256: str
    status: FinancialRoleStatus
    field_role: str | None
    matched_rule_names: tuple[str, ...]
    matter_key: str
    matter_candidate_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    segment_id: str
    raw_value: str
    normalized_value: str
    numeric_value: float
    unit: str
    char_start: int
    char_end: int
    reasons: tuple[str, ...]
    sources: tuple[dict, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["matched_rule_names"] = list(self.matched_rule_names)
        payload["reasons"] = list(self.reasons)
        payload["sources"] = list(self.sources)
        return payload


@dataclass(frozen=True, slots=True)
class FinancialComparisonPopulation:
    population_id: str
    matter_key: str
    field_role: str
    occurrence_count: int
    evidence_count: int
    artifact_count: int
    normalized_values: tuple[str, ...]
    assignments: tuple[FinancialFieldAssignment, ...]

    def to_dict(self) -> dict:
        return {
            "population_id": self.population_id,
            "matter_key": self.matter_key,
            "field_role": self.field_role,
            "occurrence_count": self.occurrence_count,
            "evidence_count": self.evidence_count,
            "artifact_count": self.artifact_count,
            "normalized_values": list(self.normalized_values),
            "assignments": [assignment.to_dict() for assignment in self.assignments],
        }


@dataclass(frozen=True, slots=True)
class FinancialRoleResult:
    method: str
    policy_name: str
    policy_sha256: str
    matter_policy_name: str
    structured_build_id: str
    assignment_count: int
    assigned_count: int
    ambiguous_count: int
    unknown_count: int
    role_counts: tuple[tuple[str, int], ...]
    repeated_population_count: int
    assignments: tuple[FinancialFieldAssignment, ...]
    comparison_populations: tuple[FinancialComparisonPopulation, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "policy_name": self.policy_name,
            "policy_sha256": self.policy_sha256,
            "matter_policy_name": self.matter_policy_name,
            "structured_build_id": self.structured_build_id,
            "assignment_count": self.assignment_count,
            "assigned_count": self.assigned_count,
            "ambiguous_count": self.ambiguous_count,
            "unknown_count": self.unknown_count,
            "role_counts": {role: count for role, count in self.role_counts},
            "repeated_population_count": self.repeated_population_count,
            "assignments": [assignment.to_dict() for assignment in self.assignments],
            "comparison_populations": [population.to_dict() for population in self.comparison_populations],
            "limitations": list(self.limitations),
        }


def _compile_rule(rule: FinancialRoleRule) -> re.Pattern[str]:
    try:
        pattern = re.compile(rule.amount_regex, re.MULTILINE)
    except re.error as exc:
        raise ValueError(f"invalid amount_regex for rule {rule.name!r}: {exc}") from exc
    if "amount" not in pattern.groupindex:
        raise ValueError(f"amount_regex for rule {rule.name!r} must define named group 'amount'")
    if pattern.search("") is not None:
        raise ValueError(f"amount_regex for rule {rule.name!r} must not match empty text")
    return pattern


def _canonical_policy_payload(policy: FinancialRolePolicy) -> dict:
    return {
        "schema": policy.schema,
        "name": policy.name,
        "matter_policy_name": policy.matter_policy_name,
        "rules": [asdict(rule) for rule in policy.rules],
    }


def financial_role_policy_sha256(policy: FinancialRolePolicy) -> str:
    serialized = json.dumps(_canonical_policy_payload(policy), sort_keys=True, separators=(",", ":"))
    return sha256_text(serialized)


def load_financial_role_policy(path: str | Path) -> FinancialRolePolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _POLICY_SCHEMA:
        raise ValueError(f"financial-role schema must be {_POLICY_SCHEMA!r}")
    name = payload.get("name")
    matter_policy_name = payload.get("matter_policy_name")
    raw_rules = payload.get("rules")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("financial-role policy name must be a non-empty string")
    if not isinstance(matter_policy_name, str) or not matter_policy_name.strip():
        raise ValueError("matter_policy_name must be a non-empty string")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("financial-role policy requires at least one rule")

    rules: list[FinancialRoleRule] = []
    seen_names: set[str] = set()
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("each financial-role rule must be an object")
        rule_name = raw.get("name")
        field_role = raw.get("field_role")
        amount_regex = raw.get("amount_regex")
        if not isinstance(rule_name, str) or not rule_name.strip():
            raise ValueError("financial-role rule name must be a non-empty string")
        if rule_name in seen_names:
            raise ValueError(f"duplicate financial-role rule name: {rule_name}")
        seen_names.add(rule_name)
        if not isinstance(field_role, str) or not field_role.strip():
            raise ValueError(f"rule {rule_name!r} field_role must be a non-empty string")
        if not isinstance(amount_regex, str) or not amount_regex:
            raise ValueError(f"rule {rule_name!r} amount_regex must be a non-empty string")
        rule = FinancialRoleRule(
            name=rule_name.strip(),
            field_role=field_role.strip(),
            amount_regex=amount_regex,
        )
        _compile_rule(rule)
        rules.append(rule)

    return FinancialRolePolicy(
        name=name.strip(),
        matter_policy_name=matter_policy_name.strip(),
        rules=tuple(rules),
    )


def _segments_for_rule(index: SegmentIndex, rule_name: str) -> dict[str, SegmentHit]:
    build = index.current_build()
    if build is None:
        raise RuntimeError("segment index has not been built")
    with index.store.connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM evidence_segments
            WHERE build_id = ? AND rule_name = ?
            ORDER BY evidence_id, char_start, segment_id
            """,
            (build["build_id"], rule_name),
        ).fetchall()
    return {row["segment_id"]: index._hit(row) for row in rows}


def _money_rows_for_segment(
    structured: StructuredIndex,
    segment: SegmentHit,
) -> tuple[dict, ...]:
    build = structured.current_build()
    if build is None:
        raise RuntimeError("structured index has not been built")
    with structured.store.connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM evidence_facts
            WHERE build_id = ?
              AND evidence_id = ?
              AND fact_type = 'money'
              AND char_start IS NOT NULL
              AND char_end IS NOT NULL
              AND char_start >= ?
              AND char_end <= ?
            ORDER BY char_start, char_end, normalized_text
            """,
            (build["build_id"], segment.evidence_id, segment.char_start, segment.char_end),
        ).fetchall()
    return tuple(dict(row) for row in rows)


def _matched_rules(
    segment: SegmentHit,
    *,
    fact_start: int,
    fact_end: int,
    rules: tuple[tuple[FinancialRoleRule, re.Pattern[str]], ...],
) -> tuple[FinancialRoleRule, ...]:
    matches: list[FinancialRoleRule] = []
    relative_fact = (fact_start - segment.char_start, fact_end - segment.char_start)
    for rule, pattern in rules:
        for match in pattern.finditer(segment.raw_text):
            start, end = match.span("amount")
            if (start, end) == relative_fact:
                matches.append(rule)
    return tuple(matches)


def _assignment(
    *,
    policy: FinancialRolePolicy,
    matter: MatterKeyCandidate,
    segment: SegmentHit,
    fact: dict,
    matched: tuple[FinancialRoleRule, ...],
) -> FinancialFieldAssignment:
    policy_sha = financial_role_policy_sha256(policy)
    roles = {rule.field_role for rule in matched}
    if not matched:
        status = FinancialRoleStatus.UNKNOWN
        field_role = None
        reasons = ("no_financial_role_rule_matches_exact_money_span",)
    elif len(roles) == 1 and len(matched) == 1:
        status = FinancialRoleStatus.ASSIGNED
        field_role = next(iter(roles))
        reasons = ()
    else:
        status = FinancialRoleStatus.AMBIGUOUS
        field_role = None
        reasons = ("multiple_financial_role_rules_match_exact_money_span",)

    normalized_value = str(fact["normalized_text"])
    char_start = int(fact["char_start"])
    char_end = int(fact["char_end"])
    assignment_id = stable_id(
        "financial-field-assignment",
        policy_sha,
        matter.matter_key or "",
        segment.evidence_id,
        str(char_start),
        str(char_end),
        normalized_value,
        status.value,
        field_role or "",
    )
    return FinancialFieldAssignment(
        assignment_id=assignment_id,
        policy_name=policy.name,
        policy_sha256=policy_sha,
        status=status,
        field_role=field_role,
        matched_rule_names=tuple(rule.name for rule in matched),
        matter_key=matter.matter_key or "",
        matter_candidate_id=matter.candidate_id,
        evidence_id=segment.evidence_id,
        artifact_id=segment.artifact_id,
        locator=segment.locator,
        segment_id=segment.segment_id,
        raw_value=str(fact["raw_text"]),
        normalized_value=normalized_value,
        numeric_value=float(fact["numeric_value"]),
        unit=str(fact["unit"] or ""),
        char_start=char_start,
        char_end=char_end,
        reasons=reasons,
        sources=segment.sources,
    )


class FinancialRoleResolver:
    """Assign financial roles inside fully resolved matter-key candidates."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.segments = SegmentIndex(state_dir)
        self.structured = StructuredIndex(state_dir)

    def resolve(
        self,
        matter_policy: MatterKeyPolicy,
        financial_policy: FinancialRolePolicy,
    ) -> FinancialRoleResult:
        if financial_policy.matter_policy_name != matter_policy.name:
            raise ValueError(
                "financial-role policy matter_policy_name does not match the active matter-key policy"
            )
        structured_build = self.structured.current_build()
        if structured_build is None:
            raise RuntimeError("structured index has not been built")

        matter_result = MatterKeyResolver(self.state_dir).resolve(matter_policy)
        segment_map = _segments_for_rule(self.segments, matter_policy.segment_rule_name)
        compiled_rules = tuple((rule, _compile_rule(rule)) for rule in financial_policy.rules)
        assignments: list[FinancialFieldAssignment] = []

        for matter in matter_result.candidates:
            if matter.status is not MatterKeyStatus.RESOLVED or matter.matter_key is None:
                continue
            segment = segment_map[matter.segment_id]
            for fact in _money_rows_for_segment(self.structured, segment):
                matched = _matched_rules(
                    segment,
                    fact_start=int(fact["char_start"]),
                    fact_end=int(fact["char_end"]),
                    rules=compiled_rules,
                )
                assignments.append(
                    _assignment(
                        policy=financial_policy,
                        matter=matter,
                        segment=segment,
                        fact=fact,
                        matched=matched,
                    )
                )

        assignments.sort(key=lambda item: (item.matter_key, item.field_role or "", item.evidence_id, item.char_start))
        assigned = tuple(item for item in assignments if item.status is FinancialRoleStatus.ASSIGNED)
        ambiguous = tuple(item for item in assignments if item.status is FinancialRoleStatus.AMBIGUOUS)
        unknown = tuple(item for item in assignments if item.status is FinancialRoleStatus.UNKNOWN)

        role_counts_map: dict[str, int] = {}
        grouped: dict[tuple[str, str], list[FinancialFieldAssignment]] = {}
        for item in assigned:
            assert item.field_role is not None
            role_counts_map[item.field_role] = role_counts_map.get(item.field_role, 0) + 1
            grouped.setdefault((item.matter_key, item.field_role), []).append(item)

        policy_sha = financial_role_policy_sha256(financial_policy)
        populations = tuple(
            FinancialComparisonPopulation(
                population_id=stable_id(
                    "financial-comparison-population", policy_sha, matter_key, field_role
                ),
                matter_key=matter_key,
                field_role=field_role,
                occurrence_count=len(items),
                evidence_count=len({item.evidence_id for item in items}),
                artifact_count=len({item.artifact_id for item in items}),
                normalized_values=tuple(sorted({item.normalized_value for item in items})),
                assignments=tuple(items),
            )
            for (matter_key, field_role), items in sorted(grouped.items())
            if len(items) >= 2
        )

        return FinancialRoleResult(
            method=_METHOD,
            policy_name=financial_policy.name,
            policy_sha256=policy_sha,
            matter_policy_name=matter_policy.name,
            structured_build_id=str(structured_build["build_id"]),
            assignment_count=len(assignments),
            assigned_count=len(assigned),
            ambiguous_count=len(ambiguous),
            unknown_count=len(unknown),
            role_counts=tuple(sorted(role_counts_map.items())),
            repeated_population_count=len(populations),
            assignments=tuple(assignments),
            comparison_populations=populations,
            limitations=(
                "Financial role assignment applies only inside resolved matter-key candidates.",
                "Unknown and ambiguous amounts are excluded from comparison populations.",
                "A comparison population requires the same resolved matter key and the same semantic field role.",
                "This layer does not assign suspiciousness, infer causation, or infer wrongdoing.",
                "Cross-matter outlier comparison is not authorized by this policy.",
            ),
        )
