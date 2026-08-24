import importlib.util
from pathlib import Path


SCRIPT = Path("experiments/akron-2026/recover_t21_april27_low_quality_ocr_v3.py")


def _module():
    spec = importlib.util.spec_from_file_location("t21_low_ocr_v3", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_progressive_ocr_accounting_contract_is_explicit():
    module = _module()
    assert module.EXPECTED_PAGE_UNITS_PRESENTED == 48
    assert module.EXPECTED_OCR_ATTEMPTED == 41
    assert module.EXPECTED_OCR_SKIPPED == 7
    assert module.EXPECTED_OCR_ATTEMPTED + module.EXPECTED_OCR_SKIPPED == module.EXPECTED_PAGE_UNITS_PRESENTED


def test_v3_reuses_frozen_v2_population_constants():
    module = _module()
    v2 = module._v2_module()
    assert v2.EXPECTED_ARTIFACT_COUNT == 4
    assert v2.EXPECTED_SOURCE_PAGE_COUNT == 48
    assert v2.EXPECTED_LOW_QUALITY_PAGE_COUNT == 41
    assert v2.EXPECTED_PUBLISH_IDS == [102589, 102590, 102593, 102597]
