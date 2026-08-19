"""Evidence-local structured fact packets for recurrence clusters.

Packets enrich recurrence candidates for human inspection without promoting similarity or
recurrence into Gold observations. Facts are included only when their explicit character span
is fully contained inside the corresponding segment span.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .recurrence import RecurrenceCluster, RecurrenceResult, SegmentRecurrenceClusterer
from .segment_similarity import SegmentOccurrence
from .structured import StructuredHit, StructuredIndex

_METHOD = "recurrence_evidence_packet/v1"


@dataclass(frozen=True, slots=True)
class FactValue:
    fact_type: str
    normalized_text: str
    unit: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SegmentFact:
    fact_id: str
    evidence_id: str
    artifact_id: str
    locator: str
    fact_type: str
    raw_text: str
    normalized_text: str | None
    numeric_value: float | None
    unit: str | None
    char_start: int
    char_end: int
    segment_relative_start: int
    segment_relative_end: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecurrenceOccurrencePacket:
    occurrence: SegmentOccurrence
    facts: tuple[SegmentFact, ...]

    def to_dict(self) -> dict:
        return {
            "occurrence": self.occurrence.to_dict(),
            "facts": [fact.to_dict() for fact in self.facts],
        }


@dataclass(frozen=True, slots=True)
class RecurrenceEvidencePacket:
    packet_method: str
    cluster: RecurrenceCluster
    occurrences: tuple[RecurrenceOccurrencePacket, ...]
    values_present_in_all_occurrences: tuple[FactValue, ...]
    values_not_present_in_all_occurrences: tuple[FactValue, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "packet_method": self.packet_method,
            "cluster": self.cluster.to_dict(),
            "occurrences": [item.to_dict() for item in self.occurrences],
            "values_present_in_all_occurrences": [
                value.to_dict() for value in self.values_present_in_all_occurrences
            ],
            "values_not_present_in_all_occurrences": [
                value.to_dict() for value in self.values_not_present_in_all_occurrences
            ],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class RecurrencePacketResult:
    method: str
    recurrence_method: str
    cluster_count: int
    returned_packet_count: int
    packets: tuple[RecurrenceEvidencePacket, ...]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "recurrence_method": self.recurrence_method,
            "cluster_count": self.cluster_count,
            "returned_packet_count": self.returned_packet_count,
            "packets": [packet.to_dict() for packet in self.packets],
        }


def _fact_value(hit: StructuredHit) -> FactValue:
    normalized = hit.normalized_text
    if normalized is None:
        normalized = " ".join(hit.raw_text.split()).casefold()
    return FactValue(
        fact_type=hit.fact_type,
        normalized_text=normalized,
        unit=hit.unit,
    )


def _value_sort_key(value: FactValue) -> tuple[str, str, str]:
    return (value.fact_type, value.normalized_text, value.unit or "")


class RecurrenceEvidencePacketBuilder:
    """Attach span-contained structured facts to deterministic recurrence clusters."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.recurrence = SegmentRecurrenceClusterer(self.state_dir)
        self.structured = StructuredIndex(self.state_dir)

    def _facts_within_span(
        self,
        evidence_id: str,
        char_start: int,
        char_end: int,
    ) -> tuple[StructuredHit, ...]:
        """Return every current structured fact fully contained in one evidence span.

        This packet-local query intentionally has no presentation limit: packet completeness
        must not depend on a hidden row ceiling. Facts without explicit character offsets are
        excluded because they cannot be attributed to a subrange of an evidence unit.
        """
        if not evidence_id.strip():
            raise ValueError("evidence_id cannot be empty")
        if char_start < 0:
            raise ValueError("char_start cannot be negative")
        if char_end <= char_start:
            raise ValueError("char_end must be greater than char_start")
        build = self.structured.current_build()
        if build is None:
            raise RuntimeError("structured index has not been built; run `proofline index` first")
        with self.structured.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evidence_facts
                WHERE build_id = ?
                  AND evidence_id = ?
                  AND char_start IS NOT NULL
                  AND char_end IS NOT NULL
                  AND char_start >= ?
                  AND char_end <= ?
                ORDER BY char_start, char_end, fact_type, fact_id
                """,
                (build["build_id"], evidence_id, char_start, char_end),
            ).fetchall()
        return tuple(self.structured._hits(rows))

    @staticmethod
    def _segment_fact(hit: StructuredHit, occurrence: SegmentOccurrence) -> SegmentFact:
        if hit.char_start is None or hit.char_end is None:
            raise ValueError("spanless fact cannot be attached to a segment packet")
        segment = occurrence.segment
        if hit.evidence_id != segment.evidence_id:
            raise ValueError("fact evidence does not match segment evidence")
        if hit.char_start < segment.char_start or hit.char_end > segment.char_end:
            raise ValueError("fact span is not contained in segment span")
        return SegmentFact(
            fact_id=hit.fact_id,
            evidence_id=hit.evidence_id,
            artifact_id=hit.artifact_id,
            locator=hit.locator,
            fact_type=hit.fact_type,
            raw_text=hit.raw_text,
            normalized_text=hit.normalized_text,
            numeric_value=hit.numeric_value,
            unit=hit.unit,
            char_start=int(hit.char_start),
            char_end=int(hit.char_end),
            segment_relative_start=int(hit.char_start) - segment.char_start,
            segment_relative_end=int(hit.char_end) - segment.char_start,
        )

    def packet_for_cluster(self, cluster: RecurrenceCluster) -> RecurrenceEvidencePacket:
        occurrence_packets: list[RecurrenceOccurrencePacket] = []
        value_sets: list[set[FactValue]] = []
        for occurrence in cluster.occurrences:
            segment = occurrence.segment
            hits = self._facts_within_span(
                segment.evidence_id,
                segment.char_start,
                segment.char_end,
            )
            facts = tuple(self._segment_fact(hit, occurrence) for hit in hits)
            occurrence_packets.append(
                RecurrenceOccurrencePacket(occurrence=occurrence, facts=facts)
            )
            value_sets.append({_fact_value(hit) for hit in hits})

        if value_sets:
            present_all = set.intersection(*value_sets)
            present_any = set.union(*value_sets)
        else:
            present_all = set()
            present_any = set()
        not_all = present_any - present_all

        return RecurrenceEvidencePacket(
            packet_method=_METHOD,
            cluster=cluster,
            occurrences=tuple(occurrence_packets),
            values_present_in_all_occurrences=tuple(sorted(present_all, key=_value_sort_key)),
            values_not_present_in_all_occurrences=tuple(sorted(not_all, key=_value_sort_key)),
            limitations=(
                "Fact aggregation is presence-based; it does not infer chronology, direction of change, or causation.",
                "Only structured facts with explicit character spans fully contained in the segment are included; spanless facts are omitted.",
                "A recurrence evidence packet is an inspection aid, not a Gold observation or allegation.",
            ),
        )

    def from_recurrence_result(self, result: RecurrenceResult) -> RecurrencePacketResult:
        packets = tuple(self.packet_for_cluster(cluster) for cluster in result.clusters)
        return RecurrencePacketResult(
            method=_METHOD,
            recurrence_method=result.method,
            cluster_count=result.cluster_count,
            returned_packet_count=len(packets),
            packets=packets,
        )

    def find(
        self,
        *,
        threshold: float = 0.60,
        shingle_size: int = 3,
        min_shared_shingles: int = 3,
        max_shingle_frequency: int = 64,
        rule_name: str | None = None,
        segment_type: str | None = None,
        min_occurrences: int = 2,
        limit: int | None = 100,
    ) -> RecurrencePacketResult:
        result = self.recurrence.find(
            threshold=threshold,
            shingle_size=shingle_size,
            min_shared_shingles=min_shared_shingles,
            max_shingle_frequency=max_shingle_frequency,
            rule_name=rule_name,
            segment_type=segment_type,
            min_occurrences=min_occurrences,
            limit=limit,
        )
        return self.from_recurrence_result(result)
