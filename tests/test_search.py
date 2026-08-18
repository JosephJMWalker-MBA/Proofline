from pathlib import Path

from proofline import Ingestor
from proofline.evaluation import RetrievalEvaluator, load_retrieval_suite
from proofline.search import SearchIndex, normalize_lexical_query
from tests.fixture_corpus import build_fixture_corpus


def _seed_search_corpus(tmp_path):
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
    ingestor.ingest(
        corpus / manifest["formula_workbook"],
        source_uri="https://fixtures.proofline.local/formula.xlsx",
        native_identifier="XLSX-FORMULA",
    )
    return state


def test_fts_index_returns_provenance_backed_hits(tmp_path) -> None:
    state = _seed_search_corpus(tmp_path)
    index = SearchIndex(state)
    build = index.rebuild()
    assert build.evidence_count == 5

    hits = index.search("Contract award 250 000", limit=5)
    assert hits
    assert hits[0].locator == "page:1"
    assert hits[0].sources[0]["source_uri"] == "https://fixtures.proofline.local/born-digital.pdf"
    assert hits[0].build_id == build.build_id

    native = index.lookup_native_identifier("CSV-B")
    assert {hit.locator for hit in native} == {"sheet:CSV!A1:C1", "sheet:CSV!A2:C2"}


def test_query_normalization_is_deterministic_and_fts_safe() -> None:
    assert normalize_lexical_query("C-002 / Lakeview Systems") == (
        '"c" AND "002" AND "lakeview" AND "systems"'
    )


def test_retrieval_benchmark_measures_known_evidence_targets(tmp_path) -> None:
    state = _seed_search_corpus(tmp_path)
    index = SearchIndex(state)
    index.rebuild()

    suite = load_retrieval_suite(Path(__file__).with_name("retrieval_eval.json"))
    result = RetrievalEvaluator(state).run(suite, k=5)

    assert result.cases == 3
    assert result.unresolved_target_count == 0
    assert result.hit_rate_at_k == 1.0
    assert result.target_recall_at_k == 1.0
    assert result.provenance_validity == 1.0
