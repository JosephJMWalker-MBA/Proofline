import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("experiments/akron-2026/export_t21_april27_contextual_reading_corpus.py")
POPULATION = Path("experiments/akron-2026/r1_t21_april27_contextual_reading_population.json")
SELECTION = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def _module():
    spec = importlib.util.spec_from_file_location("t21_contextual_reading_export", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contextual_reading_population_contract_is_exact():
    module = _module()
    population = json.loads(POPULATION.read_text(encoding="utf-8"))
    rows = module.population_rows(population)
    assert len(rows) == 20
    assert [row["publish_id"] for row in rows] == list(range(102587, 102607))
    assert sum(row["page_count"] for row in rows) == 88
    assert sum(row["native_low_quality_page_count"] for row in rows) == 41
    assert sum(row["native_nonblank_page_count"] for row in rows) == 47


def test_contextual_reading_population_rejects_artifact_drift():
    module = _module()
    population = json.loads(POPULATION.read_text(encoding="utf-8"))
    drifted = json.loads(json.dumps(population))
    drifted["documents"][0]["artifact_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="population signature drifted"):
        module.population_rows(drifted)


def test_contextual_reading_selection_remains_original_20_document_set():
    module = _module()
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    assert selection["selection_signature_sha256"] == module.EXPECTED_SELECTION_SIGNATURE
    assert selection["selected_document_count"] == 20
    assert selection["selection_method"]["content_blind"] is True
