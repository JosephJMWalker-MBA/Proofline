from __future__ import annotations

import json

import pytest

from proofline import Ingestor
from proofline.evaluation import RetrievalEvaluator, load_retrieval_suite
from proofline.search import SearchIndex
from proofline.structured import StructuredIndex
from tests.fixture_corpus import build_fixture_corpus


def _seed(tmp_path):
    corpus = tmp_path / "corpus"
    manifest = build_fixture_corpus(corpus)
    state = tmp_path / "state"
    ingestor = Ingestor(state)
    ingestor.ingest(
        corpus / manifest["born_digital_pdf"],
        source_uri="https://fixtures.proofline.local/born-digital.pdf",
        native_identifier="BORN-001",
    )
    ingestor.ingest(
        corpus / manifest["conflicting_structured_records"][1],
        source_uri="https://fixtures.proofline.local/contract-b.csv",
        native_identifier="CSV-B",
    )
    dated = tmp_path / "dated.txt"
    dated.write_text(
        "Meeting date: August 19, 2026. Routine agenda record for retrieval evaluation.",
        encoding="utf-8",
    )
    ingestor.ingest(
        dated,
        source_uri="https://fixtures.proofline.local/dated.txt",
        native_identifier="DATED-001",
    )
    SearchIndex(state).rebuild()
    StructuredIndex(state).rebuild()
    return state


def _write_suite(tmp_path):
    path = tmp_path / "eval-v2.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-retrieval-eval/v2",
                "name": "typed retrieval evaluation fixture",
                "cases": [
                    {
                        "case_id": "lexical-positive",
                        "mode": "lexical",
                        "query": "Contract award 250 000",
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/born-digital.pdf",
                                "locator": "page:1",
                            }
                        ],
                    },
                    {
                        "case_id": "publisher-native-id",
                        "mode": "native_identifier",
                        "query": "CSV-B",
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/contract-b.csv",
                                "locator": "sheet:CSV!A2:C2",
                            }
                        ],
                    },
                    {
                        "case_id": "content-identifier",
                        "mode": "identifier",
                        "query": "C-001",
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/contract-b.csv",
                                "locator": "sheet:CSV!A2:C2",
                            }
                        ],
                    },
                    {
                        "case_id": "exact-money",
                        "mode": "money",
                        "minimum": 410000,
                        "maximum": 410000,
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/contract-b.csv",
                                "locator": "sheet:CSV!A2:C2",
                            }
                        ],
                    },
                    {
                        "case_id": "exact-date",
                        "mode": "date",
                        "start": "2026-08-19",
                        "end": "2026-08-19",
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/dated.txt",
                                "locator": "record:1",
                            }
                        ],
                    },
                    {
                        "case_id": "negative-lexical",
                        "mode": "lexical",
                        "query": "ZXQNOTPRESENT",
                        "expect_empty": True,
                        "expected": [],
                    },
                    {
                        "case_id": "known-positive-miss",
                        "mode": "lexical",
                        "query": "entirely unrelated vocabulary",
                        "expected": [
                            {
                                "source_uri": "https://fixtures.proofline.local/born-digital.pdf",
                                "locator": "page:1",
                            }
                        ],
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_v2_evaluation_supports_typed_and_negative_cases(tmp_path) -> None:
    state = _seed(tmp_path)
    suite = load_retrieval_suite(_write_suite(tmp_path))
    result = RetrievalEvaluator(state).run(suite, k=5)

    assert result.schema == "proofline-retrieval-eval/v2"
    assert result.cases == 7
    assert result.unresolved_target_count == 0
    assert result.negative_case_count == 1
    assert result.negative_accuracy == 1.0
    assert result.provenance_validity == 1.0
    assert result.structured_build_id is not None

    by_id = {case.case_id: case for case in result.case_results}
    for case_id in (
        "lexical-positive",
        "publisher-native-id",
        "content-identifier",
        "exact-money",
        "exact-date",
        "negative-lexical",
    ):
        assert by_id[case_id].expectation_met is True
        assert by_id[case_id].failure_class is None

    miss = by_id["known-positive-miss"]
    assert miss.expectation_met is False
    assert miss.hit is False
    assert miss.failure_class == "miss_all_targets"
    assert result.expectation_accuracy == pytest.approx(6 / 7)
    assert {row["failure_class"]: row["count"] for row in result.failure_counts} == {
        "miss_all_targets": 1
    }

    mode_metrics = {row["mode"]: row for row in result.mode_metrics}
    assert mode_metrics["money"]["expectation_accuracy"] == 1.0
    assert mode_metrics["date"]["expectation_accuracy"] == 1.0
    assert mode_metrics["lexical"]["negative_accuracy"] == 1.0
    assert mode_metrics["lexical"]["positive_hit_rate"] == pytest.approx(0.5)


def test_v2_negative_cases_cannot_declare_positive_targets(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-retrieval-eval/v2",
                "name": "bad",
                "cases": [
                    {
                        "case_id": "bad-negative",
                        "mode": "lexical",
                        "query": "anything",
                        "expect_empty": True,
                        "expected": [
                            {"source_uri": "https://example.gov/a", "locator": "page:1"}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="negative case"):
        load_retrieval_suite(path)


def test_v1_suite_remains_supported(tmp_path) -> None:
    path = tmp_path / "v1.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-retrieval-eval/v1",
                "name": "legacy",
                "cases": [
                    {
                        "case_id": "legacy-case",
                        "query": "legacy query",
                        "expected": [
                            {"source_uri": "https://example.gov/a", "locator": "page:1"}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    suite = load_retrieval_suite(path)
    assert suite.schema == "proofline-retrieval-eval/v1"
    assert suite.cases[0].mode == "lexical"
