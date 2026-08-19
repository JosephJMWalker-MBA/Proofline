"""Run deterministic version observations only across evidence-backed source relations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .detectors import build_version_change_observation
from .relations import RelationStore, SourceRelation, derive_civicengage_version_relations
from .storage import ProoflineStore
from .watch_storage import WatcherStore

_LINK_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS observation_source_relations (
    observation_id TEXT NOT NULL REFERENCES observations(observation_id),
    relation_id TEXT NOT NULL REFERENCES source_relations(relation_id),
    PRIMARY KEY(observation_id, relation_id)
);
CREATE TRIGGER IF NOT EXISTS observation_source_relations_no_update
BEFORE UPDATE ON observation_source_relations BEGIN
    SELECT RAISE(ABORT, 'observation source relations are append-only');
END;
CREATE TRIGGER IF NOT EXISTS observation_source_relations_no_delete
BEFORE DELETE ON observation_source_relations BEGIN
    SELECT RAISE(ABORT, 'observation source relations are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class VersionObservationItem:
    relation_id: str
    before_artifact_id: str | None
    after_artifact_id: str | None
    observation_id: str | None
    observation_created: bool
    changed: bool | None
    status: str
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VersionObservationRun:
    relation_count: int
    compared: int
    observations_created: int
    unchanged: int
    skipped: int
    failed: int
    items: tuple[VersionObservationItem, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data


class VersionObservationRunner:
    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.relations = RelationStore(self.state_dir)
        self.store: ProoflineStore = self.relations.store
        self.watcher = WatcherStore(self.state_dir / "proofline.db")
        with self.store.connection() as connection:
            connection.executescript(_LINK_SCHEMA)

    def _latest_artifact(self, source_id: str) -> str | None:
        artifact_id = self.watcher.latest_successful_artifact(source_id)
        if artifact_id is None:
            artifact_id = self.store.latest_artifact_for_source(source_id)
        return artifact_id

    def _has_substantive_silver(self, artifact_id: str) -> bool:
        """Return whether preferred Silver contains any non-whitespace extracted text.

        An evidence-unit row proves that the source was structurally ingested; it does not
        prove that extraction yielded content suitable for a Gold comparison. Blank wrapper
        PDFs, empty pages, and similarly contentless artifacts must remain insufficient
        evidence rather than being interpreted as a substantive deletion/addition.
        """
        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM evidence_units eu
                JOIN evidence_extractions best
                  ON best.extraction_id = (
                    SELECT ee.extraction_id
                    FROM evidence_extractions ee
                    WHERE ee.evidence_id = eu.evidence_id
                    ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                             ee.occurred_at DESC,
                             ee.rowid DESC
                    LIMIT 1
                  )
                WHERE eu.artifact_id = ?
                  AND TRIM(COALESCE(best.extracted_text, '')) <> ''
                LIMIT 1
                """,
                (artifact_id,),
            ).fetchone()
        return row is not None

    def _attach(self, observation_id: str, relation_id: str) -> None:
        with self.store.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO observation_source_relations(observation_id, relation_id)
                VALUES (?, ?)
                """,
                (observation_id, relation_id),
            )

    def relations_for_observation(self, observation_id: str) -> list[dict]:
        """Return the publisher-backed source relations that authorized an observation."""
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    sr.relation_id,
                    sr.relation_type,
                    sr.evidence_artifact_id,
                    sr.method,
                    sr.method_version,
                    sr.details_json,
                    source.source_id,
                    source.source_uri,
                    related.source_id AS related_source_id,
                    related.source_uri AS related_source_uri
                FROM observation_source_relations osr
                JOIN source_relations sr ON sr.relation_id = osr.relation_id
                JOIN sources source ON source.source_id = sr.source_id
                JOIN sources related ON related.source_id = sr.related_source_id
                WHERE osr.observation_id = ?
                ORDER BY sr.relation_id
                """,
                (observation_id,),
            ).fetchall()
        return [
            {
                "relation_id": row["relation_id"],
                "relation_type": row["relation_type"],
                "source_id": row["source_id"],
                "source_uri": row["source_uri"],
                "related_source_id": row["related_source_id"],
                "related_source_uri": row["related_source_uri"],
                "evidence_artifact_id": row["evidence_artifact_id"],
                "method": row["method"],
                "method_version": row["method_version"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def _run_relation(self, relation: SourceRelation) -> VersionObservationItem:
        before_artifact_id = self._latest_artifact(relation.source_id)
        after_artifact_id = self._latest_artifact(relation.related_source_id)
        if before_artifact_id is None or after_artifact_id is None:
            return VersionObservationItem(
                relation_id=relation.relation_id,
                before_artifact_id=before_artifact_id,
                after_artifact_id=after_artifact_id,
                observation_id=None,
                observation_created=False,
                changed=None,
                status="missing_artifact",
            )
        if before_artifact_id == after_artifact_id:
            return VersionObservationItem(
                relation_id=relation.relation_id,
                before_artifact_id=before_artifact_id,
                after_artifact_id=after_artifact_id,
                observation_id=None,
                observation_created=False,
                changed=False,
                status="same_artifact",
            )
        if not self._has_substantive_silver(before_artifact_id) or not self._has_substantive_silver(
            after_artifact_id
        ):
            return VersionObservationItem(
                relation_id=relation.relation_id,
                before_artifact_id=before_artifact_id,
                after_artifact_id=after_artifact_id,
                observation_id=None,
                observation_created=False,
                changed=None,
                status="insufficient_evidence",
            )

        try:
            diff, observation = build_version_change_observation(
                self.store,
                before_artifact_id,
                after_artifact_id,
            )
        except Exception as exc:
            return VersionObservationItem(
                relation_id=relation.relation_id,
                before_artifact_id=before_artifact_id,
                after_artifact_id=after_artifact_id,
                observation_id=None,
                observation_created=False,
                changed=None,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )

        if observation is None:
            return VersionObservationItem(
                relation_id=relation.relation_id,
                before_artifact_id=before_artifact_id,
                after_artifact_id=after_artifact_id,
                observation_id=None,
                observation_created=False,
                changed=diff.changed,
                status="unchanged",
            )

        created = self.store.add_observation(observation)
        self._attach(observation.observation_id, relation.relation_id)
        return VersionObservationItem(
            relation_id=relation.relation_id,
            before_artifact_id=before_artifact_id,
            after_artifact_id=after_artifact_id,
            observation_id=observation.observation_id,
            observation_created=created,
            changed=True,
            status="observed" if created else "already_observed",
        )

    def run(self, *, derive_relations: bool = True) -> VersionObservationRun:
        if derive_relations:
            derive_civicengage_version_relations(self.state_dir)
        relations = self.relations.list(relation_type="historical_version_of")
        items = tuple(self._run_relation(relation) for relation in relations)
        compared = sum(item.status in {"observed", "already_observed", "unchanged"} for item in items)
        observations_created = sum(item.observation_created for item in items)
        unchanged = sum(item.status == "unchanged" for item in items)
        failed = sum(item.status == "failed" for item in items)
        skipped = len(items) - compared - failed
        return VersionObservationRun(
            relation_count=len(relations),
            compared=compared,
            observations_created=observations_created,
            unchanged=unchanged,
            skipped=skipped,
            failed=failed,
            items=items,
        )
