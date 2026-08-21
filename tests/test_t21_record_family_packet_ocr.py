from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]
_SCRIPT = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "recover_t21_record_family_packet_ocr.py"
)
_RECEIPT = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_record_family_evolution_summary.json"
)
_SELECTION = (
    _ROOT
    / "experiments"
    / "akron-2026"
    / "r1_t21_record_family_packet_selection.json"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("t21_packet_ocr", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t21_packet_ocr_requires_the_frozen_pre_ocr_receipt() -> None:
    module = _load_module()
    receipt = json.loads(_RECEIPT.read_text(encoding="utf-8"))
    selection = json.loads(_SELECTION.read_text(encoding="utf-8"))

    module.verify_receipt(receipt, selection)
    assert module.EXPECTED_ARTIFACT_ID == (
        "artifact:87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a"
    )
    assert module.EXPECTED_PAGE_COUNT == 3
    assert module.EXPECTED_PACKET_SOURCE_COUNT == 24

    drifted = copy.deepcopy(receipt)
    drifted["counts"]["unique_bronze_artifact_count"] = 2
    with pytest.raises(ValueError, match="exactly one Bronze artifact"):
        module.verify_receipt(drifted, selection)

    wrong_bytes = copy.deepcopy(receipt)
    wrong_bytes["unique_bronze_packet"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256 drifted"):
        module.verify_receipt(wrong_bytes, selection)


def test_t21_packet_ocr_representative_is_deterministic_from_frozen_selection() -> None:
    module = _load_module()
    selection = json.loads(_SELECTION.read_text(encoding="utf-8"))
    evolution = module._evolution_module()
    selected = evolution._selection_rows(selection)

    assert selected[0] == module.EXPECTED_REPRESENTATIVE
    assert module.EXPECTED_REPRESENTATIVE == {
        "meeting_id": 668,
        "item_id": 46485,
        "publish_id": 100240,
        "source_uri_sha256": (
            "a107c2c3331a4f6f6511b7031dcbef193b92d638692580e904d87b0068f454cc"
        ),
    }


def test_t21_packet_ocr_stage_has_no_semantic_authority_by_construction() -> None:
    module = _load_module()
    assert module.SCHEMA == "proofline-akron-t21-record-family-packet-ocr/v1"
    assert module.STAGE == "raw_packet_ocr_silver_before_contextual_interpretation"
