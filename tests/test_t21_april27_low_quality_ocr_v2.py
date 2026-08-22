import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path("experiments/akron-2026/recover_t21_april27_low_quality_ocr_v2.py")
LOW = Path("experiments/akron-2026/r1_t21_april27_low_quality_ocr_selection_v2.json")
RECEIPT = Path("experiments/akron-2026/r1_t21_april27_supporting_document_acquisition_summary_v2.json")
FULL = Path("experiments/akron-2026/r1_t21_april27_supporting_document_selection.json")


def _module():
    spec = importlib.util.spec_from_file_location("t21_april27_low_quality_ocr_v2", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corrected_inputs_round_trip_without_v1_receipt():
    module = _module()
    rows = module.verify_frozen_inputs(
        low_selection=json.loads(LOW.read_text(encoding="utf-8")),
        receipt=json.loads(RECEIPT.read_text(encoding="utf-8")),
        full_selection=json.loads(FULL.read_text(encoding="utf-8")),
    )
    assert [row["publish_id"] for row in rows] == [102589, 102590, 102593, 102597]
    assert sum(row["page_count"] for row in rows) == 48
    assert sum(row["native_low_quality_page_count"] for row in rows) == 41


def test_corrected_receipt_or_selection_drift_fails_closed():
    module = _module()
    low = json.loads(LOW.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    full = json.loads(FULL.read_text(encoding="utf-8"))

    drifted = json.loads(json.dumps(low))
    drifted["selected_artifacts"][1]["source_uri_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        module.low_selection_rows(drifted)

    drifted_receipt = json.loads(json.dumps(receipt))
    drifted_receipt["correction"]["canonical_measurement_changed"] = True
    with pytest.raises(ValueError, match="canonical measurement"):
        module.verify_frozen_inputs(low_selection=low, receipt=drifted_receipt, full_selection=full)
