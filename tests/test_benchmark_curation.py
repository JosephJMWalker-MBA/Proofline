from __future__ import annotations

from proofline.benchmark_curation import curate_benchmark_pool, lexical_phrase_quality


def _case(case_id: str, query: str, kind: str, targets: int = 1) -> dict:
    return {
        "case_id": case_id,
        "mode": "lexical",
        "query": query,
        "selection_kind": kind,
        "expected": [
            {
                "source_uri": f"https://example.gov/{case_id}/{index}",
                "locator": "page:1",
                "artifact_sha256": f"{index + 1:064x}",
            }
            for index in range(targets)
        ],
    }


def test_phrase_quality_rejects_procedural_fragments_without_retrieval() -> None:
    for query in (
        "REQ LEG FOR PURCH",
        "MEETING OPEN",
        "Posted Aug",
        "SUPPORT HER PLANS",
        "Regular Meeting November",
    ):
        quality, reason = lexical_phrase_quality(query)
        assert quality is None
        assert reason is not None

    for query in (
        "Schauer Group",
        "GPD Group",
        "Northstar Civic Systems",
        "BROOKPARK WATER MAIN REPLACEMENT",
    ):
        quality, reason = lexical_phrase_quality(query)
        assert quality is not None
        assert reason is None


def test_curation_preserves_raw_rejections_and_never_claims_retrieval_use() -> None:
    pool = {
        "schema": "proofline-retrieval-eval/v2",
        "name": "raw",
        "selection": {
            "method": "proofline-retrieval-benchmark-pool/v1",
            "retrieval_results_consulted": False,
        },
        "cases": [
            _case("junk-1", "REQ LEG FOR PURCH", "lexical_entity_unique"),
            _case("junk-2", "MEETING OPEN", "lexical_entity_cross", targets=2),
            _case("good-1", "Schauer Group", "lexical_entity_unique"),
            _case("good-2", "Northstar Civic Systems", "lexical_entity_cross", targets=2),
            _case("good-3", "GPD Group", "lexical_entity_cross", targets=3),
            {
                "case_id": "money-1",
                "mode": "money",
                "minimum": 185000,
                "maximum": 185000,
                "selection_kind": "money_exact",
                "expected": [
                    {
                        "source_uri": "https://example.gov/money",
                        "locator": "page:1",
                        "artifact_sha256": "a" * 64,
                    }
                ],
            },
            {
                "case_id": "negative-1",
                "mode": "lexical",
                "query": "zzmissingzz",
                "selection_kind": "negative_control",
                "expect_empty": True,
                "expected": [],
            },
        ],
    }

    curated = curate_benchmark_pool(pool, max_per_kind=2)
    assert curated["selection"]["retrieval_results_consulted"] is False
    assert curated["selection"]["raw_case_count"] == 7
    assert curated["selection"]["curated_case_count"] == 5
    assert curated["selection"]["rejection_counts"]

    queries = {case.get("query") for case in curated["cases"]}
    assert "REQ LEG FOR PURCH" not in queries
    assert "MEETING OPEN" not in queries
    assert "Schauer Group" in queries
    assert "Northstar Civic Systems" in queries or "GPD Group" in queries

    rejected_queries = {
        item["query"] for item in curated["selection"]["rejected_lexical_cases"]
    }
    assert {"REQ LEG FOR PURCH", "MEETING OPEN"} <= rejected_queries
