from __future__ import annotations

import json

from proofline import Ingestor
from proofline.benchmarking import RetrievalBenchmarkPoolBuilder
from proofline.evaluation import load_retrieval_suite
from proofline.structured import StructuredIndex


def _seed(tmp_path):
    state = tmp_path / "state"
    ingestor = Ingestor(state)

    records = (
        (
            "north-1.txt",
            "Northstar Civic Systems received a routine award of $123,456 on August 19, 2026.",
            "https://example.gov/meetings/1",
            "MEETING-001",
        ),
        (
            "north-2.txt",
            "Northstar Civic Systems presented a routine update with $150,000 on August 26, 2026.",
            "https://example.gov/meetings/2",
            "MEETING-002",
        ),
        (
            "lakeview.txt",
            "Lakeview Engineering Partners submitted a routine proposal of $77,000 on September 2, 2026.",
            "https://example.gov/meetings/3",
            "MEETING-003",
        ),
    )
    for filename, text, source_uri, native_id in records:
        path = tmp_path / filename
        path.write_text(text, encoding="utf-8")
        ingestor.ingest(
            path,
            source_uri=source_uri,
            source_name=f"Fixture {native_id}",
            native_identifier=native_id,
        )

    csv_path = tmp_path / "contracts.csv"
    csv_path.write_text(
        "contract_id,vendor,amount\nC-001,Harbor Systems,410000\n",
        encoding="utf-8",
    )
    ingestor.ingest(
        csv_path,
        source_uri="https://example.gov/contracts.csv",
        source_name="Fixture contracts",
        native_identifier="CONTRACTS-CSV",
    )

    # Deliberately build only the structured index. Benchmark generation must not need FTS/search.
    StructuredIndex(state).rebuild()
    return state


def test_benchmark_pool_is_retrieval_blind_deterministic_and_v2_loadable(tmp_path) -> None:
    state = _seed(tmp_path)
    builder = RetrievalBenchmarkPoolBuilder(state)

    first = builder.build(max_per_kind=10, max_targets=5)
    second = builder.build(max_per_kind=10, max_targets=5)
    assert first == second
    assert first["schema"] == "proofline-retrieval-eval/v2"
    assert first["selection"]["retrieval_results_consulted"] is False

    kinds = {case["selection_kind"] for case in first["cases"]}
    assert "lexical_entity_cross" in kinds
    assert "lexical_entity_unique" in kinds
    assert "native_identifier" in kinds
    assert "money_exact" in kinds
    assert "date_exact" in kinds
    assert "content_identifier" in kinds
    assert "negative_control" in kinds

    cross = [
        case for case in first["cases"] if case["selection_kind"] == "lexical_entity_cross"
    ]
    assert any(len(case["expected"]) >= 2 for case in cross)

    positives = [case for case in first["cases"] if not case.get("expect_empty", False)]
    assert positives
    for case in positives:
        assert case["expected"]
        for target in case["expected"]:
            assert target["source_uri"].startswith("https://")
            assert target["locator"]
            assert len(target["artifact_sha256"]) == 64

    negatives = [case for case in first["cases"] if case.get("expect_empty", False)]
    assert len(negatives) == 5
    assert all(case["expected"] == [] for case in negatives)

    suite_path = tmp_path / "pool.json"
    suite_path.write_text(json.dumps(first, indent=2), encoding="utf-8")
    suite = load_retrieval_suite(suite_path)
    assert suite.schema == "proofline-retrieval-eval/v2"
    assert len(suite.cases) == len(first["cases"])


def test_pool_case_ids_and_targets_do_not_depend_on_output_order(tmp_path) -> None:
    state = _seed(tmp_path)
    pool = RetrievalBenchmarkPoolBuilder(state).build(max_per_kind=4, max_targets=5)
    case_ids = [case["case_id"] for case in pool["cases"]]
    assert len(case_ids) == len(set(case_ids))

    # Each expected evidence target is bound to an exact artifact revision.
    for case in pool["cases"]:
        if case.get("expect_empty"):
            continue
        identities = {
            (target["source_uri"], target["locator"], target["artifact_sha256"])
            for target in case["expected"]
        }
        assert len(identities) == len(case["expected"])
