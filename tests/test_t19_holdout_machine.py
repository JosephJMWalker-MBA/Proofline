from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def _module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, EXP / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t19_holdout_helpers_import_and_pin_frozen_contracts() -> None:
    sync = _module("proofline_t19_sync_test", "sync_t19_attachment_holdout.py")
    evaluate = _module("proofline_t19_eval_test", "evaluate_local_grouping_holdout.py")
    validate = _module("proofline_t19_validate_test", "validate_local_grouping_holdout.py")

    expected = "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"
    assert sync.EXPECTED_SELECTED_SIGNATURE == expected
    assert evaluate.EXPECTED_SELECTED_SIGNATURE == expected
    assert validate.SELECTED_SIGNATURE == expected
    assert evaluate.LOCAL_GROUPING_METHOD == "proofline-local-grouping/nearest-components-v1"
    assert evaluate.PARSER_VERSION == "proofline-structured/v3"


def test_t19_sync_signature_matches_frozen_identity_hashes() -> None:
    sync = _module("proofline_t19_sync_signature_test", "sync_t19_attachment_holdout.py")
    frozen = json.loads((EXP / "r1_t19_future_holdout_sources.json").read_text(encoding="utf-8"))
    hashes = frozen["selected"]["source_uri_sha256"]
    assert sync._signature(hashes) == frozen["selected"]["signature_sha256"]


def test_t19_holdout_money_parser_smoke_is_current_v3() -> None:
    evaluate = _module("proofline_t19_eval_money_test", "evaluate_local_grouping_holdout.py")
    facts = evaluate._money_facts("Amount: $1,250.00 and fee: $75")
    assert [item["normalized_text"] for item in facts] == ["1250.00", "75.00"]
