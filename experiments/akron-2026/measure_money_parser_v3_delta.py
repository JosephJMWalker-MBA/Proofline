#!/usr/bin/env python3
"""Measure the explicit v2 -> v3 money-parser delta on preserved T13b anchors.

The fixture is a compact derivative of already-opened T13b evidence. It is not a new
out-of-sample evaluation. Each record preserves the exact v2 money token and its local
character anchor so historical v2 behavior must reproduce before v3 is compared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from proofline.structured import extract_structured_facts

SCHEMA = "proofline-akron-money-parser-v3-delta/v1"
FIXTURE_SCHEMA = "proofline-akron-t15-t13b-money-anchor-fixture/v1"
EXPECTED_FIXTURE_SHA256 = "016a149d5d1f092f87533be012961a0f9b3a310beb4af0c6b25540159b1ec2f9"
V2 = "proofline-structured/v2"
V3 = "proofline-structured/v3"


def _money(text: str, parser_version: str):
    return [
        fact
        for fact in extract_structured_facts(text, parser_version=parser_version)
        if fact.fact_type == "money"
    ]


def measure(fixture_path: Path) -> dict:
    raw = fixture_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_FIXTURE_SHA256:
        raise RuntimeError(f"T15 fixture SHA-256 changed: {digest}")

    fixture = json.loads(raw)
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise RuntimeError("unexpected T15 anchor-fixture schema")
    rows = fixture.get("facts") or []
    if fixture.get("fact_count") != 194 or len(rows) != 194:
        raise RuntimeError("T15 anchor fixture must contain exactly 194 facts")

    unchanged = []
    removed = []
    changed = []
    for ordinal, row in enumerate(rows):
        text = row["s"]
        start = int(row["a"])
        end = int(row["b"])
        expected_raw = row["raw"]
        expected_norm = row["norm"]
        if text[start:end] != expected_raw:
            raise RuntimeError(f"fixture anchor {ordinal} no longer slices to its raw token")

        v2_at_anchor = [fact for fact in _money(text, V2) if fact.char_start == start]
        if len(v2_at_anchor) != 1:
            raise RuntimeError(
                f"v2 no longer reproduces exactly one anchored fact at fixture ordinal {ordinal}"
            )
        old = v2_at_anchor[0]
        if (
            old.char_end != end
            or old.raw_text != expected_raw
            or old.normalized_text != expected_norm
        ):
            raise RuntimeError(
                f"v2 historical anchor changed at ordinal {ordinal}: "
                f"{old.raw_text!r}/{old.normalized_text!r}/{old.char_end}"
            )

        v3_at_anchor = [fact for fact in _money(text, V3) if fact.char_start == start]
        if not v3_at_anchor:
            removed.append(
                {
                    "ordinal": ordinal,
                    "old_raw_text": expected_raw,
                    "old_normalized_text": expected_norm,
                    "snippet": text,
                    "char_start": start,
                    "char_end": end,
                }
            )
            continue
        if len(v3_at_anchor) != 1:
            raise RuntimeError(f"v3 emitted multiple facts at fixture ordinal {ordinal}")
        new = v3_at_anchor[0]
        if (
            new.char_end == end
            and new.raw_text == expected_raw
            and new.normalized_text == expected_norm
        ):
            unchanged.append(ordinal)
        else:
            changed.append(
                {
                    "ordinal": ordinal,
                    "old": {
                        "raw_text": expected_raw,
                        "normalized_text": expected_norm,
                        "char_end": end,
                    },
                    "new": {
                        "raw_text": new.raw_text,
                        "normalized_text": new.normalized_text,
                        "char_end": new.char_end,
                    },
                    "snippet": text,
                    "char_start": start,
                }
            )

    if len(unchanged) != 193 or len(removed) != 1 or changed:
        raise RuntimeError(
            "unexpected T13b v2->v3 delta: "
            f"unchanged={len(unchanged)}, removed={len(removed)}, changed={len(changed)}"
        )
    removal = removed[0]
    if removal["old_raw_text"] != "$20" or "$20,001___" not in removal["snippet"]:
        raise RuntimeError(f"v3 removed an unexpected historical anchor: {removal}")
    if any(fact.raw_text in {"$20", "$20,001"} for fact in _money(removal["snippet"], V3)):
        raise RuntimeError("v3 did not fail closed on the malformed OCR continuation")

    return {
        "schema": SCHEMA,
        "fixture": {
            "schema": FIXTURE_SCHEMA,
            "sha256": digest,
            "fact_count": len(rows),
            "provenance": {
                "stage": "already_opened_t13b_evidence_derivative",
                "workflow_run_id": 32440471169,
                "workflow_artifact_id": 9432387690,
                "workflow_artifact_digest": "sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338",
            },
        },
        "old_parser_version": V2,
        "new_parser_version": V3,
        "fact_count": len(rows),
        "unchanged_fact_count": len(unchanged),
        "removed_fact_count": len(removed),
        "changed_fact_count": len(changed),
        "removed": removed,
        "changed": changed,
        "semantic_contract_changed": False,
        "detector_authorized": False,
        "lead_count": None,
        "non_claims": [
            "This is a parser-regression measurement on already-opened T13b evidence, not a new holdout.",
            "A removed malformed token is not reconstructed into a guessed monetary value.",
            "No semantic-role precision or detector claim follows from this numeric-integrity repair.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = measure(Path(args.fixture))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
