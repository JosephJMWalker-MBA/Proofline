from __future__ import annotations

import json

import proofline.cli as cli
from proofline import Ingestor, RecurrenceEvidencePacketBuilder
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def test_recurrence_packet_builder_is_exported_from_public_api() -> None:
    assert RecurrenceEvidencePacketBuilder.__module__ == "proofline.recurrence_packets"


def test_recurrence_packets_cli_emits_evidence_local_fact_packet(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    rule = SegmentationRule(
        name="board-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
        segment_type="agenda_item",
        min_chars=30,
    )
    base = (
        "Ordinance 1/2026\n"
        "Enter into a four year contract with Example Systems for a public safety drone "
        "program in the total amount of $299,991.00 with later years costing $99,997.00.\n"
    )
    texts = (
        base,
        base.replace("amount of", "amount of"),
        base.replace("public safety drone program", "public safety BRINCS drone program"),
    )
    for index, text in enumerate(texts, start=1):
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/meeting/{index}",
            source_name=f"Board of Control — Meeting {index}",
        )

    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(rule,)))

    exit_code = cli.main(
        [
            "--state-dir",
            str(state),
            "recurrence-packets",
            "--rule",
            "board-items",
            "--threshold",
            "0.5",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "recurrence_evidence_packet/v1"
    assert payload["recurrence_method"] == "segment_recurrence_connected_components/v1"
    assert payload["cluster_count"] == 1
    assert payload["returned_packet_count"] == 1

    packet = payload["packets"][0]
    assert packet["cluster"]["family_count"] == 3
    assert len(packet["occurrences"]) == 3
    common = {
        (item["fact_type"], item["normalized_text"], item["unit"])
        for item in packet["values_present_in_all_occurrences"]
    }
    assert ("money", "299991.00", "USD") in common
    assert ("money", "99997.00", "USD") in common
    assert "not a Gold observation" in packet["limitations"][-1]
    for occurrence in packet["occurrences"]:
        segment = occurrence["occurrence"]["segment"]
        assert occurrence["facts"]
        for fact in occurrence["facts"]:
            assert fact["evidence_id"] == segment["evidence_id"]
            assert segment["char_start"] <= fact["char_start"] < fact["char_end"] <= segment["char_end"]
