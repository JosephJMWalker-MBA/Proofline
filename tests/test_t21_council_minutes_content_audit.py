from __future__ import annotations
import importlib.util
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"experiments"/"akron-2026"/"audit_t21_council_minutes_content.py"
spec=importlib.util.spec_from_file_location("minutes_audit",SCRIPT); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

def test_target_anchors_require_target_local_signal():
    assert "training_eastwood_cooccurrence" in mod.anchor_hits("Proposed Training Facility at Eastwood Avenue")
    assert mod.anchor_hits("Goodyear Boulevard between Eastwood Avenue and Eastland Avenue") == []

def test_block_split_prevents_other_ordinance_passage_leakage():
    text=("LEGAL NOTICE: ORDINANCE authorizing a Conditional Use to establish a defense education training facility at 1928 Eastwood Avenue.\n"
          "A PUBLIC HEARING WAS DECLARED. Fusco polled the Committee for Time.\n"
          "LEGAL NOTICE: ORDINANCE authorizing a Conditional Use to place a shed.\n"
          "Motion by Fusco for passage. Voice vote on final passage and said Ordinance was declared passed.\n")
    blocks=mod.split_blocks(text,["LEGAL NOTICE:"])
    target=[b for b in blocks if mod.anchor_hits(b["text"])][0]
    low=mod.normalize(target["text"]).lower()
    assert "polled the committee for time" in low
    assert "final passage" not in low
    assert "declared passed" not in low
