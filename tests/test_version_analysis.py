from __future__ import annotations

import sqlite3

from proofline import Ingestor, ProoflineStore
from proofline.version_analysis import VersionObservationRunner


def _seed_version_family(tmp_path):
    state = tmp_path / "state"
    ingestor = Ingestor(state)
    current_uri = "https://city.example.gov/AgendaCenter/ViewFile/Agenda/_05262026-1147"
    archived_uri = "https://city.example.gov/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1033"
    listing_uri = "https://city.example.gov/AgendaCenter/PreviousVersions/_05262026-1147"

    current = tmp_path / "current.txt"
    archived = tmp_path / "archived.txt"
    listing = tmp_path / "versions.html"
    archived.write_text(
        "Change Order No. 1 adds $325.00 per month; first-year amount $278,593.00.",
        encoding="utf-8",
    )
    current.write_text(
        "Change Order No. 1 adds $325.00 per month; first-year amount $282,168.00.",
        encoding="utf-8",
    )
    listing.write_text(
        """
        <h2>Board of Control</h2>
        <h3>May 26, 2026 — Amended</h3>
        <a href="/AgendaCenter/ViewFile/Agenda/_05262026-1147">PDF</a>
        <h3>May 26, 2026 — Posted</h3>
        <a href="/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1033">PDF</a>
        """,
        encoding="utf-8",
    )

    ingestor.ingest(archived, source_uri=archived_uri)
    ingestor.ingest(current, source_uri=current_uri)
    ingestor.ingest(listing, source_uri=listing_uri)
    return state


def test_runner_derives_relation_then_persists_observation_and_provenance(tmp_path) -> None:
    state = _seed_version_family(tmp_path)
    runner = VersionObservationRunner(state)

    first = runner.run()
    assert first.relation_count == 1
    assert first.compared == 1
    assert first.observations_created == 1
    assert first.failed == 0
    item = first.items[0]
    assert item.status == "observed"
    assert item.observation_id is not None

    store = ProoflineStore(state / "proofline.db")
    trace = store.trace_observation(item.observation_id)
    assert trace is not None
    assert len(trace["evidence"]) == 2

    with store.connection() as connection:
        link = connection.execute(
            "SELECT observation_id, relation_id FROM observation_source_relations"
        ).fetchone()
        relation = connection.execute(
            "SELECT * FROM source_relations WHERE relation_id = ?",
            (link["relation_id"],),
        ).fetchone()
    assert link["observation_id"] == item.observation_id
    assert relation["relation_type"] == "historical_version_of"

    second = runner.run()
    assert second.observations_created == 0
    assert second.items[0].status == "already_observed"


def test_observation_relation_links_are_append_only(tmp_path) -> None:
    state = _seed_version_family(tmp_path)
    runner = VersionObservationRunner(state)
    result = runner.run()
    observation_id = result.items[0].observation_id
    assert observation_id

    with runner.store.connection() as connection:
        row = connection.execute(
            "SELECT relation_id FROM observation_source_relations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
        try:
            connection.execute(
                "UPDATE observation_source_relations SET relation_id = 'relation:other' "
                "WHERE observation_id = ?",
                (observation_id,),
            )
        except sqlite3.IntegrityError as exc:
            assert "append-only" in str(exc)
        else:
            raise AssertionError("observation relation link update should be rejected")
        assert row is not None
