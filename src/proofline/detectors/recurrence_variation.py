"""Promote narrowly eligible recurrence fact variations into candidate observations.

The detector is deliberately conservative. Recurrence alone is not an observation worthy of
Gold storage, and a missing/low-quality extraction must never masquerade as a changed fact.
An eligible candidate therefore requires distinct publisher families, multiple evidence units,
structured facts in every occurrence, at least one fact value common to every occurrence, and
at least one fact value whose presence varies across occurrences.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ..hashing import stable_id
from ..models import EvidenceReference, Observation
from ..recurrence_packets import FactValue, RecurrenceEvidencePacket
from ..storage import ProoflineStore

_METHOD = "recurrence_fact_variation/v1"


@dataclass(frozen=True, slots=True)
class RecurrenceVariationDecision:
    eligible: bool
    reason: str
    input_fingerprint: str | None = None
    minimum_quality: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecurrenceVariationCandidate:
    cluster_id: str
    input_fingerprint: str
    observation: Observation
    common_values: tuple[FactValue, ...]
    varying_values: tuple[FactValue, ...]
    possible_ordinary_explanations: tuple[str, ...]
    questions_worth_asking: tuple[str, ...]
    method: str = _METHOD

    def __post_init__(self) -> None:
        if not self.possible_ordinary_explanations:
            raise ValueError("candidate must include at least one possible ordinary explanation")
        if not self.questions_worth_asking:
            raise ValueError("candidate must include at least one question worth asking")

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "input_fingerprint": self.input_fingerprint,
            "method": self.method,
            "observation": asdict(self.observation),
            "common_values": [value.to_dict() for value in self.common_values],
            "varying_values": [value.to_dict() for value in self.varying_values],
            "possible_ordinary_explanations": list(self.possible_ordinary_explanations),
            "questions_worth_asking": list(self.questions_worth_asking),
        }


def _excerpt(text: str, *, limit: int = 700) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _fact_token(value: FactValue) -> str:
    return f"{value.fact_type}:{value.normalized_text}:{value.unit or ''}"


def _preferred_extraction_rows(
    store: ProoflineStore,
    evidence_ids: tuple[str, ...],
) -> dict[str, dict]:
    if not evidence_ids:
        return {}
    placeholders = ",".join("?" for _ in evidence_ids)
    with store.connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                eu.evidence_id,
                best.extraction_id,
                best.quality_score,
                best.method,
                best.software_version,
                best.model_version
            FROM evidence_units eu
            LEFT JOIN evidence_extractions best
              ON best.extraction_id = (
                SELECT ee.extraction_id
                FROM evidence_extractions ee
                WHERE ee.evidence_id = eu.evidence_id
                ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                         ee.occurred_at DESC,
                         ee.rowid DESC
                LIMIT 1
              )
            WHERE eu.evidence_id IN ({placeholders})
            ORDER BY eu.evidence_id
            """,
            evidence_ids,
        ).fetchall()
    return {str(row["evidence_id"]): dict(row) for row in rows}


