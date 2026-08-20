from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "akron-2026"
        / "measure_money_parser_delta.py"
    )
    spec = importlib.util.spec_from_file_location("akron_money_parser_delta", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen() -> dict:
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "akron-2026"
        / "r1_t8_money_facts.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _current_profile_from_frozen(frozen: dict) -> dict:
    current_money = []
    for fact in frozen["facts"]:
        source = frozen["sources"][fact["source"]]
        current = {
            "source_uri": source["source_uri"],
            "artifact_id": source["artifact_id"],
            "locator": fact["locator"],
            "char_start": fact["char_start"],
            "char_end": fact["char_end"],
            "raw_text": fact["raw_text"],
            "normalized_text": fact["normalized_text"],
        }
        if (fact["source"], fact["locator"], fact["char_start"]) == ("s4", "page:4", 378):
            current.update(
                raw_text="$138MM",
                normalized_text="138000000.00",
                char_end=384,
            )
        if (fact["source"], fact["locator"], fact["char_start"]) == ("s5", "page:2", 1207):
            current.update(
                raw_text="$ 51 ,780.00",
                normalized_text="51780.00",
                char_end=1219,
            )
        current_money.append(current)

    attachments = [
        {
            "source_uri": meta["source_uri"],
            "artifact": {"artifact_id": meta["artifact_id"]},
        }
        for meta in frozen["sources"].values()
    ]
    return {
        "post_ocr": {
            "structured_build": {"parser_version": "proofline-structured/v2"},
            "facts": {"money": current_money},
        },
        "attachments": attachments,
    }


def test_t10_delta_accepts_only_the_two_proven_parser_repairs() -> None:
    module = _load_module()
    frozen = _frozen()
    result = module.measure_delta(frozen, _current_profile_from_frozen(frozen))

    assert result["fact_count"] == 31
    assert result["unchanged_fact_count"] == 29
    assert result["changed_fact_count"] == 2
    assert result["unexpected_changes"] == []
    assert result["missing_expected_changes"] == []


def test_t10_delta_rejects_unrelated_fact_drift() -> None:
    module = _load_module()
    frozen = _frozen()
    current = _current_profile_from_frozen(frozen)
    mutated = deepcopy(current)
    mutated["post_ocr"]["facts"]["money"][0]["normalized_text"] = "999999.00"

    with pytest.raises(RuntimeError, match="unexpected parser changes"):
        module.measure_delta(frozen, mutated)
