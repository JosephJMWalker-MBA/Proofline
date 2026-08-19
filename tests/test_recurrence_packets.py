from __future__ import annotations

from proofline import Ingestor, evidence_id_from_locator
from proofline.recurrence_packets import RecurrenceEvidencePacketBuilder
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def test_recurrence_packet_contains_only_facts_inside_each_segment(tmp_path) -> None:
    state = tmp_path / "state"
    rule = SegmentationRule(
        name="board-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
        segment_type="agenda_item",
        min_chars=40,
    )

    totals = ("$200.00", "$200.00", "$250.00")
    for index, total in enumerate(totals, start=1):
        text = (
            f"Meeting preamble amount $999.{index:02d} should not attach to an agenda item.\n"
            "Ordinance 1/2026\n"
            "Enter into a four year contract with Example Systems for a public safety drone "
            f"program with an administrative fee of $100.00 and a total amount of {total}. "
            "Year one is free and later years are billed annually under cooperative purchasing.\n"
            f"Ordinance {index + 10}/2026\n"
            f"Unrelated facilities work has a separate amount of $888.{index:02d} and unique "
            f"scope marker {index} that belongs to a different agenda item.\n"
        )
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/meeting/{index}",
            source_name=f"Board of Control — Meeting {index}",
        )

    structured = StructuredIndex(state)
    structured.rebuild()
    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(rule,)))

    result = RecurrenceEvidencePacketBuilder(state).find(
        rule_name="board-items",
        threshold=0.60,
        shingle_size=3,
        min_shared_shingles=3,
        max_shingle_frequency=64,
        min_occurrences=3,
        limit=None,
    )

    assert result.cluster_count >= 1
    packet = next(
        item for item in result.packets if item.cluster.occurrence_count == 3
    )
    assert packet.packet_method == "recurrence_evidence_packet/v1"
    assert packet.cluster.family_count == 3
    assert len(packet.occurrences) == 3

    for occurrence_packet in packet.occurrences:
        segment = occurrence_packet.occurrence.segment
        values = {fact.normalized_text for fact in occurrence_packet.facts}
        assert "100.00" in values
        assert not any(value and value.startswith("999.") for value in values)
        assert not any(value and value.startswith("888.") for value in values)
        for fact in occurrence_packet.facts:
            assert fact.evidence_id == segment.evidence_id
            assert segment.char_start <= fact.char_start < fact.char_end <= segment.char_end
            assert fact.segment_relative_start == fact.char_start - segment.char_start
            assert fact.segment_relative_end == fact.char_end - segment.char_start

    common = {
        (value.fact_type, value.normalized_text, value.unit)
        for value in packet.values_present_in_all_occurrences
    }
    varying = {
        (value.fact_type, value.normalized_text, value.unit)
        for value in packet.values_not_present_in_all_occurrences
    }
    assert ("money", "100.00", "USD") in common
    assert ("money", "200.00", "USD") in varying
    assert ("money", "250.00", "USD") in varying
    assert not any(value[1].startswith("999.") for value in common | varying)
    assert not any(value[1].startswith("888.") for value in common | varying)
    assert len(packet.limitations) == 3
    assert "presence-based" in packet.limitations[0]
    assert "not a Gold observation" in packet.limitations[2]


def test_structured_within_span_excludes_neighboring_facts(tmp_path) -> None:
    state = tmp_path / "state"
    text = "Outside $999.00.\nInside $123.45 on January 2, 2026.\nOutside $777.00.\n"
    path = tmp_path / "facts.txt"
    path.write_text(text, encoding="utf-8")
    result = Ingestor(state).ingest(
        path,
        source_uri="https://example.gov/facts",
        source_name="Board of Control — Facts",
    )
    index = StructuredIndex(state)
    index.rebuild()

    evidence_id = evidence_id_from_locator(result.artifact_id, "record", "record:1")
    start = text.index("Inside")
    end = text.index("\nOutside $777")
    hits = index.within_span(evidence_id, start, end)
    values = {(hit.fact_type, hit.normalized_text) for hit in hits}
    assert ("money", "123.45") in values
    assert ("date", "2026-01-02") in values
    assert ("money", "999.00") not in values
    assert ("money", "777.00") not in values
