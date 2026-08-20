#!/usr/bin/env python3
"""Reproduce the frozen R1.T8 Akron money facts and emit local Silver context.

R1.T9 is deliberately a characterization stage. It assigns no financial roles.
The frozen T8 population must reproduce against the same Bronze artifacts before
any local context is emitted; source-version drift therefore fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from proofline.hashing import source_id_from_uri
from proofline.storage import ProoflineStore
from proofline.structured import StructuredIndex
from proofline.watch_storage import WatcherStore

FROZEN_SCHEMA = "proofline-akron-t8-money-facts/v1"
OUTPUT_SCHEMA = "proofline-akron-money-context-profile/v1"
_WHITESPACE_RE = re.compile(r"\s+")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _signature(facts: list[dict]) -> str:
    return hashlib.sha256(_canonical_json(facts).encode("utf-8")).hexdigest()


def _load_frozen(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != FROZEN_SCHEMA:
        raise ValueError(f"unexpected frozen fact schema: {payload.get('schema')!r}")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise ValueError("frozen facts must be a list")
    if payload.get("fact_count") != len(facts):
        raise ValueError("frozen fact_count does not match facts")
    expected = payload.get("signature_sha256")
    actual = _signature(facts)
    if expected != actual:
        raise ValueError(
            f"frozen money-fact signature mismatch: expected {expected}, computed {actual}"
        )
    sources = payload.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("frozen source map is missing")
    unknown = sorted({fact.get("source") for fact in facts} - set(sources))
    if unknown:
        raise ValueError(f"frozen facts reference unknown source keys: {unknown}")
    return payload


def _normalize_context(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _context_window(text: str, start: int, end: int, radius: int) -> dict:
    if radius < 0:
        raise ValueError("context radius cannot be negative")
    if start < 0 or end < start or end > len(text):
        raise ValueError(
            f"invalid fact character range {start}:{end} for preferred text length {len(text)}"
        )
    context_start = max(0, start - radius)
    context_end = min(len(text), end + radius)
    before = text[context_start:start]
    token = text[start:end]
    after = text[end:context_end]
    context_text = text[context_start:context_end]
    normalized = _normalize_context(context_text)
    return {
        "context_start": context_start,
        "context_end": context_end,
        "before": before,
        "token": token,
        "after": after,
        "context_text": context_text,
        "context_normalized": normalized,
        "context_sha256": hashlib.sha256(context_text.encode("utf-8")).hexdigest(),
        "context_normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def _locator_sort(locator: str) -> tuple[str, int, str]:
    prefix, separator, suffix = locator.partition(":")
    if separator and suffix.isdigit():
        return (prefix, int(suffix), "")
    return (prefix, 10**9, suffix)


def _fact_sort_key(fact: dict) -> tuple:
    return (
        fact["source"],
        _locator_sort(fact["locator"]),
        fact["char_start"],
        fact["char_end"],
        fact["raw_text"],
        fact["normalized_text"],
    )


def _preferred_extraction(store: ProoflineStore, artifact_id: str, locator: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT
                eu.evidence_id,
                eu.locator,
                ee.method,
                ee.extracted_text,
                ee.quality_score,
                ee.software_version,
                ee.model_version,
                ee.occurred_at
            FROM evidence_units eu
            JOIN evidence_extractions ee
              ON ee.extraction_id = (
                SELECT candidate.extraction_id
                FROM evidence_extractions candidate
                WHERE candidate.evidence_id = eu.evidence_id
                ORDER BY COALESCE(candidate.quality_score, -1.0) DESC,
                         candidate.occurred_at DESC,
                         candidate.rowid DESC
                LIMIT 1
              )
            WHERE eu.artifact_id = ? AND eu.locator = ?
            LIMIT 1
            """,
            (artifact_id, locator),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"preferred Silver evidence missing: {artifact_id} {locator}")
    payload = dict(row)
    text = payload.get("extracted_text") or ""
    if not text.strip():
        raise RuntimeError(f"preferred Silver evidence is blank: {artifact_id} {locator}")
    payload["page_text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return payload


def _verify_frozen_sources(
    store: ProoflineStore,
    watcher: WatcherStore,
    frozen: dict,
) -> dict[str, dict]:
    resolved: dict[str, dict] = {}
    for source_key, specification in sorted(frozen["sources"].items()):
        source_uri = specification["source_uri"]
        source_id = source_id_from_uri(source_uri)
        artifact_id = watcher.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = store.latest_artifact_for_source(source_id)
        if artifact_id is None:
            raise RuntimeError(f"frozen source has no current successful artifact: {source_key}")
        expected_artifact = specification["artifact_id"]
        if artifact_id != expected_artifact:
            raise RuntimeError(
                "frozen source-version drift detected; refusing to reinterpret T8 facts: "
                f"{source_key} expected {expected_artifact}, current {artifact_id}"
            )
        with store.connection() as connection:
            row = connection.execute(
                "SELECT sha256, byte_size, media_type, stored_path FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"frozen artifact row is missing: {artifact_id}")
        resolved[source_key] = {
            "source_id": source_id,
            "source_uri": source_uri,
            "artifact_id": artifact_id,
            **dict(row),
        }
    return resolved


def _current_money_facts(
    store: ProoflineStore,
    *,
    build_id: str,
    resolved_sources: dict[str, dict],
) -> list[dict]:
    source_by_artifact = {
        specification["artifact_id"]: source_key
        for source_key, specification in resolved_sources.items()
    }
    artifact_ids = sorted(source_by_artifact)
    placeholders = ",".join("?" for _ in artifact_ids)
    with store.connection() as connection:
        rows = connection.execute(
            f"""
            SELECT artifact_id, locator, raw_text, normalized_text, char_start, char_end
            FROM evidence_facts
            WHERE build_id = ?
              AND fact_type = 'money'
              AND artifact_id IN ({placeholders})
            """,
            [build_id, *artifact_ids],
        ).fetchall()
    facts = [
        {
            "source": source_by_artifact[row["artifact_id"]],
            "locator": row["locator"],
            "raw_text": row["raw_text"],
            "normalized_text": row["normalized_text"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
        }
        for row in rows
    ]
    return sorted(facts, key=_fact_sort_key)


def build_profile(
    state_dir: Path,
    frozen_path: Path,
    *,
    context_chars: int,
) -> dict:
    if context_chars < 0:
        raise ValueError("context_chars cannot be negative")
    frozen = _load_frozen(frozen_path)
    store = ProoflineStore(state_dir / "proofline.db")
    watcher = WatcherStore(state_dir / "proofline.db")
    structured = StructuredIndex(state_dir)
    build = structured.current_build()
    if build is None:
        raise RuntimeError("structured index is missing; run the T8 evidence profile first")

    resolved_sources = _verify_frozen_sources(store, watcher, frozen)
    current_facts = _current_money_facts(
        store,
        build_id=build["build_id"],
        resolved_sources=resolved_sources,
    )
    frozen_facts = sorted(frozen["facts"], key=_fact_sort_key)
    if current_facts != frozen_facts:
        raise RuntimeError(
            "current preferred-Silver money population does not reproduce the frozen T8 facts"
        )
    current_signature = _signature(current_facts)
    if current_signature != frozen["signature_sha256"]:
        raise RuntimeError("reproduced money-fact signature differs from the frozen T8 signature")

    extraction_cache: dict[tuple[str, str], dict] = {}
    contexts: list[dict] = []
    method_counts: Counter[str] = Counter()
    quality_values: list[float] = []
    for fact in frozen["facts"]:
        source_key = fact["source"]
        source = resolved_sources[source_key]
        cache_key = (source["artifact_id"], fact["locator"])
        extraction = extraction_cache.get(cache_key)
        if extraction is None:
            extraction = _preferred_extraction(store, *cache_key)
            extraction_cache[cache_key] = extraction
        text = extraction["extracted_text"]
        window = _context_window(
            text,
            int(fact["char_start"]),
            int(fact["char_end"]),
            context_chars,
        )
        if window["token"] != fact["raw_text"]:
            raise RuntimeError(
                "frozen fact token does not match preferred Silver at its frozen character range: "
                f"{source_key} {fact['locator']} {fact['char_start']}:{fact['char_end']} "
                f"expected {fact['raw_text']!r}, found {window['token']!r}"
            )
        quality = extraction["quality_score"]
        if quality is not None:
            quality_values.append(float(quality))
        method_counts[extraction["method"]] += 1
        contexts.append(
            {
                **fact,
                "source_uri": source["source_uri"],
                "artifact_id": source["artifact_id"],
                "artifact_sha256": source["sha256"],
                "evidence_id": extraction["evidence_id"],
                "extraction_method": extraction["method"],
                "quality_score": quality,
                "software_version": extraction["software_version"],
                "model_version": extraction["model_version"],
                "page_text_sha256": extraction["page_text_sha256"],
                **window,
            }
        )

    if any("role" in context for context in contexts):
        raise AssertionError("R1.T9 context profile must not assign semantic roles")

    return {
        "schema": OUTPUT_SCHEMA,
        "stage": "context_characterization_only",
        "semantic_roles_assigned": False,
        "context_chars": context_chars,
        "frozen": {
            "schema": frozen["schema"],
            "fact_count": frozen["fact_count"],
            "signature_sha256": frozen["signature_sha256"],
            "source_run": frozen.get("source_run"),
        },
        "reproduction": {
            "source_count": len(resolved_sources),
            "fact_count": len(current_facts),
            "signature_sha256": current_signature,
            "structured_build_id": build["build_id"],
            "exact_fact_population_match": True,
            "exact_source_artifact_match": True,
            "exact_token_anchor_match": True,
        },
        "preferred_silver": {
            "unique_page_count": len(extraction_cache),
            "fact_method_counts": dict(sorted(method_counts.items())),
            "minimum_quality_score": min(quality_values) if quality_values else None,
            "maximum_quality_score": max(quality_values) if quality_values else None,
        },
        "sources": resolved_sources,
        "contexts": contexts,
        "decision_note": (
            "No financial role is assigned here. These frozen local Silver contexts are the "
            "evidence basis for deriving a later conservative Akron attachment role contract."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--frozen", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--context-chars", type=int, default=320)
    args = parser.parse_args()
    if args.context_chars < 0:
        raise SystemExit("--context-chars cannot be negative")

    profile = build_profile(
        Path(args.state_dir),
        Path(args.frozen),
        context_chars=args.context_chars,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
