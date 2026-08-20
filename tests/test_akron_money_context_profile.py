from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "akron-2026"
        / "profile_money_context.py"
    )
    spec = importlib.util.spec_from_file_location("akron_money_context_profile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "akron-2026"
        / "r1_t8_money_facts.json"
    )


def test_frozen_t8_money_population_signature_is_self_consistent() -> None:
    module = _load_module()
    frozen = module._load_frozen(_frozen_path())

    assert frozen["fact_count"] == 31
    assert len(frozen["facts"]) == 31
    assert len(frozen["sources"]) == 7
    assert module._signature(frozen["facts"]) == frozen["signature_sha256"]


def test_frozen_signature_rejects_fact_tampering(tmp_path: Path) -> None:
    module = _load_module()
    payload = json.loads(_frozen_path().read_text(encoding="utf-8"))
    payload["facts"][0]["raw_text"] = "$999,999"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="signature mismatch"):
        module._load_frozen(path)


def test_context_window_preserves_exact_token_anchor() -> None:
    module = _load_module()
    text = "Estimated TOTAL project cost: $400,000. Additional application text follows."
    token = "$400,000"
    start = text.index(token)
    end = start + len(token)

    window = module._context_window(text, start, end, radius=12)

    assert window["token"] == token
    assert window["context_text"] == text[start - 12 : end + 12]
    assert window["before"].endswith("ject cost: ")
    assert window["after"].startswith(". Additional")
    assert len(window["context_sha256"]) == 64
    assert len(window["context_normalized_sha256"]) == 64


def test_context_window_rejects_invalid_ranges() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="invalid fact character range"):
        module._context_window("abc", 1, 5, radius=2)
