"""Deterministic candidate-observation orchestration.

This layer is the boundary between descriptive retrieval/inspection structures and Gold
observations. Detector context is stored append-only so a later trace can reconstruct the
publisher-family and policy inputs that authorized each observation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .detectors.recurrence_variation import (
    RecurrenceVariationCandidate,
    RecurrenceVariationDecision,
    evaluate_recurrence_variation,
)
from .hashing import stable_id
from .recurrence_packets import RecurrenceEvidencePacketBuilder
from .storage import ProoflineStore

_CONTEXT_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS observation_detector_contexts (
    context_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES observations(observation_id),
    detector_method TEXT NOT NULL,
    context_type TEXT NOT NULL,
    context_key TEXT NOT NULL,
    details_json TEXT NOT NULL,
    UNIQUE(observation_id, detector_method, context_type, context_key)
);
CREATE TRIGGER IF NOT EXISTS observation_detector_contexts_no_update
BEFORE UPDATE ON observation_detector_contexts BEGIN
    SELECT RAISE(ABORT, 'observation detector contexts are append-only');
END;
CREATE TRIGGER IF NOT EXISTS observation_detector_contexts_no_delete
BEFORE DELETE ON observation_detector_contexts BEGIN
    SELECT RAISE(ABORT, 'observation detector contexts are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class CandidateObservationItem:
    cluster_id: str
    status: str
    observation_id: str | None
    observation_created: bool
    decision: RecurrenceVariationDecision
    candidate: RecurrenceVariationCandidate | None

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "status": self.status,
            "observation_id": self.observation_id,
            "observation_created": self.observation_created,
            "decision": self.decision.to_dict(),
            "candidate": self.candidate.to_dict() if self.candidate else None,
        }


@dataclass(frozen=True, slots=True)
class CandidateObservationRun:
    detector_method: str
    cluster_count: int
    eligible: int
    observations_created: int
    already_observed: int
    skipped: int
    items: tuple[CandidateObservationItem, ...]

    def to_dict(self) -> dict:
        return {
            "detector_method": self.detector_method,
            "cluster_count": self.cluster_count,
            "eligible": self.eligible,
            "observations_created": self.observations_created,
            "already_observed": self.already_observed,
            "skipped": self.skipped,
            "items": [item.to_dict() for item in self.items],
        }


class CandidateObservationRunner:
    """Run conservative detector policy over recurrence evidence packets."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self.packets = RecurrenceEvidencePacketBuilder(self.state_dir)
        with self.store.connection() as connection:
            connection.executescript(_CONTEXT_SCHEMA)

    @staticmethod
    def _context_details(candidate: RecurrenceVariationCandidate) -> dict:
        packet_cluster = candidate.observation.observation_id
        # Source-family context is reconstructed from the candidate's recurrence packet in
        # _attach_context; this placeholder keeps this helper intentionally data-only.
        return {"observation_id": packet_cluster}

    def _attach_context(self, candidate: RecurrenceVariationCandidate, packet) -> None:
        family_contexts = []
        for occurrence in sorted(
            packet.occurrences,
            key=lambda item: (item.occurrence.family_id, item.occurrence.segment.segment_id),
        ):
            family_contexts.append(
                {
                    "family_id": occurrence.occurrence.family_id,
                    "segment_id": occurrence.occurrence.segment.segment_id,
                    "evidence_id": occurrence.occurrence.segment.evidence_id,
                    "sources": [
                        {
                            "source_id": source.get("source_id"),
                            "source_uri": source.get("source_uri"),
                            "source_name": source.get("source_name"),
                            "native_identifier": source.get("native_identifier"),
                        }
                        for source in occurrence.occurrence.sources
                    ],
                }
            )
        details = {
            "cluster_id": candidate.cluster_id,
            "input_fingerprint": candidate.input_fingerprint,
            "packet_method": packet.packet_method,
            "recurrence_method": packet.cluster.method,
            "similarity_method": packet.cluster.similarity_method,
            "threshold": packet.cluster.threshold,
            "family_count": packet.cluster.family_count,
            "evidence_count": packet.cluster.evidence_count,
            "family_contexts": family_contexts,
            "common_values": [value.to_dict() for value in candidate.common_values],
            "varying_values": [value.to_dict() for value in candidate.varying_values],
            "possible_ordinary_explanations": list(candidate.possible_ordinary_explanations),
            "questions_worth_asking": list(candidate.questions_worth_asking),
        }
        context_id = stable_id(
            "observation-detector-context",
            candidate.observation.observation_id,
            candidate.method,
            candidate.cluster_id,
        )
        with self.store.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO observation_detector_contexts(
                    context_id, observation_id, detector_method, context_type, context_key, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    context_id,
                    candidate.observation.observation_id,
                    candidate.method,
                    "recurrence_cluster",
                    candidate.cluster_id,
                    json.dumps(details, sort_keys=True),
                ),
            )

    def contexts_for_observation(self, observation_id: str) -> list[dict]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT context_id, detector_method, context_type, context_key, details_json
                FROM observation_detector_contexts
                WHERE observation_id = ?
                ORDER BY context_id
                """,
                (observation_id,),
            ).fetchall()
        return [
            {
                "context_id": row["context_id"],
                "detector_method": row["detector_method"],
                "context_type": row["context_type"],
                "context_key": row["context_key"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def run_recurrence_variations(
        self,
        *,
        threshold: float = 0.60,
        shingle_size: int = 3,
        min_shared_shingles: int = 3,
        max_shingle_frequency: int = 64,
        rule_name: str | None = None,
        segment_type: str | None = None,
        min_occurrences: int = 2,
        min_quality: float = 0.70,
    ) -> CandidateObservationRun:
        packet_result = self.packets.find(
            threshold=threshold,
            shingle_size=shingle_size,
            min_shared_shingles=min_shared_shingles,
            max_shingle_frequency=max_shingle_frequency,
            rule_name=rule_name,
            segment_type=segment_type,
            min_occurrences=min_occurrences,
            limit=None,
        )
        items: list[CandidateObservationItem] = []
        detector_method = "recurrence_fact_variation/v1"
        for packet in packet_result.packets:
            decision, candidate = evaluate_recurrence_variation(
                self.store,
                packet,
                min_quality=min_quality,
            )
            if candidate is None:
                items.append(
                    CandidateObservationItem(
                        cluster_id=packet.cluster.cluster_id,
                        status="skipped",
                        observation_id=None,
                        observation_created=False,
                        decision=decision,
                        candidate=None,
                    )
                )
                continue
            created = self.store.add_observation(candidate.observation)
            self._attach_context(candidate, packet)
            items.append(
                CandidateObservationItem(
                    cluster_id=packet.cluster.cluster_id,
                    status="observed" if created else "already_observed",
                    observation_id=candidate.observation.observation_id,
                    observation_created=created,
                    decision=decision,
                    candidate=candidate,
                )
            )

        eligible = sum(item.candidate is not None for item in items)
        created = sum(item.observation_created for item in items)
        already = sum(item.status == "already_observed" for item in items)
        skipped = sum(item.status == "skipped" for item in items)
        return CandidateObservationRun(
            detector_method=detector_method,
            cluster_count=packet_result.cluster_count,
            eligible=eligible,
            observations_created=created,
            already_observed=already,
            skipped=skipped,
            items=tuple(items),
        )
