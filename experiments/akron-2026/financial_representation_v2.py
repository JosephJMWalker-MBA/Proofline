#!/usr/bin/env python3
"""Apply the frozen Akron financial-representation v2 contract to one money fact.

This representation is descriptive only. It assigns independent context facets and
never creates transaction identity, event independence, anomaly, conflict, suspiciousness,
or lead judgments.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "proofline-akron-financial-representation/v2"


def load_contract(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_contract(payload)
    return payload


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_LIST_FIELDS = (
    "context_all",
    "context_any",
    "context_none",
    "page_all",
    "page_any",
    "page_none",
    "source_name_all",
    "source_name_any",
    "source_name_none",
    "context_types",
)
_REGEX_FIELDS = (
    "left_regex",
    "right_regex",
    "token_before_first_regex",
    "token_after_first_regex",
)


def validate_contract(contract: dict) -> None:
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected Akron financial-representation schema")
    if contract.get("parser_version") != "proofline-structured/v2":
        raise ValueError("financial representation v2 requires structured parser v2")
    for key in ("detector_authorized", "event_identity_assigned", "independence_assessed"):
        if contract.get(key) is not False:
            raise ValueError(f"{key} must remain false in representation-only stage")

    defaults = contract.get("defaults") or {}
    allowed = contract.get("allowed") or {}
    for axis in ("scope", "context_type", "amount_type"):
        values = allowed.get(axis)
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError(f"allowed {axis} values must be a unique non-empty list")
        if defaults.get(axis) not in values:
            raise ValueError(f"default {axis} must be an allowed value")

    scope_map = contract.get("scope_by_context_type") or {}
    if set(scope_map) != set(allowed["context_type"]):
        raise ValueError("scope mapping must cover every context_type")
    if any(value not in allowed["scope"] for value in scope_map.values()):
        raise ValueError("scope mapping contains an unknown scope")

    seen: set[str] = set()
    for collection_name, value_axis in (
        ("context_rules", "context_type"),
        ("amount_rules", "amount_type"),
    ):
        for rule in contract.get(collection_name) or []:
            rule_id = rule.get("rule_id")
            if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
                raise ValueError("representation rules require unique non-empty rule_id values")
            seen.add(rule_id)
            if rule.get("value") not in allowed[value_axis]:
                raise ValueError(f"rule {rule_id} has invalid {value_axis} value")
            for field in _LIST_FIELDS:
                if field in rule and not isinstance(rule[field], list):
                    raise ValueError(f"rule {rule_id} field {field} must be a list")
            for field in _REGEX_FIELDS:
                if rule.get(field):
                    re.compile(rule[field], re.IGNORECASE)
            if collection_name == "amount_rules":
                context_types = rule.get("context_types") or []
                if not context_types:
                    raise ValueError(f"amount rule {rule_id} must declare context_types")
                if any(value not in allowed["context_type"] for value in context_types):
                    raise ValueError(f"amount rule {rule_id} contains unknown context_type")


def _contains_all(haystack: str, needles: list[str]) -> bool:
    return all(_normalize(needle) in haystack for needle in needles)


def _contains_any(haystack: str, needles: list[str]) -> bool:
    return not needles or any(_normalize(needle) in haystack for needle in needles)


def _contains_none(haystack: str, needles: list[str]) -> bool:
    return all(_normalize(needle) not in haystack for needle in needles)


def _rule_matches(
    rule: dict,
    *,
    page_text: str,
    normalized_page: str,
    context_text: str,
    normalized_context: str,
    left_text: str,
    normalized_left: str,
    right_text: str,
    normalized_right: str,
    source_name: str,
    normalized_source_name: str,
    char_start: int,
    char_end: int,
    context_type: str | None = None,
) -> bool:
    del context_text, left_text, right_text, source_name, char_end

    if context_type is not None:
        context_types = rule.get("context_types") or []
        if context_type not in context_types:
            return False

    for prefix, haystack in (
        ("context", normalized_context),
        ("page", normalized_page),
        ("source_name", normalized_source_name),
    ):
        if not _contains_all(haystack, rule.get(f"{prefix}_all") or []):
            return False
        if not _contains_any(haystack, rule.get(f"{prefix}_any") or []):
            return False
        if not _contains_none(haystack, rule.get(f"{prefix}_none") or []):
            return False

    left_regex = rule.get("left_regex")
    if left_regex and re.search(left_regex, normalized_left, re.IGNORECASE) is None:
        return False
    right_regex = rule.get("right_regex")
    if right_regex and re.search(right_regex, normalized_right, re.IGNORECASE) is None:
        return False

    before = rule.get("token_before_first_regex")
    if before:
        match = re.search(before, page_text, re.IGNORECASE)
        if match is None or char_start >= match.start():
            return False

    after = rule.get("token_after_first_regex")
    if after:
        match = re.search(after, page_text, re.IGNORECASE)
        if match is None or char_start <= match.end():
            return False

    return True


def represent_money_fact(
    contract: dict,
    *,
    page_text: str,
    char_start: int,
    char_end: int,
    raw_text: str,
    normalized_text: str,
    source_name: str = "",
) -> dict:
    validate_contract(contract)
    if char_start < 0 or char_end <= char_start or char_end > len(page_text):
        raise ValueError("money fact has an invalid source character range")
    if page_text[char_start:char_end] != raw_text:
        raise ValueError("money fact token no longer matches its preferred Silver anchor")

    radius = int(contract["context_radius_chars"])
    left_size = int(contract["left_context_chars"])
    right_size = int(contract["right_context_chars"])
    context_start = max(0, char_start - radius)
    context_end = min(len(page_text), char_end + radius)
    left_start = max(0, char_start - left_size)
    right_end = min(len(page_text), char_end + right_size)

    context_text = page_text[context_start:context_end]
    left_text = page_text[left_start:char_start]
    right_text = page_text[char_end:right_end]

    normalized_page = _normalize(page_text)
    normalized_context = _normalize(context_text)
    normalized_left = _normalize(left_text)
    normalized_right = _normalize(right_text)
    normalized_source_name = _normalize(source_name)

    common = dict(
        page_text=page_text,
        normalized_page=normalized_page,
        context_text=context_text,
        normalized_context=normalized_context,
        left_text=left_text,
        normalized_left=normalized_left,
        right_text=right_text,
        normalized_right=normalized_right,
        source_name=source_name,
        normalized_source_name=normalized_source_name,
        char_start=char_start,
        char_end=char_end,
    )

    context_rule = None
    for rule in contract.get("context_rules") or []:
        if _rule_matches(rule, **common):
            context_rule = rule
            break
    context_type = (
        context_rule["value"] if context_rule is not None else contract["defaults"]["context_type"]
    )

    amount_rule = None
    for rule in contract.get("amount_rules") or []:
        if _rule_matches(rule, context_type=context_type, **common):
            amount_rule = rule
            break
    amount_type = (
        amount_rule["value"] if amount_rule is not None else contract["defaults"]["amount_type"]
    )
    scope = contract["scope_by_context_type"].get(context_type, contract["defaults"]["scope"])

    return {
        "scope": scope,
        "context_type": context_type,
        "amount_type": amount_type,
        "context_rule_id": context_rule["rule_id"] if context_rule else None,
        "amount_rule_id": amount_rule["rule_id"] if amount_rule else None,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "context_start": context_start,
        "context_end": context_end,
        "context_sha256": _sha256_text(context_text),
        "page_text_sha256": _sha256_text(page_text),
        "source_name_sha256": _sha256_text(source_name),
        "detector_authorized": False,
        "event_identity_assigned": False,
        "independence_assessed": False,
    }
