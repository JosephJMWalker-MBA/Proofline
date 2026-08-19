"""Human-review lead packaging and append-only disposition history.

A lead packet is immutable once created. Human review does not overwrite the machine
observation or mutate the packet; each review decision is appended as a separate event and the
current disposition is derived from the latest event.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .candidate_analysis import CandidateObservationRunner
from .hashing import stable_id
from .models import EvidenceReference, Lead, LeadStatus
from .storage import ProoflineStore

_METHOD = "candidate_observation_lead/v1"
_REVIEWABLE_STATUSES = {
    LeadStatus.TRIAGED,
    LeadStatus.INVESTIGATING,
    LeadStatus.EXPLAINED,
    LeadStatus.CORROBORATED,
    LeadStatus.REJECTED,
    LeadStatus.ARCHIVED,
}

_REVIEW_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS lead_review_events (
    event_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES leads(lead_id),
    occurred_at TEXT NOT NULL,
    status TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    rationale TEXT NOT NULL,
    notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_lead_review_events_lead_time
ON lead_review_events(lead_id, occurred_at);

CREATE TRIGGER IF NOT EXISTS leads_no_update
BEFORE UPDATE ON leads BEGIN
    SELECT RAISE(ABORT, 'lead packets are immutable');
END;
CREATE TRIGGER IF NOT EXISTS leads_no_delete
BEFORE DELETE ON leads BEGIN
    SELECT RAISE(ABORT, 'lead packets are immutable');
END;
CREATE TRIGGER IF NOT EXISTS lead_observations_no_update
BEFORE UPDATE ON lead_observations BEGIN
    SELECT RAISE(ABORT, 'lead observation links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS lead_observations_no_delete
BEFORE DELETE ON lead_observations BEGIN
    SELECT RAISE(ABORT, 'lead observation links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS lead_evidence_no_update
BEFORE UPDATE ON lead_evidence BEGIN
    SELECT RAISE(ABORT, 'lead evidence links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS lead_evidence_no_delete
BEFORE DELETE ON lead_evidence BEGIN
    SELECT RAISE(ABORT, 'lead evidence links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS lead_review_events_no_update
BEFORE UPDATE ON lead_review_events BEGIN
    SELECT RAISE(ABORT, 'lead review events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS lead_review_events_no_delete
BEFORE DELETE ON lead_review_events BEGIN
    SELECT RAISE(ABORT, 'lead review events are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class LeadPackageResult:
    observation_id: str
    lead_id: str
    created: bool
    method: str = _METHOD

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LeadReviewEvent:
    event_id: str
    lead_id: str
    occurred_at: str
    status: str
    reviewer: str
    rationale: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class LeadLifecycle:
    """Package Gold observations into immutable leads and append human review events."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        self.candidates = CandidateObservationRunner(self.state_dir)
        with self.store.connection() as connection:
            connection.executescript(_REVIEW_SCHEMA)

    def _observation(self, observation_id: str) -> tuple[dict, tuple[EvidenceReference, ...]]:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM observations WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown observation: {observation_id}")
            refs = connection.execute(
                """
                SELECT evidence_id, artifact_id, locator, excerpt
                FROM observation_evidence
                WHERE observation_id = ?
                ORDER BY evidence_id
                """,
                (observation_id,),
            ).fetchall()
        return dict(row), tuple(
            EvidenceReference(
                evidence_id=str(ref["evidence_id"]),
                artifact_id=str(ref["artifact_id"]),
                locator=str(ref["locator"]),
                excerpt=ref["excerpt"],
            )
            for ref in refs
        )

    def package_observation(self, observation_id: str) -> LeadPackageResult:
        observation, refs = self._observation(observation_id)
        contexts = self.candidates.contexts_for_observation(observation_id)
        if observation["observation_type"] != "recurrence_structured_fact_variation":
            raise ValueError(
                "R0 lead packaging currently requires a recurrence_structured_fact_variation observation"
            )
        if len(contexts) != 1 or contexts[0]["context_type"] != "recurrence_cluster":
            raise ValueError("candidate observation must have exactly one recurrence detector context")
        details = contexts[0]["details"]
        questions = tuple(str(value) for value in details.get("questions_worth_asking") or ())
        benign = tuple(str(value) for value in details.get("possible_ordinary_explanations") or ())
        if not questions:
            raise ValueError("candidate detector context lacks questions worth asking")
        if not benign:
            raise ValueError("candidate detector context lacks possible ordinary explanations")

        lead_id = stable_id("lead", _METHOD, observation_id)
        lead = Lead(
            lead_id=lead_id,
            title="Recurring public-record item with structured fact variation",
            why_surfaced=str(observation["explanation"]),
            observation_ids=(observation_id,),
            evidence_refs=refs,
            questions_worth_asking=questions,
            possible_benign_explanations=benign,
            status=LeadStatus.CANDIDATE,
        )
        created = self.store.add_lead(lead)
        return LeadPackageResult(
            observation_id=observation_id,
            lead_id=lead_id,
            created=created,
        )

    def package_candidate_observations(self) -> tuple[LeadPackageResult, ...]:
        """Package every eligible recurrence candidate observation deterministically."""
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT observation_id
                FROM observations
                WHERE observation_type = 'recurrence_structured_fact_variation'
                ORDER BY observation_id
                """
            ).fetchall()
        return tuple(self.package_observation(str(row["observation_id"])) for row in rows)

    def review(
        self,
        lead_id: str,
        *,
        status: LeadStatus | str,
        reviewer: str,
        rationale: str,
        notes: tuple[str, ...] = (),
        occurred_at: datetime | None = None,
    ) -> LeadReviewEvent:
        if isinstance(status, str):
            status = LeadStatus(status)
        if status not in _REVIEWABLE_STATUSES:
            allowed = ", ".join(sorted(value.value for value in _REVIEWABLE_STATUSES))
            raise ValueError(f"review status must be one of: {allowed}")
        reviewer = reviewer.strip()
        rationale = rationale.strip()
        if not reviewer:
            raise ValueError("reviewer cannot be empty")
        if not rationale:
            raise ValueError("review rationale cannot be empty")
        with self.store.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM leads WHERE lead_id = ?", (lead_id,)
            ).fetchone() is None:
                raise ValueError(f"unknown lead: {lead_id}")

        moment = occurred_at or datetime.now(UTC)
        occurred = moment.isoformat()
        event_id = stable_id(
            "lead-review-event",
            lead_id,
            occurred,
            status.value,
            reviewer,
            rationale,
            *notes,
        )
        with self.store.connection() as connection:
            connection.execute(
                """
                INSERT INTO lead_review_events(
                    event_id, lead_id, occurred_at, status, reviewer, rationale, notes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    lead_id,
                    occurred,
                    status.value,
                    reviewer,
                    rationale,
                    json.dumps(list(notes)),
                ),
            )
        return LeadReviewEvent(
            event_id=event_id,
            lead_id=lead_id,
            occurred_at=occurred,
            status=status.value,
            reviewer=reviewer,
            rationale=rationale,
            notes=notes,
        )

    def review_history(self, lead_id: str) -> tuple[LeadReviewEvent, ...]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT event_id, lead_id, occurred_at, status, reviewer, rationale, notes_json
                FROM lead_review_events
                WHERE lead_id = ?
                ORDER BY occurred_at, rowid
                """,
                (lead_id,),
            ).fetchall()
        return tuple(
            LeadReviewEvent(
                event_id=str(row["event_id"]),
                lead_id=str(row["lead_id"]),
                occurred_at=str(row["occurred_at"]),
                status=str(row["status"]),
                reviewer=str(row["reviewer"]),
                rationale=str(row["rationale"]),
                notes=tuple(json.loads(row["notes_json"])),
            )
            for row in rows
        )

    def get(self, lead_id: str) -> dict | None:
        with self.store.connection() as connection:
            lead = connection.execute(
                "SELECT * FROM leads WHERE lead_id = ?", (lead_id,)
            ).fetchone()
            if lead is None:
                return None
            observations = connection.execute(
                """
                SELECT observation_id FROM lead_observations
                WHERE lead_id = ? ORDER BY observation_id
                """,
                (lead_id,),
            ).fetchall()
            evidence = connection.execute(
                """
                SELECT evidence_id, artifact_id, locator, excerpt
                FROM lead_evidence WHERE lead_id = ? ORDER BY evidence_id
                """,
                (lead_id,),
            ).fetchall()
        history = self.review_history(lead_id)
        current_status = history[-1].status if history else str(lead["status"])
        return {
            "lead": dict(lead),
            "current_status": current_status,
            "observation_ids": [str(row["observation_id"]) for row in observations],
            "evidence": [dict(row) for row in evidence],
            "review_history": [event.to_dict() for event in history],
        }
