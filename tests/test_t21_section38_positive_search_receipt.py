from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "akron-2026"


def load(name: str) -> dict:
    return json.loads((EXP / name).read_text())


def sha256_file(name: str) -> str:
    return hashlib.sha256((EXP / name).read_bytes()).hexdigest()


def test_frozen_section38_receipt_pins_pre_observation_and_direct_sources() -> None:
    receipt = load("r1_t21_section38_positive_search_summary.json")
    assert receipt["schema"] == "proofline-akron-t21-section38-positive-search-receipt/v1"
    assert receipt["canonical_measurement"]["head_sha"] == "f34ca25bb335d09de861fc9a5309eed06edb7ca0"
    assert receipt["canonical_measurement"]["raw_measurement_sha256"] == "89297c93bd8413a0480466ec6d3947be6dc2a6693b713793a2e797c35e0ded2b"

    assert receipt["source_receipts"]["plan"]["pre_observation_commit"] == "7b5c5a514fed0786f83029bc6bd2977d2840485e"
    assert receipt["source_receipts"]["plan"]["file_sha256"] == sha256_file("r1_t21_section38_positive_search_plan.json")
    assert receipt["source_receipts"]["discovery"]["file_sha256"] == sha256_file("r1_t21_section38_discovery_observation.json")
    assert receipt["source_receipts"]["inventory"]["file_sha256"] == sha256_file("r1_t21_disposition_surface_inventory_summary.json")

    assert receipt["counts"] == {
        "direct_candidate_retrieval_count": 1,
        "frozen_discovery_query_count": 4,
        "section38_terminal_positive_candidate_count": 0,
        "target_identity_candidate_count": 1,
        "unique_discovered_candidate_count": 1,
    }

    control = receipt["positive_control"]
    assert control["sha256"] == "813b1c9c383dafe03e1fd1850a435696000c5bb99ff6ca382c88c745ee3eab04"
    assert control["text_sha256"] == "ffe94a961479168bc45d3b6349492d2acb079f941edb09c2f0187158830ad83e"
    assert control["classification"]["all_required_section38_markers_present"] is True
    assert control["classification"]["identity_hits"] == []
    assert control["classification"]["terminal_positive"] is False

    assert len(receipt["target_candidates"]) == 1
    target = receipt["target_candidates"][0]
    assert target["requested_url"].endswith("advertise%20for%203.9%20public%20hearings.pdf")
    assert target["sha256"] == "9125a5aa0267a53dafcb1378e5af78296cb34eb9a849988edfc441ddf4547cb4"
    assert target["text_sha256"] == "5414cfcd78b68e6cdb83e4fc98318b93c16538954d3be78862ecd699e246f5ff"
    assert target["classification"]["identity_hits"] == [
        "exact_address",
        "distinctive_use_tokens_and_location",
    ]
    assert target["classification"]["section38_marker_hits"] == ["Clerk of Council"]
    assert target["classification"]["terminal_positive"] is False

    assert receipt["candidate_population_signature_sha256"] == "e3df9cdf4c11e1f5c1e8e0b1e55c9c8c8ebf5970c0bb81f72420b12b7e97360a"
    assert receipt["measurement_signature_sha256"] == "7d4bb85187f5d90c90cd8b4a086ff118920f6994fcf509646f1d0d6c6ac07c63"
    assert receipt["outcome"]["status"] == "unknown"
    assert "Clerk public-record request" in receipt["next_stage"]
    assert receipt["authority_boundary"]["search_engine_nonfinding_is_disposition_evidence"] is False
    assert receipt["authority_boundary"]["notice_absence_is_non_passage"] is False
    assert receipt["authority_boundary"]["post_observation_query_expansion_performed"] is False
