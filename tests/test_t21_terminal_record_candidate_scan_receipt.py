import json
from pathlib import Path

RECEIPT = Path("experiments/akron-2026/r1_t21_terminal_record_candidate_scan_summary.json")


def test_t21_terminal_record_candidate_scan_receipt_is_frozen_and_non_terminal():
    p = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert p["schema"] == "proofline-akron-t21-terminal-record-candidate-scan-receipt/v1"
    assert p["stage"] == "post_measurement_pre_disposition_receipt"
    assert p["observation_time"] == "2026-08-24T20:51:00-04:00"

    run = p["canonical_run"]
    assert run["workflow_run_id"] == 32800525222
    assert run["job_id"] == 97660306254
    assert run["head_sha"] == "52819316e3c057850aac693de52041c167332498"
    assert run["artifact_id"] == 9546329454
    assert run["artifact_digest"] == "sha256:023b6bb47eadbcc73803c7a41e8a1b32ef713a32964f10ab454d8a5cad2ea410"
    assert run["raw_measurement_json_sha256"] == "b3c846e6f3eec81e96f9c2e0008b6ddb0d4bec182d0e8f5aee9e093451a0b952"
    assert run["raw_measurement_byte_size"] == 254275

    assert p["target"] == {
        "introduced_on_or_after": "2026-02-23",
        "ordinance_title_sha256": "484e8b7cd5bc9957938bc6aaf98063ae0c93ffb1bc2df86b10205501437a1c84",
        "planning_case": {"kind": "planning_case", "normalized_key": "PC-2025-80-CU"},
    }

    assert p["scan_window"] == {
        "eligible_marked_agenda_count": 26,
        "meetings_before_target_introduction_excluded": 6,
        "publisher_meetings_after_observation_excluded": 1,
    }
    assert p["counts"] == {
        "marked_agenda_count": 26,
        "numbered_vote_candidate_count": 215,
        "target_exact_title_match_count": 0,
        "terminal_outcomes_assigned": 0,
    }
    assert p["source_population_signature_sha256"] == "089c1b0c4104ecb6752cc2c1bdd34355abca40b29c63a1c989a935842ed0eec5"
    assert p["candidate_population_signature_sha256"] == "43cbba8bdcfde7ce4a2d037a29087946d37a28bb8affd88ff6806329c163f848"

    sources = p["source_receipts"]
    assert len(sources) == 26
    assert len({row["meeting_id"] for row in sources}) == 26
    assert len({row["artifact_sha256"] for row in sources}) == 26
    assert sum(row["candidate_count"] for row in sources) == 215
    assert p["target_matches"] == []

    outcome = p["outcome"]
    assert outcome["status"] == "unknown"
    assert "not a terminal disposition" in outcome["reason"]

    boundary = p["authority_boundary"]
    assert boundary == {
        "absence_treated_as_disposition": False,
        "candidate_is_review_target_only": True,
        "causality_assigned": False,
        "detector_authorized": False,
        "exact_title_match_is_relationship_evidence_only": True,
        "lead_count": None,
        "meeting_occurrence_asserted": False,
        "terminal_outcome_assigned": False,
        "vote_arithmetic_interpreted": False,
    }

    guards = p["receipt_guards"]
    assert guards["complete_eligible_marked_agenda_coverage_required"] is True
    assert guards["source_artifact_sha256_frozen"] is True
    assert guards["candidate_population_signature_frozen"] is True
    assert guards["exact_raw_measurement_sha256_frozen"] is True
    assert guards["zero_match_is_not_disposition"] is True
