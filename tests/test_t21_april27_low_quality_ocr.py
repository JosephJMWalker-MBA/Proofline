import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path("experiments/akron-2026/recover_t21_april27_low_quality_ocr.py")
LOW_SELECTION = Path("experiments/akron-2026/r1_t21_april27_low_quality_ocr_selection.json")
RECEIPT = Path("experiments/akron-2026/r1_t21_april27_supporting_document_acquisition_summary.json")
FULL_SELECTION = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def _module():
    spec = importlib.util.spec_from_file_location("t21_april27_low_quality_ocr", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_low_quality_ocr_selection_matches_receipt():
    module = _module()
    rows = module.verify_frozen_inputs(
        low_selection=json.loads(LOW_SELECTION.read_text(encoding="utf-8")),
        receipt=json.loads(RECEIPT.read_text(encoding="utf-8")),
        full_selection=json.loads(FULL_SELECTION.read_text(encoding="utf-8")),
    )
    assert [row["publish_id"] for row in rows] == [102589, 102590, 102593, 102597]
    assert sum(row["page_count"] for row in rows) == 48
    assert sum(row["native_low_quality_page_count"] for row in rows) == 41


def test_low_quality_selection_rejects_semantic_or_count_drift():
    module = _module()
    selection = json.loads(LOW_SELECTION.read_text(encoding="utf-8"))

    drifted = json.loads(json.dumps(selection))
    drifted["selection_method"] = "manual"
    with pytest.raises(ValueError, match="selection method drifted"):
        module.low_selection_rows(drifted)

    drifted = json.loads(json.dumps(selection))
    drifted["selected_artifacts"][0]["native_low_quality_page_count"] = 32
    with pytest.raises(ValueError):
        module.low_selection_rows(drifted)
