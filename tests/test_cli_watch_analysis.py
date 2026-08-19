from __future__ import annotations

import json
from datetime import UTC, datetime

from proofline import Ingestor, source_id_from_uri
from proofline.cli import main
from proofline.watch_storage import WatcherStore


def test_analyze_watch_changes_cli_and_trace_source_check(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    uri = "https://example.gov/stable-record"
    source_id = source_id_from_uri(uri)
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("Amount $100.00. Deadline January 1, 2026.\n", encoding="utf-8")
    second_path.write_text("Amount $125.00. Deadline February 1, 2026.\n", encoding="utf-8")
    ingestor = Ingestor(state)
    first = ingestor.ingest(first_path, source_uri=uri, source_name="Stable record")
    second = ingestor.ingest(second_path, source_uri=uri, source_name="Stable record")

    WatcherStore(state / "proofline.db").add_source_check(
        check_id="check-change",
        run_id="run-change",
        source_id=source_id,
        checked_at=datetime(2026, 1, 2, tzinfo=UTC),
        state="changed",
        artifact_id=second.artifact_id,
        previous_artifact_id=first.artifact_id,
        http_status=200,
        content_type="text/plain",
        etag=None,
        last_modified=None,
        error=None,
        attempts=1,
        manifest_name="fixture",
    )

    code = main(["--state-dir", str(state), "analyze-watch-changes"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["changed_checks"] == 1
    assert payload["observations_created"] == 1
    assert payload["failed"] == 0
    item = payload["items"][0]
    assert item["status"] == "observed"
    observation_id = item["observation_id"]

    code = main(["--state-dir", str(state), "trace", observation_id])
    assert code == 0
    trace = json.loads(capsys.readouterr().out)
    assert trace["source_relations"] == []
    assert trace["detector_contexts"] == []
    assert len(trace["source_checks"]) == 1
    check = trace["source_checks"][0]
    assert check["check_id"] == "check-change"
    assert check["source_id"] == source_id
    assert check["previous_artifact_id"] == first.artifact_id
    assert check["artifact_id"] == second.artifact_id

    code = main(["--state-dir", str(state), "analyze-watch-changes"])
    assert code == 0
    rerun = json.loads(capsys.readouterr().out)
    assert rerun["observations_created"] == 0
    assert rerun["already_observed"] == 1
    assert rerun["items"][0]["observation_id"] == observation_id
