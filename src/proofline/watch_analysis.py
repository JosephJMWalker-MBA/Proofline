"""Create deterministic source-change observations from append-only watcher chronology.

A stable source URI is itself the provenance relationship between successive watcher visits.
For each `changed` visit, Proofline compares exactly the previous and current artifact recorded
on that visit. Seen-before bytes are not collapsed: an A -> B -> A reversion is two distinct
chronological changes even though the final artifact was observed earlier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .detectors import build_version_change_observation
from .silver import artifact_has_substantive_preferred_text
from .storage import ProoflineStore
from .watch_storage import WatcherStore

_LINK_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS observation_source_checks (
    observation_id TEXT NOT NULL REFERENCES observations(observation_id),
    check_id TEXT NOT NULL REFERENCES source_checks(check_id),
    PRIMARY KEY(observation_id, check_id)
);
CREATE TRIGGER IF NOT EXISTS observation_source_checks_no_update
BEFORE UPDATE ON observation_source_checks BEGIN
    SELECT RAISE(ABORT, 'observation source checks are append-only');
END;
CREATE TRIGGER IF NOT EXISTS observation_source_checks_no_delete
BEFORE DELETE ON observation_source_checks BEGIN
    SELECT RAISE(ABORT, 'observation source checks are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class WatchChangeObservationItem:
    check_id: str
    source_id: str
    previous_artifact_id: str | None
    artifact_id: str | None
    observation_id: str | None
    observation_created: bool
    status: str
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WatchChangeObservationRun:
    changed_checks: int
    compared: int
    observations_created: int
    already_observed: int
    no_substantive_change: int
    skipped: int
    failed: int
    items: tuple[WatchChangeObservationItem, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data


class WatchChangeObservationRunner:
    """Promote substantive watcher `changed` transitions into traceable observations."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.watcher = WatcherStore(self.state_dir / "proofline.db")
        self.store: ProoflineStore = self.watcher.base
        with self.store.connection() as connection:
            connection.executescript(_LINK_SCHEMA)

    def _changed_checks(self) -> list[dict]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT sc.*, s.source_uri, s.source_name
                FROM source_checks sc
                JOIN sources s ON s.source_id = sc.source_id
                WHERE sc.state = 'changed'
                ORDER BY sc.checked_at, sc.rowid
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _attach(self, observation_id: str, check_id: str) -> None:
        with self.store.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO observation_source_checks(observation_id, check_id)
                VALUES (?, ?)
                """,
                (observation_id, check_id),
            )

    def checks_for_observation(self, observation_id: str) -> list[dict]:
        """Return exact watcher visits that authorized an observation."""
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    sc.check_id,
                    sc.run_id,
                    sc.checked_at,
                    sc.state,
                    sc.artifact_id,
                    sc.previous_artifact_id,
                    sc.http_status,
                    sc.content_type,
                    sc.etag,
                    sc.last_modified,
                    sc.error,
                    sc.attempts,
                    sc.manifest_name,
                    s.source_id,
                    s.source_uri,
                    s.source_name
                FROM observation_source_checks osc
                JOIN source_checks sc ON sc.check_id = osc.check_id
                JOIN sources s ON s.source_id = sc.source_id
                WHERE osc.observation_id = ?
                ORDER BY sc.checked_at, sc.rowid
                """,
                (observation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _run_check(self, check: dict) -> WatchChangeObservationItem:
        check_id = str(check["check_id"])
        source_id = str(check["source_id"])
        before = check.get("previous_artifact_id")
        after = check.get("artifact_id")
        if before is None or after is None:
            return WatchChangeObservationItem(
                check_id=check_id,
                source_id=source_id,
                previous_artifact_id=before,
                artifact_id=after,
                observation_id=None,
                observation_created=False,
                status="missing_artifact",
            )
        before = str(before)
        after = str(after)
        if before == after:
            return WatchChangeObservationItem(
                check_id=check_id,
                source_id=source_id,
                previous_artifact_id=before,
                artifact_id=after,
                observation_id=None,
                observation_created=False,
                status="invalid_same_artifact",
            )
        if not artifact_has_substantive_preferred_text(
            self.store, before
        ) or not artifact_has_substantive_preferred_text(self.store, after):
            return WatchChangeObservationItem(
                check_id=check_id,
                source_id=source_id,
                previous_artifact_id=before,
                artifact_id=after,
                observation_id=None,
                observation_created=False,
                status="insufficient_evidence",
            )
        try:
            _, observation = build_version_change_observation(self.store, before, after)
        except Exception as exc:
            return WatchChangeObservationItem(
                check_id=check_id,
                source_id=source_id,
                previous_artifact_id=before,
                artifact_id=after,
                observation_id=None,
                observation_created=False,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        if observation is None:
            return WatchChangeObservationItem(
                check_id=check_id,
                source_id=source_id,
                previous_artifact_id=before,
                artifact_id=after,
                observation_id=None,
                observation_created=False,
                status="no_substantive_change",
            )
        created = self.store.add_observation(observation)
        self._attach(observation.observation_id, check_id)
        return WatchChangeObservationItem(
            check_id=check_id,
            source_id=source_id,
            previous_artifact_id=before,
            artifact_id=after,
            observation_id=observation.observation_id,
            observation_created=created,
            status="observed" if created else "already_observed",
        )

    def run(self) -> WatchChangeObservationRun:
        checks = self._changed_checks()
        items = tuple(self._run_check(check) for check in checks)
        compared_statuses = {"observed", "already_observed", "no_substantive_change"}
        compared = sum(item.status in compared_statuses for item in items)
        created = sum(item.observation_created for item in items)
        already = sum(item.status == "already_observed" for item in items)
        no_substantive = sum(item.status == "no_substantive_change" for item in items)
        failed = sum(item.status == "failed" for item in items)
        skipped = len(items) - compared - failed
        return WatchChangeObservationRun(
            changed_checks=len(checks),
            compared=compared,
            observations_created=created,
            already_observed=already,
            no_substantive_change=no_substantive,
            skipped=skipped,
            failed=failed,
            items=items,
        )
