from __future__ import annotations

from datetime import UTC, datetime, timedelta

from proofline import Ingestor, source_id_from_uri
from proofline.watch_analysis import WatchChangeObservationRunner
from proofline.watch_storage import WatcherStore


def _add_check(
    watcher: WatcherStore,
    *,
    check_id: str,
    source_id: str,
    checked_at: datetime,
    artifact_id: str,
    previous_artifact_id: str,
) -> None:
    watcher.add_source_check(
        check_id=check_id,
        run_id=f"run-{check_id}",
        source_id=source_id,
        checked_at=checked_at,
        state="changed",
        artifact_id=artifact_id,
        previous_artifact_id=previous_artifact_id,
        http_status=200,
        content_type="text/plain",
        etag=None,
        last_modified=None,
        error=None,
        attempts=1,
        manifest_name="fixture",
    )


def test_watcher_change_runner_preserves_a_b_a_chronology(tmp_path) -> None:
    state = tmp_path / "state"
    uri = "https://example.gov/record"
    source_id = source_id_from_uri(uri)

    first_path = tmp_path / "a.txt"
    second_path = tmp_path / "b.txt"
    first_path.write_text(
        "Contract amount $100.00. Deadline January 1, 2026.\n",
        encoding="utf-8",
    )
    second_path.write_text(
        "Contract amount $125.00. Deadline February 1, 2026.\n",
        encoding="utf-8",
    )
    ingestor = Ingestor(state)
    first = ingestor.ingest(first_path, source_uri=uri, source_name="Stable public record")
    second = ingestor.ingest(second_path, source_uri=uri, source_name="Stable public record")

    watcher = WatcherStore(state / "proofline.db")
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    _add_check(
        watcher,
        check_id="check-a-to-b",
        source_id=source_id,
        checked_at=start,
        artifact_id=second.artifact_id,
        previous_artifact_id=first.artifact_id,
    )
    _add_check(
        watcher,
        check_id="check-b-to-a",
        source_id=source_id,
        checked_at=start + timedelta(hours=1),
        artifact_id=first.artifact_id,
        previous_artifact_id=second.artifact_id,
    )

    runner = WatchChangeObservationRunner(state)
    result = runner.run()
    assert result.changed_checks == 2
    assert result.compared == 2
    assert result.observations_created == 2
    assert result.already_observed == 0
    assert result.failed == 0
    assert [item.status for item in result.items] == ["observed", "observed"]

    first_observation = result.items[0].observation_id
    second_observation = result.items[1].observation_id
    assert first_observation
    assert second_observation
    assert first_observation != second_observation

    first_checks = runner.checks_for_observation(first_observation)
    second_checks = runner.checks_for_observation(second_observation)
    assert [row["check_id"] for row in first_checks] == ["check-a-to-b"]
    assert [row["check_id"] for row in second_checks] == ["check-b-to-a"]
    assert first_checks[0]["previous_artifact_id"] == first.artifact_id
    assert first_checks[0]["artifact_id"] == second.artifact_id
    assert second_checks[0]["previous_artifact_id"] == second.artifact_id
    assert second_checks[0]["artifact_id"] == first.artifact_id

    rerun = runner.run()
    assert rerun.observations_created == 0
    assert rerun.already_observed == 2
    assert [item.observation_id for item in rerun.items] == [first_observation, second_observation]
    assert len(runner.checks_for_observation(first_observation)) == 1
    assert len(runner.checks_for_observation(second_observation)) == 1


def test_watcher_changed_bytes_without_substantive_silver_are_skipped(tmp_path) -> None:
    state = tmp_path / "state"
    uri = "https://example.gov/blank"
    source_id = source_id_from_uri(uri)
    first_path = tmp_path / "blank-a.txt"
    second_path = tmp_path / "blank-b.txt"
    first_path.write_text("   \n", encoding="utf-8")
    second_path.write_text("\t\n", encoding="utf-8")
    ingestor = Ingestor(state)
    first = ingestor.ingest(first_path, source_uri=uri, source_name="Blank record")
    second = ingestor.ingest(second_path, source_uri=uri, source_name="Blank record")

    watcher = WatcherStore(state / "proofline.db")
    _add_check(
        watcher,
        check_id="check-blank-change",
        source_id=source_id,
        checked_at=datetime(2026, 1, 1, tzinfo=UTC),
        artifact_id=second.artifact_id,
        previous_artifact_id=first.artifact_id,
    )

    result = WatchChangeObservationRunner(state).run()
    assert result.changed_checks == 1
    assert result.observations_created == 0
    assert result.skipped == 1
    assert result.items[0].status == "insufficient_evidence"
