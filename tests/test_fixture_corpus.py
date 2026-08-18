from proofline import Ingestor, ProoflineStore, sha256_file
from proofline.extractors import text_quality
from tests.fixture_corpus import build_fixture_corpus


def test_fixture_corpus_exercises_duplicate_scan_and_corruption(tmp_path) -> None:
    corpus = tmp_path / "corpus"
    manifest = build_fixture_corpus(corpus)

    assert sha256_file(corpus / manifest["born_digital_pdf"]) == sha256_file(
        corpus / manifest["exact_duplicate"]
    )

    scan_state = tmp_path / "scan_state"
    scan = Ingestor(scan_state).ingest(corpus / manifest["scanned_pdf"])
    assert scan.evidence_units_seen == 1
    assert ProoflineStore(scan_state / "proofline.db").status()["needs_review"] == 1

    corrupt_state = tmp_path / "corrupt_state"
    corrupt = Ingestor(corrupt_state).ingest(corpus / manifest["corrupted_pdf"])
    assert corrupt.new_artifact is True
    assert any("native extraction failed" in warning for warning in corrupt.warnings)
    assert (corrupt_state / corrupt.stored_path).exists()


def test_text_quality_is_unicode_aware() -> None:
    assert text_quality("政府采购记录 合同金额 250000") >= 0.70
