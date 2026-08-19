from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import proofline.cli as cli
from proofline import SourceManifest
from tests.test_version_analysis import _seed_version_family


def test_analyze_versions_command_emits_runner_result_and_trace_relation(tmp_path, capsys) -> None:
    state = _seed_version_family(tmp_path)

    exit_code = cli.main(["--state-dir", str(state), "analyze-versions"])
    assert exit_code == 0
    analysis = json.loads(capsys.readouterr().out)
    assert analysis["relation_count"] == 1
    assert analysis["compared"] == 1
    assert analysis["observations_created"] == 1
    assert analysis["failed"] == 0
    observation_id = analysis["items"][0]["observation_id"]
    assert observation_id

    trace_exit = cli.main(["--state-dir", str(state), "trace", observation_id])
    assert trace_exit == 0
    trace = json.loads(capsys.readouterr().out)
    assert len(trace["source_relations"]) == 1
    relation = trace["source_relations"][0]
    assert relation["relation_type"] == "historical_version_of"
    assert relation["evidence_artifact_id"]


def test_sync_always_runs_and_emits_version_analysis(tmp_path, monkeypatch, capsys) -> None:
    state = tmp_path / "state"
    manifest = SourceManifest(name="fixture", resources=())
    plan = SimpleNamespace(name="fixture-plan")
    discovered = SimpleNamespace(
        manifest=manifest,
        to_dict=lambda: {"plan": "fixture-plan", "manifest": {"resources": []}},
    )
    manifest_path = state / "manifests" / "fixture-plan.json"
    calls: list[str] = []

    monkeypatch.setattr(
        cli,
        "_discover",
        lambda state_dir, plan_path, output: (plan, discovered, manifest_path),
    )

    class FakeWatcher:
        def __init__(self, state_dir):
            assert state_dir == state

        def run(self, received_manifest):
            assert received_manifest is manifest
            calls.append("watch")
            return {"counts": {"unavailable": 0}, "results": []}

    class FakeVersionRun:
        failed = 0

        def to_dict(self):
            return {
                "relation_count": 2,
                "compared": 1,
                "observations_created": 1,
                "unchanged": 0,
                "skipped": 1,
                "failed": 0,
                "items": [],
            }

    class FakeVersionRunner:
        def __init__(self, state_dir):
            assert state_dir == state

        def run(self):
            calls.append("version_analysis")
            return FakeVersionRun()

    class FakeLexical:
        def __init__(self, state_dir):
            assert state_dir == state

        def rebuild(self):
            calls.append("lexical")
            return SimpleNamespace(to_dict=lambda: {"indexed_units": 0})

    class FakeStructured:
        def __init__(self, state_dir):
            assert state_dir == state

        def rebuild(self):
            calls.append("structured")
            return SimpleNamespace(to_dict=lambda: {"fact_count": 0})

    monkeypatch.setattr(cli, "CorpusWatcher", FakeWatcher)
    monkeypatch.setattr(cli, "VersionObservationRunner", FakeVersionRunner)
    monkeypatch.setattr(cli, "SearchIndex", FakeLexical)
    monkeypatch.setattr(cli, "StructuredIndex", FakeStructured)

    exit_code = cli.main(["--state-dir", str(state), "sync", "plan.json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version_analysis"]["relation_count"] == 2
    assert payload["version_analysis"]["failed"] == 0
    assert calls == ["watch", "version_analysis", "lexical", "structured"]


def test_sync_returns_nonzero_when_version_analysis_reports_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    state = tmp_path / "state"
    manifest = SourceManifest(name="fixture", resources=())
    plan = SimpleNamespace(name="fixture-plan")
    discovered = SimpleNamespace(
        manifest=manifest,
        to_dict=lambda: {"plan": "fixture-plan", "manifest": {"resources": []}},
    )

    monkeypatch.setattr(
        cli,
        "_discover",
        lambda state_dir, plan_path, output: (plan, discovered, Path("fixture.json")),
    )
    monkeypatch.setattr(
        cli,
        "CorpusWatcher",
        lambda state_dir: SimpleNamespace(run=lambda received: {"counts": {}, "results": []}),
    )

    failed_run = SimpleNamespace(
        failed=1,
        to_dict=lambda: {
            "relation_count": 1,
            "compared": 0,
            "observations_created": 0,
            "unchanged": 0,
            "skipped": 0,
            "failed": 1,
            "items": [{"status": "failed", "error": "fixture failure"}],
        },
    )
    monkeypatch.setattr(
        cli,
        "VersionObservationRunner",
        lambda state_dir: SimpleNamespace(run=lambda: failed_run),
    )
    monkeypatch.setattr(
        cli,
        "SearchIndex",
        lambda state_dir: SimpleNamespace(
            rebuild=lambda: SimpleNamespace(to_dict=lambda: {"indexed_units": 0})
        ),
    )
    monkeypatch.setattr(
        cli,
        "StructuredIndex",
        lambda state_dir: SimpleNamespace(
            rebuild=lambda: SimpleNamespace(to_dict=lambda: {"fact_count": 0})
        ),
    )

    exit_code = cli.main(["--state-dir", str(state), "sync", "plan.json"])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["version_analysis"]["failed"] == 1
