from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "akron-2026" / "measure_t21_passed_legislation_recall_expansion.py"
PLAN = ROOT / "experiments" / "akron-2026" / "r1_t21_passed_legislation_recall_expansion_plan.json"

spec = importlib.util.spec_from_file_location("t21_recall", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_expansion_vocabulary_is_exact_and_frozen() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    actual = tuple((row["request_id"], row["keyword"]["Value"]) for row in plan["requests"])
    assert actual == module.EXPECTED_REQUESTS
    assert plan["selection_rule"]["post_result_term_expansion_allowed"] is False
    assert plan["selection_rule"]["document_retrieval_in_this_stage"] is False
    assert plan["selection_rule"]["opaque_tokens_are_not_stable_identity"] is True


def test_stable_projection_excludes_opaque_token() -> None:
    row = {
        "ID": "opaque-token-a",
        "Name": "O-1-2026 - SOME TITLE",
        "DisplayColumnValues": ["O-1-2026"],
        "Score": 1,
        "Summary": None,
    }
    projection = module.stable_document_projection(row)
    assert "ID" not in projection
    row["ID"] = "opaque-token-b"
    assert module.stable_document_projection(row) == projection


def test_screening_requires_target_combination_not_eastwood_alone() -> None:
    unrelated = {"name": "resurfacing Eastwood Avenue", "display_column_values": None, "score": None, "summary": None}
    target = {"name": "conditional use for a training facility at 1928 Eastwood Avenue", "display_column_values": None, "score": None, "summary": None}
    assert module.screening_hits(unrelated) == []
    hits = module.screening_hits(target)
    assert "street_number_and_location" in hits
    assert "use_and_location" in hits
    assert "action_and_location" in hits


def test_tokens_must_come_from_frozen_title_in_order() -> None:
    title = "authorizing a Conditional Use to establish a defense education training facility at 1928 Eastwood Avenue; and declaring an emergency."
    assert module.tokens_appear_in_order("*training*facility*", title)
    assert module.tokens_appear_in_order("*conditional*use*", title)
    assert not module.tokens_appear_in_order("*facility*training*", title)
