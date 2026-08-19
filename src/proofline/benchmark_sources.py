"""Source-role policy for longitudinal retrieval benchmark target selection.

A benchmark should distinguish canonical evidence from discovery/support provenance. The policy is
source-profile data: Proofline core does not hardcode any publisher's URL structure.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = "proofline-benchmark-source-policy/v1"
_ALLOWED_ROLES = {"canonical", "support", "excluded"}


@dataclass(frozen=True, slots=True)
class BenchmarkSourceRule:
    name: str
    role: str
    source_uri_regex: str

    def matches(self, source_uri: str) -> bool:
        return re.search(self.source_uri_regex, source_uri) is not None


@dataclass(frozen=True, slots=True)
class BenchmarkSourcePolicy:
    name: str
    rules: tuple[BenchmarkSourceRule, ...]
    default_role: str = "excluded"
    schema: str = _SCHEMA

    def classify(self, source_uri: str) -> str:
        matched = {rule.role for rule in self.rules if rule.matches(source_uri)}
        if not matched:
            return self.default_role
        if len(matched) > 1:
            raise ValueError(f"ambiguous benchmark source roles for {source_uri!r}: {sorted(matched)}")
        return next(iter(matched))

    def matching_rules(self, source_uri: str) -> tuple[str, ...]:
        return tuple(rule.name for rule in self.rules if rule.matches(source_uri))

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "name": self.name,
            "default_role": self.default_role,
            "rules": [
                {
                    "name": rule.name,
                    "role": rule.role,
                    "source_uri_regex": rule.source_uri_regex,
                }
                for rule in self.rules
            ],
        }


def load_benchmark_source_policy(path: str | Path) -> BenchmarkSourcePolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _SCHEMA:
        raise ValueError(f"benchmark source policy schema must be {_SCHEMA!r}")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("benchmark source policy name must be non-empty")
    default_role = payload.get("default_role", "excluded")
    if default_role not in _ALLOWED_ROLES:
        raise ValueError(f"default_role must be one of {sorted(_ALLOWED_ROLES)}")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("benchmark source policy rules must be a non-empty list")

    rules: list[BenchmarkSourceRule] = []
    names: set[str] = set()
    for item in raw_rules:
        if not isinstance(item, dict):
            raise ValueError("each benchmark source rule must be an object")
        rule_name = item.get("name")
        role = item.get("role")
        pattern = item.get("source_uri_regex")
        if not isinstance(rule_name, str) or not rule_name.strip():
            raise ValueError("benchmark source rule name must be non-empty")
        if rule_name in names:
            raise ValueError(f"duplicate benchmark source rule name: {rule_name}")
        names.add(rule_name)
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"benchmark source rule role must be one of {sorted(_ALLOWED_ROLES)}")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"source_uri_regex missing for rule {rule_name}")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid source_uri_regex for rule {rule_name}: {exc}") from exc
        rules.append(
            BenchmarkSourceRule(
                name=rule_name,
                role=str(role),
                source_uri_regex=pattern,
            )
        )

    return BenchmarkSourcePolicy(
        name=name.strip(),
        rules=tuple(rules),
        default_role=str(default_role),
    )