def _structured_parser_version(store: ProoflineStore) -> str:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT parser_version
            FROM structured_index_builds
            ORDER BY built_at DESC, rowid DESC
            LIMIT 1
            """
        ).fetchone()
    return str(row["parser_version"]) if row else "unknown"


def _ordinary_explanations(packet: RecurrenceEvidencePacket) -> tuple[str, ...]:
    types = {value.fact_type for value in packet.values_not_present_in_all_occurrences}
    values: list[str] = []
    if "money" in types:
        values.append(
            "A routine amendment, scope or quantity change, renewal, proration, corrected amount, or separate transaction using similar boilerplate may explain the monetary variation."
        )
    if "date" in types:
        values.append(
            "A routine deadline, meeting date, effective date, scheduling change, or correction may explain the date variation."
        )
    if "identifier" in types:
        values.append(
            "The similar language may describe separate records or transactions whose identifiers legitimately differ."
        )
    values.append(
        "Near-duplicate agenda language can be routine carry-forward or reused administrative language rather than evidence that the occurrences describe one continuing matter."
    )
    return tuple(dict.fromkeys(values))


def _questions(packet: RecurrenceEvidencePacket) -> tuple[str, ...]:
    types = {value.fact_type for value in packet.values_not_present_in_all_occurrences}
    questions = [
        "Do the underlying ordinances, contracts, minutes, or attachments identify these occurrences as the same matter or as separate matters using similar language?",
        "Is there a published amendment, correction, renewal, or other record that explains why the structured facts differ?",
    ]
    if "date" in types:
        questions.append("What semantic role does each differing date play in its source record?")
    if "money" in types:
        questions.append("Do the differing monetary values represent the same field and scope, or different components of the transaction?")
    return tuple(questions)


def evaluate_recurrence_variation(
    store: ProoflineStore,
    packet: RecurrenceEvidencePacket,
    *,
    min_quality: float = 0.70,
) -> tuple[RecurrenceVariationDecision, RecurrenceVariationCandidate | None]:
    """Evaluate one recurrence packet and optionally build a candidate Gold observation."""
    if not 0.0 <= min_quality <= 1.0:
        raise ValueError("min_quality must be between 0 and 1")
    cluster = packet.cluster
    if cluster.family_count < 2:
        return RecurrenceVariationDecision(False, "requires_multiple_source_families"), None
    if cluster.evidence_count < 2:
        return RecurrenceVariationDecision(False, "requires_multiple_evidence_units"), None
    if not packet.values_not_present_in_all_occurrences:
        return RecurrenceVariationDecision(False, "no_structured_fact_variation"), None
    if not packet.values_present_in_all_occurrences:
        return RecurrenceVariationDecision(False, "no_common_structured_fact_anchor"), None
    if any(not item.facts for item in packet.occurrences):
        return RecurrenceVariationDecision(False, "occurrence_missing_structured_facts"), None

    evidence_ids = tuple(sorted({item.occurrence.segment.evidence_id for item in packet.occurrences}))
    extraction_rows = _preferred_extraction_rows(store, evidence_ids)
    if len(extraction_rows) != len(evidence_ids):
        return RecurrenceVariationDecision(False, "missing_preferred_extraction"), None
    qualities: list[float] = []
    for evidence_id in evidence_ids:
        row = extraction_rows[evidence_id]
        quality = row.get("quality_score")
        if quality is None:
            return RecurrenceVariationDecision(False, "unknown_extraction_quality"), None
        qualities.append(float(quality))
    minimum_quality = min(qualities)
    if minimum_quality < min_quality:
        return (
            RecurrenceVariationDecision(
                False,
                "extraction_quality_below_threshold",
                minimum_quality=minimum_quality,
            ),
            None,
        )

    parser_version = _structured_parser_version(store)
    fingerprint_parts: list[str] = [
        packet.packet_method,
        cluster.method,
        cluster.similarity_method,
        cluster.cluster_id,
        parser_version,
    ]
    for occurrence in sorted(
        packet.occurrences,
        key=lambda item: (item.occurrence.family_id, item.occurrence.segment.segment_id),
    ):
        segment = occurrence.occurrence.segment
        row = extraction_rows[segment.evidence_id]
        fingerprint_parts.extend(
            [
                occurrence.occurrence.family_id,
                segment.segment_id,
                segment.evidence_id,
                str(row.get("extraction_id") or "none"),
            ]
        )
    fingerprint_parts.extend(
        f"common:{_fact_token(value)}" for value in packet.values_present_in_all_occurrences
    )
    fingerprint_parts.extend(
        f"varying:{_fact_token(value)}" for value in packet.values_not_present_in_all_occurrences
    )
    input_fingerprint = stable_id("recurrence-variation-inputs", *fingerprint_parts)

    refs: list[EvidenceReference] = []
    seen: set[str] = set()
    for occurrence in packet.occurrences:
        segment = occurrence.occurrence.segment
        if segment.evidence_id in seen:
            continue
        seen.add(segment.evidence_id)
        refs.append(
            EvidenceReference(
                evidence_id=segment.evidence_id,
                artifact_id=segment.artifact_id,
                locator=segment.locator,
                excerpt=_excerpt(segment.raw_text),
            )
        )

    common_text = [_fact_token(value) for value in packet.values_present_in_all_occurrences]
    varying_text = [_fact_token(value) for value in packet.values_not_present_in_all_occurrences]
    ordinary = _ordinary_explanations(packet)
    questions = _questions(packet)
    observation = Observation(
        observation_id=stable_id(
            "observation",
            "recurrence_fact_variation",
            cluster.cluster_id,
            input_fingerprint,
            _METHOD,
        ),
        observation_type="recurrence_structured_fact_variation",
        explanation=(
            f"Near-duplicate agenda language recurs across {cluster.family_count} distinct publisher source families and {cluster.evidence_count} evidence units. "
            f"Structured values present in every occurrence={common_text!r}; values not present in every occurrence={varying_text!r}."
        ),
        evidence_refs=tuple(refs),
        method=_METHOD,
        uncertainty=(
            "Fact comparison is presence-based and does not establish chronology, field equivalence, causation, materiality, or that the occurrences refer to the same underlying matter."
        ),
        limitations=(
            "Recurrence uses lexical single-linkage; endpoint occurrences may be connected through another occurrence rather than a direct similarity edge.",
            "Source-family separation prevents publisher-backed historical versions from counting as independent recurrence, but similar language can still describe separate routine matters.",
            *(f"Possible ordinary explanation: {item}" for item in ordinary),
            *(f"Question worth asking: {item}" for item in questions),
            f"Gold input fingerprint: {input_fingerprint}",
        ),
    )
    candidate = RecurrenceVariationCandidate(
        cluster_id=cluster.cluster_id,
        input_fingerprint=input_fingerprint,
        observation=observation,
        common_values=packet.values_present_in_all_occurrences,
        varying_values=packet.values_not_present_in_all_occurrences,
        possible_ordinary_explanations=ordinary,
        questions_worth_asking=questions,
    )
    return (
        RecurrenceVariationDecision(
            True,
            "eligible_recurrence_fact_variation",
            input_fingerprint=input_fingerprint,
            minimum_quality=minimum_quality,
        ),
        candidate,
    )
