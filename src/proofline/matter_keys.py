"""Deterministic, evidence-backed matter identity candidates.

Matter keys are derived comparison guards, not source evidence and not claims of wrongdoing.
A key is emitted only when a source/profile-specific policy supplies all required identity
components without ambiguity. Missing or conflicting identity components remain explicit.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from .hashing import sha256_text, stable_id
from .segments import SegmentHit, SegmentIndex

_POLICY_SCHEMA = "proofline-matter-key-policy/v1"
_METHOD = "proofline-matter-key/v1"


class MatterKeyStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_IDENTITY = "insufficient_identity"


@dataclass(frozen=True, slots=True)
class MatterKeyResolverRule:
    name: str
    transaction_role: str
    identity_regex: str
    required_components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatterKeyPolicy:
    name: str
    segment_rule_name: str
    project_id_regex: str
    resolvers: tuple[MatterKeyResolverRule, ...]
    schema: str = _POLICY_SCHEMA


@dataclass(frozen=True, slots=True)
class MatterKeyComponent:
    role: str
    raw_value: str
    normalized_value: str
    evidence_id: str
    segment_id: str
    char_start: int
    char_end: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MatterKeyCandidate:
    candidate_id: str
    policy_name: str
    policy_sha256: str
    status: MatterKeyStatus
    matter_key: str | None
    resolver_name: str | None
    segment_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    rule_name: str
    anchor_text: str
    components: tuple[MatterKeyComponent, ...]
    reasons: tuple[str, ...]
    sources: tuple[dict, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["components"] = [component.to_dict() for component in self.components]
        payload["reasons"] = list(self.reasons)
        payload["sources"] = list(self.sources)
        return payload

    def component(self, role: str) -> MatterKeyComponent | None:
        for component in self.components:
            if component.role == role:
                return component
        return None


@dataclass(frozen=True, slots=True)
class MatterKeyGroup:
    matter_key: str
    occurrence_count: int
    evidence_count: int
    artifact_count: int
    candidates: tuple[MatterKeyCandidate, ...]

    def to_dict(self) -> dict:
        return {
            "matter_key": self.matter_key,
            "occurrence_count": self.occurrence_count,
            "evidence_count": self.evidence_count,
            "artifact_count": self.artifact_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class MatterKeyResult:
    method: str
    policy_name: str
    policy_sha256: str
    segment_build_id: str
    candidate_count: int
    resolved_count: int
    ambiguous_count: int
    insufficient_identity_count: int
    repeated_group_count: int
    candidates: tuple[MatterKeyCandidate, ...]
    repeated_groups: tuple[MatterKeyGroup, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "policy_name": self.policy_name,
            "policy_sha256": self.policy_sha256,
            "segment_build_id": self.segment_build_id,
            "candidate_count": self.candidate_count,
            "resolved_count": self.resolved_count,
            "ambiguous_count": self.ambiguous_count,
            "insufficient_identity_count": self.insufficient_identity_count,
            "repeated_group_count": self.repeated_group_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "repeated_groups": [group.to_dict() for group in self.repeated_groups],
            "limitations": list(self.limitations),
        }


def _compile(pattern: str, *, label: str) -> re.Pattern[str]:
    try:
        compiled = re.compile(pattern, re.MULTILINE)
    except re.error as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if compiled.search("") is not None:
        raise ValueError(f"{label} must not match empty text")
    return compiled


def _canonical_policy_payload(policy: MatterKeyPolicy) -> dict:
    return {
        "schema": policy.schema,
        "name": policy.name,
        "segment_rule_name": policy.segment_rule_name,
        "project_id_regex": policy.project_id_regex,
        "resolvers": [asdict(rule) for rule in policy.resolvers],
    }


def matter_key_policy_sha256(policy: MatterKeyPolicy) -> str:
    serialized = json.dumps(_canonical_policy_payload(policy), sort_keys=True, separators=(",", ":"))
    return sha256_text(serialized)


def load_matter_key_policy(path: str | Path) -> MatterKeyPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _POLICY_SCHEMA:
        raise ValueError(f"matter-key schema must be {_POLICY_SCHEMA!r}")

    name = payload.get("name")
    segment_rule_name = payload.get("segment_rule_name")
    project_id_regex = payload.get("project_id_regex")
    raw_resolvers = payload.get("resolvers")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("matter-key policy name must be a non-empty string")
    if not isinstance(segment_rule_name, str) or not segment_rule_name.strip():
        raise ValueError("segment_rule_name must be a non-empty string")
    if not isinstance(project_id_regex, str) or not project_id_regex:
        raise ValueError("project_id_regex must be a non-empty string")
    if not isinstance(raw_resolvers, list) or not raw_resolvers:
        raise ValueError("matter-key policy requires at least one resolver")

    project_pattern = _compile(project_id_regex, label="project_id_regex")
    if "project_id" not in project_pattern.groupindex:
        raise ValueError("project_id_regex must define named group 'project_id'")

    resolvers: list[MatterKeyResolverRule] = []
    seen_names: set[str] = set()
    for raw in raw_resolvers:
        if not isinstance(raw, dict):
            raise ValueError("each matter-key resolver must be an object")
        rule_name = raw.get("name")
        transaction_role = raw.get("transaction_role")
        identity_regex = raw.get("identity_regex")
        required = raw.get("required_components")
        if not isinstance(rule_name, str) or not rule_name.strip():
            raise ValueError("resolver name must be a non-empty string")
        if rule_name in seen_names:
            raise ValueError(f"duplicate matter-key resolver name: {rule_name}")
        seen_names.add(rule_name)
        if not isinstance(transaction_role, str) or not transaction_role.strip():
            raise ValueError(f"resolver {rule_name!r} transaction_role must be non-empty")
        if not isinstance(identity_regex, str) or not identity_regex:
            raise ValueError(f"resolver {rule_name!r} identity_regex must be non-empty")
        if not isinstance(required, list) or not required or not all(isinstance(item, str) for item in required):
            raise ValueError(f"resolver {rule_name!r} required_components must be a non-empty string list")

        identity_pattern = _compile(identity_regex, label=f"resolver {rule_name!r} identity_regex")
        group_names = set(identity_pattern.groupindex)
        if "role_anchor" not in group_names:
            raise ValueError(f"resolver {rule_name!r} identity_regex must define named group 'role_anchor'")
        for component in required:
            if component in {"project_id", "transaction_role"}:
                continue
            if component not in group_names:
                raise ValueError(
                    f"resolver {rule_name!r} requires component {component!r} but identity_regex has no named group"
                )

        resolvers.append(
            MatterKeyResolverRule(
                name=rule_name.strip(),
                transaction_role=transaction_role.strip(),
                identity_regex=identity_regex,
                required_components=tuple(required),
            )
        )

    return MatterKeyPolicy(
        name=name.strip(),
        segment_rule_name=segment_rule_name.strip(),
        project_id_regex=project_id_regex,
        resolvers=tuple(resolvers),
    )


def _normalize_party(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = text.replace("&", " and ").replace(".", "")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _normalize_component(role: str, value: str) -> str:
    if role in {"project_id", "change_order_number"}:
        digits = "".join(character for character in value if character.isdigit())
        return str(int(digits)) if digits else ""
    if role == "counterparty":
        return _normalize_party(value)
    if role == "transaction_role":
        return "_".join(value.casefold().split())
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _component_from_group(
    segment: SegmentHit,
    match: re.Match[str],
    *,
    group_name: str,
    role: str,
    normalized_override: str | None = None,
) -> MatterKeyComponent:
    start, end = match.span(group_name)
    raw_value = match.group(group_name).strip()
    return MatterKeyComponent(
        role=role,
        raw_value=raw_value,
        normalized_value=(normalized_override if normalized_override is not None else _normalize_component(role, raw_value)),
        evidence_id=segment.evidence_id,
        segment_id=segment.segment_id,
        char_start=segment.char_start + start,
        char_end=segment.char_start + end,
    )


def resolve_segment(segment: SegmentHit, policy: MatterKeyPolicy) -> MatterKeyCandidate:
    policy_sha = matter_key_policy_sha256(policy)
    candidate_id = stable_id("matter-key-candidate", policy_sha, segment.segment_id)
    reasons: list[str] = []
    components: list[MatterKeyComponent] = []

    if segment.rule_name != policy.segment_rule_name:
        return MatterKeyCandidate(
            candidate_id=candidate_id,
            policy_name=policy.name,
            policy_sha256=policy_sha,
            status=MatterKeyStatus.INSUFFICIENT_IDENTITY,
            matter_key=None,
            resolver_name=None,
            segment_id=segment.segment_id,
            evidence_id=segment.evidence_id,
            artifact_id=segment.artifact_id,
            locator=segment.locator,
            rule_name=segment.rule_name,
            anchor_text=segment.anchor_text,
            components=(),
            reasons=("segment_rule_not_in_policy_scope",),
            sources=segment.sources,
        )

    project_pattern = _compile(policy.project_id_regex, label="project_id_regex")
    project_matches = list(project_pattern.finditer(segment.raw_text))
    normalized_projects: dict[str, list[re.Match[str]]] = {}
    for match in project_matches:
        normalized = _normalize_component("project_id", match.group("project_id"))
        if normalized:
            normalized_projects.setdefault(normalized, []).append(match)

    if not normalized_projects:
        reasons.append("missing_project_id")
    elif len(normalized_projects) > 1:
        reasons.append("multiple_project_ids")
    else:
        normalized_project, matches = next(iter(normalized_projects.items()))
        components.append(
            _component_from_group(
                segment,
                matches[0],
                group_name="project_id",
                role="project_id",
                normalized_override=normalized_project,
            )
        )
        if len(matches) > 1:
            reasons.append("repeated_same_project_id")

    resolver_matches: list[tuple[MatterKeyResolverRule, re.Match[str]]] = []
    for resolver in policy.resolvers:
        pattern = _compile(resolver.identity_regex, label=f"resolver {resolver.name!r} identity_regex")
        resolver_matches.extend((resolver, match) for match in pattern.finditer(segment.raw_text))

    if not resolver_matches:
        reasons.append("unrecognized_transaction_identity")
    elif len(resolver_matches) > 1:
        reasons.append("multiple_transaction_identity_matches")

    ambiguous = "multiple_project_ids" in reasons or "multiple_transaction_identity_matches" in reasons
    if ambiguous:
        return MatterKeyCandidate(
            candidate_id=candidate_id,
            policy_name=policy.name,
            policy_sha256=policy_sha,
            status=MatterKeyStatus.AMBIGUOUS,
            matter_key=None,
            resolver_name=None,
            segment_id=segment.segment_id,
            evidence_id=segment.evidence_id,
            artifact_id=segment.artifact_id,
            locator=segment.locator,
            rule_name=segment.rule_name,
            anchor_text=segment.anchor_text,
            components=tuple(components),
            reasons=tuple(reasons),
            sources=segment.sources,
        )

    if not normalized_projects or not resolver_matches:
        return MatterKeyCandidate(
            candidate_id=candidate_id,
            policy_name=policy.name,
            policy_sha256=policy_sha,
            status=MatterKeyStatus.INSUFFICIENT_IDENTITY,
            matter_key=None,
            resolver_name=(resolver_matches[0][0].name if resolver_matches else None),
            segment_id=segment.segment_id,
            evidence_id=segment.evidence_id,
            artifact_id=segment.artifact_id,
            locator=segment.locator,
            rule_name=segment.rule_name,
            anchor_text=segment.anchor_text,
            components=tuple(components),
            reasons=tuple(reasons),
            sources=segment.sources,
        )

    resolver, identity_match = resolver_matches[0]
    components.append(
        _component_from_group(
            segment,
            identity_match,
            group_name="role_anchor",
            role="transaction_role",
            normalized_override=_normalize_component("transaction_role", resolver.transaction_role),
        )
    )
    for component_role in resolver.required_components:
        if component_role in {"project_id", "transaction_role"}:
            continue
        raw_value = identity_match.groupdict().get(component_role)
        if raw_value is None or not raw_value.strip():
            reasons.append(f"missing_{component_role}")
            continue
        components.append(
            _component_from_group(
                segment,
                identity_match,
                group_name=component_role,
                role=component_role,
            )
        )

    by_role = {component.role: component for component in components}
    missing_required = [role for role in resolver.required_components if role not in by_role or not by_role[role].normalized_value]
    if missing_required:
        reasons.extend(f"missing_{role}" for role in missing_required if f"missing_{role}" not in reasons)
        return MatterKeyCandidate(
            candidate_id=candidate_id,
            policy_name=policy.name,
            policy_sha256=policy_sha,
            status=MatterKeyStatus.INSUFFICIENT_IDENTITY,
            matter_key=None,
            resolver_name=resolver.name,
            segment_id=segment.segment_id,
            evidence_id=segment.evidence_id,
            artifact_id=segment.artifact_id,
            locator=segment.locator,
            rule_name=segment.rule_name,
            anchor_text=segment.anchor_text,
            components=tuple(components),
            reasons=tuple(reasons),
            sources=segment.sources,
        )

    key_parts = [f"{role}={by_role[role].normalized_value}" for role in resolver.required_components]
    matter_key = stable_id("matter-key", policy_sha, resolver.name, *key_parts)
    return MatterKeyCandidate(
        candidate_id=candidate_id,
        policy_name=policy.name,
        policy_sha256=policy_sha,
        status=MatterKeyStatus.RESOLVED,
        matter_key=matter_key,
        resolver_name=resolver.name,
        segment_id=segment.segment_id,
        evidence_id=segment.evidence_id,
        artifact_id=segment.artifact_id,
        locator=segment.locator,
        rule_name=segment.rule_name,
        anchor_text=segment.anchor_text,
        components=tuple(components),
        reasons=tuple(reasons),
        sources=segment.sources,
    )


class MatterKeyResolver:
    """Resolve current segments under an explicit source/profile matter-key policy."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.index = SegmentIndex(state_dir)

    def _segments(self, rule_name: str) -> tuple[SegmentHit, ...]:
        build = self.index.current_build()
        if build is None:
            raise RuntimeError("segment index has not been built")
        with self.index.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evidence_segments
                WHERE build_id = ? AND rule_name = ?
                ORDER BY evidence_id, char_start, segment_id
                """,
                (build["build_id"], rule_name),
            ).fetchall()
        return tuple(self.index._hit(row) for row in rows)

    def resolve(self, policy: MatterKeyPolicy) -> MatterKeyResult:
        build = self.index.current_build()
        if build is None:
            raise RuntimeError("segment index has not been built")
        candidates = tuple(resolve_segment(segment, policy) for segment in self._segments(policy.segment_rule_name))
        resolved = tuple(candidate for candidate in candidates if candidate.status is MatterKeyStatus.RESOLVED)
        ambiguous = tuple(candidate for candidate in candidates if candidate.status is MatterKeyStatus.AMBIGUOUS)
        insufficient = tuple(
            candidate for candidate in candidates if candidate.status is MatterKeyStatus.INSUFFICIENT_IDENTITY
        )

        grouped: dict[str, list[MatterKeyCandidate]] = {}
        for candidate in resolved:
            assert candidate.matter_key is not None
            grouped.setdefault(candidate.matter_key, []).append(candidate)
        repeated_groups = tuple(
            MatterKeyGroup(
                matter_key=matter_key,
                occurrence_count=len(items),
                evidence_count=len({item.evidence_id for item in items}),
                artifact_count=len({item.artifact_id for item in items}),
                candidates=tuple(items),
            )
            for matter_key, items in sorted(grouped.items())
            if len(items) >= 2
        )

        return MatterKeyResult(
            method=_METHOD,
            policy_name=policy.name,
            policy_sha256=matter_key_policy_sha256(policy),
            segment_build_id=build["build_id"],
            candidate_count=len(candidates),
            resolved_count=len(resolved),
            ambiguous_count=len(ambiguous),
            insufficient_identity_count=len(insufficient),
            repeated_group_count=len(repeated_groups),
            candidates=candidates,
            repeated_groups=repeated_groups,
            limitations=(
                "A resolved matter key is a policy-scoped comparison guard, not proof that two records are legally identical.",
                "Ambiguous and insufficient-identity candidates must not be joined for conflicting-value detection.",
                "This method deliberately prefers false negatives over false joins.",
                "Matter-key resolution is descriptive and does not infer wrongdoing.",
            ),
        )
