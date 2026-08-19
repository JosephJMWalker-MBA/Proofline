from __future__ import annotations

import json

import pytest

from proofline import Ingestor
from proofline.benchmark_sources import (
    BenchmarkSourcePolicy,
    BenchmarkSourceRule,
    load_benchmark_source_policy,
)
from proofline.benchmarking import RetrievalBenchmarkPoolBuilder
from proofline.structured import StructuredIndex


def _policy() -> BenchmarkSourcePolicy:
    return BenchmarkSourcePolicy(
        name="fixture roles",
        rules=(
            BenchmarkSourceRule(
                name="canonical",
                role="canonical",
                source_uri_regex=r"^https://example\.gov/canonical/",
            ),
            BenchmarkSourceRule(
                name="support",
                role="support",
                source_uri_regex=r"^https://example\.gov/support/",
            ),
        ),
    )


def test_policy_loader_and_ambiguous_role_guard(tmp_path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-benchmark-source-policy/v1",
                "name": "fixture",
                "default_role": "excluded",
                "rules": [
                    {
                        "name": "canonical",
                        "role": "canonical",
                        "source_uri_regex": r"^https://example\.gov/canonical/",
                    },
                    {
                        "name": "support",
                        "role": "support",
                        "source_uri_regex": r"^https://example\.gov/support/",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    policy = load_benchmark_source_policy(path)
    assert policy.classify("https://example.gov/canonical/a") == "canonical"
    assert policy.classify("https://example.gov/support/a") == "support"
    assert policy.classify("https://other.example/a") == "excluded"

    ambiguous = BenchmarkSourcePolicy(
        name="ambiguous",
        rules=(
            BenchmarkSourceRule("a", "canonical", r"example\.gov"),
            BenchmarkSourceRule("b", "support", r"example\.gov"),
        ),
    )
    with pytest.raises(ValueError, match="ambiguous benchmark source roles"):
        ambiguous.classify("https://example.gov/a")


def test_benchmark_uses_canonical_context_and_excludes_support_only_evidence(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)

    canonical = tmp_path / "canonical.txt"
    canonical.write_text(
        "Harbor Engineering Project approved $120,000 on August 19, 2026.",
        encoding="utf-8",
    )
    ingestor.ingest(
        canonical,
        source_uri="https://example.gov/canonical/one",
        native_identifier="CANON-ONE",
    )

    support = tmp_path / "support.txt"
    support.write_text(
        "Support Calendar Fragment lists $999,999 on August 20, 2026.",
        encoding="utf-8",
    )
    ingestor.ingest(
        support,
        source_uri="https://example.gov/support/index",
        native_identifier="SUPPORT-ONLY",
    )

    shared = tmp_path / "shared.txt"
    shared.write_text(
        "Shared Civic Contract approved $77,000 on August 21, 2026.",
        encoding="utf-8",
    )
    ingestor.ingest(
        shared,
        source_uri="https://example.gov/support/shared",
        native_identifier="SUPPORT-SHARED",
    )
    # Same bytes/artifact, independently linked from a canonical source.
    ingestor.ingest(
        shared,
        source_uri="https://example.gov/canonical/shared",
        native_identifier="CANON-SHARED",
    )

    StructuredIndex(state).rebuild()
    pool = RetrievalBenchmarkPoolBuilder(state, source_policy=_policy()).build(
        max_per_kind=20,
        max_targets=10,
    )

    assert pool["selection"]["target_source_role"] == "canonical"
    assert pool["selection"]["source_policy"]["name"] == "fixture roles"

    positives = [case for case in pool["cases"] if not case.get("expect_empty")]
    assert positives
    all_targets = [target for case in positives for target in case["expected"]]
    assert all(target["source_uri"].startswith("https://example.gov/canonical/") for target in all_targets)

    lexical_queries = {case.get("query") for case in positives if case["mode"] == "lexical"}
    assert "Support Calendar Fragment" not in lexical_queries
    assert "Harbor Engineering Project" in lexical_queries
    assert "Shared Civic Contract" in lexical_queries

    native_queries = {case.get("query") for case in positives if case["mode"] == "native_identifier"}
    assert "CANON-ONE" in native_queries
    assert "CANON-SHARED" in native_queries
    assert "SUPPORT-ONLY" not in native_queries
    assert "SUPPORT-SHARED" not in native_queries
