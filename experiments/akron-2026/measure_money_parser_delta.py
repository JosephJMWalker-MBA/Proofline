#!/usr/bin/env python3
"""Measure the structured money parser v1 -> v2 delta on frozen Akron evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "proofline-akron-money-parser-delta/v1"
OLD_PARSER = "proofline-structured/v1"
NEW_PARSER = "proofline-structured/v2"

# T9 proved exactly two malformed v1 facts on this frozen population. T10 must
# repair these two anchors and leave the other 29 facts unchanged.
_EXPECTED_CHANGES = {
    ("s4", "page:4", 378): {
        "old": {"raw_text": "$138", "normalized_text": "138.00", "char_end": 382},
        "new": {
            "raw_text": "$138MM",
            "normalized_text": "138000000.00",
            "char_end": 384,
        },
        "reason": "contiguous magnitude suffix must be consumed and expanded",
    },
    ("s5", "page:2", 1207): {
        "old": {"raw_text": "$ 51", "normalized_text": "51.00", "char_end": 1211},
        "new": {
            "raw_text": "$ 51 ,780.00",
            "normalized_text": "51780.00",
            "char_end": 1219,
        },
        "reason": "whitespace-separated thousands punctuation must remain one amount",
    },
}


def _fact_projection(fact: dict) -> dict:
    return {
        "raw_text": fact.get("raw_text"),
        "normalized_text": fact.get("normalized_text"),
        "char_end": fact.get("char_end"),
    }


def measure_delta(frozen: dict, current_profile: dict) -> dict:
    if frozen.get("schema") != "proofline-akron-t8-money-facts/v1":
        raise RuntimeError("unexpected frozen money-fact schema")
    if frozen.get("fact_count") != 31 or len(frozen.get("facts") or []) != 31:
        raise RuntimeError("frozen money population is no longer exactly 31 facts")

    current_build = current_profile["post_ocr"]["structured_build"]
    if current_build.get("parser_version") != NEW_PARSER:
        raise RuntimeError(
            f"current profile used {current_build.get('parser_version')} instead of {NEW_PARSER}"
        )

    frozen_sources = frozen.get("sources") or {}
    alias_by_identity = {
        (meta["source_uri"], meta["artifact_id"]): alias
        for alias, meta in frozen_sources.items()
    }
    if len(alias_by_identity) != 7:
        raise RuntimeError("frozen source population is no longer seven unique Bronze identities")

    attachment_identities = {
        (item["source_uri"], item["artifact"]["artifact_id"])
        for item in current_profile.get("attachments") or []
    }
    missing_identities = sorted(set(alias_by_identity) - attachment_identities)
    if missing_identities:
        raise RuntimeError(f"current profile no longer contains frozen Bronze identities: {missing_identities}")

    frozen_by_anchor: dict[tuple[str, str, int], dict] = {}
    for fact in frozen["facts"]:
        key = (fact["source"], fact["locator"], fact["char_start"])
        if key in frozen_by_anchor:
            raise RuntimeError(f"duplicate frozen money anchor: {key}")
        frozen_by_anchor[key] = fact

    current_by_anchor: dict[tuple[str, str, int], dict] = {}
    for fact in current_profile["post_ocr"]["facts"]["money"]:
        identity = (fact.get("source_uri"), fact.get("artifact_id"))
        alias = alias_by_identity.get(identity)
        if alias is None:
            # The eighth bounded T7 source contains no money and any other money-bearing
            # identity would represent source/sample drift.
            raise RuntimeError(f"money fact escaped the frozen seven-source Bronze population: {identity}")
        key = (alias, fact["locator"], fact["char_start"])
        if key in current_by_anchor:
            raise RuntimeError(f"duplicate current money anchor: {key}")
        current_by_anchor[key] = fact

    if set(current_by_anchor) != set(frozen_by_anchor):
        missing = sorted(set(frozen_by_anchor) - set(current_by_anchor))
        added = sorted(set(current_by_anchor) - set(frozen_by_anchor))
        raise RuntimeError(f"money anchor population drifted; missing={missing}, added={added}")

    changed = []
    unchanged = 0
    unexpected = []
    for key in sorted(frozen_by_anchor):
        old_fact = frozen_by_anchor[key]
        new_fact = current_by_anchor[key]
        old_projection = _fact_projection(old_fact)
        new_projection = _fact_projection(new_fact)
        if old_projection == new_projection:
            unchanged += 1
            continue

        expected = _EXPECTED_CHANGES.get(key)
        item = {
            "source": key[0],
            "locator": key[1],
            "char_start": key[2],
            "old": old_projection,
            "new": new_projection,
            "reason": expected["reason"] if expected else None,
        }
        changed.append(item)
        if expected is None or old_projection != expected["old"] or new_projection != expected["new"]:
            unexpected.append(item)

    expected_changed_keys = set(_EXPECTED_CHANGES)
    actual_changed_keys = {
        (item["source"], item["locator"], item["char_start"]) for item in changed
    }
    missing_expected_changes = sorted(expected_changed_keys - actual_changed_keys)

    result = {
        "schema": SCHEMA,
        "old_parser_version": OLD_PARSER,
        "new_parser_version": NEW_PARSER,
        "frozen_signature_sha256": frozen.get("signature_sha256"),
        "exact_source_artifact_match": True,
        "fact_count": len(current_by_anchor),
        "unchanged_fact_count": unchanged,
        "changed_fact_count": len(changed),
        "expected_changed_fact_count": len(_EXPECTED_CHANGES),
        "changes": changed,
        "unexpected_changes": unexpected,
        "missing_expected_changes": [
            {"source": key[0], "locator": key[1], "char_start": key[2]}
            for key in missing_expected_changes
        ],
    }

    if result["fact_count"] != 31:
        raise RuntimeError(f"v2 money fact count changed unexpectedly: {result['fact_count']}")
    if result["unchanged_fact_count"] != 29:
        raise RuntimeError(
            f"expected 29 unchanged v1 facts, found {result['unchanged_fact_count']}"
        )
    if result["changed_fact_count"] != 2:
        raise RuntimeError(f"expected exactly two v1 -> v2 changes, found {result['changed_fact_count']}")
    if unexpected:
        raise RuntimeError(f"unexpected parser changes detected: {unexpected}")
    if missing_expected_changes:
        raise RuntimeError(f"expected parser repairs did not occur: {missing_expected_changes}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", required=True)
    parser.add_argument("--current-profile", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    frozen = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current_profile).read_text(encoding="utf-8"))
    result = measure_delta(frozen, current)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
