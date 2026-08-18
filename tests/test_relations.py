from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from proofline import Ingestor, source_id_from_uri
from proofline.relations import RelationStore, derive_civicengage_version_relations
from proofline.watch_storage import WatcherStore


def test_previous_versions_page_creates_evidence_backed_relation(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)

    current_uri = "https://city.example.gov/AgendaCenter/ViewFile/Agenda/_05262026-1147"
    archived_uri = "https://city.example.gov/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1033"
    listing_uri = "https://city.example.gov/AgendaCenter/PreviousVersions/_05262026-1147"

    current = tmp_path / "current.txt"
    archived = tmp_path / "archived.txt"
    listing = tmp_path / "versions.html"
    current.write_text("current record", encoding="utf-8")
    archived.write_text("archived record", encoding="utf-8")
    listing.write_text(
        """
        <html><body>
        <h2>Board of Control</h2>
        <h3>May 26, 2026 — Amended</h3>
        <a href="/AgendaCenter/ViewFile/Agenda/_05262026-1147">PDF</a>
        <h3>May 26, 2026 — Posted</h3>
        <a href="/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1033">PDF</a>
        </body></html>
        """,
        encoding="utf-8",
    )

    ingestor.ingest(current, source_uri=current_uri)
    ingestor.ingest(archived, source_uri=archived_uri)
    listing_result = ingestor.ingest(listing, source_uri=listing_uri)

    created = derive_civicengage_version_relations(state)
    assert len(created) == 1
    relation = created[0]
    assert relation.source_uri == archived_uri
    assert relation.relation_type == "historical_version_of"
    assert relation.related_source_uri == current_uri
    assert relation.evidence_artifact_id == listing_result.artifact_id
    assert relation.details["format"] == "pdf"

    # Re-derivation is idempotent rather than manufacturing duplicate edges.
    assert derive_civicengage_version_relations(state) == ()
    assert len(RelationStore(state).list(relation_type="historical_version_of")) == 1


def test_relation_evidence_uses_latest_watcher_visit_after_a_b_a_reversion(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)
    listing_uri = "https://city.example.gov/AgendaCenter/PreviousVersions/_05262026-1147"
    current_uri = "https://city.example.gov/AgendaCenter/ViewFile/Agenda/_05262026-1147"
    archived_a_uri = "https://city.example.gov/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1033"
    archived_b_uri = "https://city.example.gov/AgendaCenter/ViewFile/ArchivedAgenda/_05262026-1034"

    current = tmp_path / "current.txt"
    archived_a = tmp_path / "archived_a.txt"
    archived_b = tmp_path / "archived_b.txt"
    listing_a = tmp_path / "listing_a.html"
    listing_b = tmp_path / "listing_b.html"

    current.write_text("current", encoding="utf-8")
    archived_a.write_text("archived A", encoding="utf-8")
    archived_b.write_text("archived B", encoding="utf-8")
    listing_a.write_text(
        f"""
        <h2>Board of Control</h2><h3>May 26, 2026</h3>
        <a href="{current_uri}">PDF</a>
        <h3>May 26, 2026 — original A</h3>
        <a href="{archived_a_uri}">PDF</a>
        """,
        encoding="utf-8",
    )
    listing_b.write_text(
        f"""
        <h2>Board of Control</h2><h3>May 26, 2026</h3>
        <a href="{current_uri}">PDF</a>
        <h3>May 26, 2026 — temporary B</h3>
        <a href="{archived_b_uri}">PDF</a>
        """,
        encoding="utf-8",
    )

    ingestor.ingest(current, source_uri=current_uri)
    ingestor.ingest(archived_a, source_uri=archived_a_uri)
    ingestor.ingest(archived_b, source_uri=archived_b_uri)
    a = ingestor.ingest(listing_a, source_uri=listing_uri)
    b = ingestor.ingest(listing_b, source_uri=listing_uri)

    watcher = WatcherStore(state / "proofline.db")
    source_id = source_id_from_uri(listing_uri)
    start = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    watcher.add_source_check(
        check_id="check:a1",
        run_id="run:1",
        source_id=source_id,
        checked_at=start,
        state="new",
        artifact_id=a.artifact_id,
        previous_artifact_id=None,
        http_status=200,
        content_type="text/html",
        etag=None,
        last_modified=None,
        error=None,
        attempts=1,
        manifest_name="fixture",
    )
    watcher.add_source_check(
        check_id="check:b",
        run_id="run:2",
        source_id=source_id,
        checked_at=start + timedelta(minutes=1),
        state="changed",
        artifact_id=b.artifact_id,
        previous_artifact_id=a.artifact_id,
        http_status=200,
        content_type="text/html",
        etag=None,
        last_modified=None,
        error=None,
        attempts=1,
        manifest_name="fixture",
    )
    watcher.add_source_check(
        check_id="check:a2",
        run_id="run:3",
        source_id=source_id,
        checked_at=start + timedelta(minutes=2),
        state="changed",
        artifact_id=a.artifact_id,
        previous_artifact_id=b.artifact_id,
        http_status=200,
        content_type="text/html",
        etag=None,
        last_modified=None,
        error=None,
        attempts=1,
        manifest_name="fixture",
    )

    relations = derive_civicengage_version_relations(state)
    assert len(relations) == 1
    assert relations[0].source_uri == archived_a_uri
    assert relations[0].evidence_artifact_id == a.artifact_id
    assert not RelationStore(state).list(relation_type="historical_version_of")[0].source_uri == archived_b_uri


def test_source_relations_are_append_only(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)
    current_uri = "https://records.example.gov/current"
    archived_uri = "https://records.example.gov/archived"
    evidence_uri = "https://records.example.gov/version-listing"

    current = tmp_path / "current.txt"
    archived = tmp_path / "archived.txt"
    evidence = tmp_path / "evidence.txt"
    current.write_text("current", encoding="utf-8")
    archived.write_text("archived", encoding="utf-8")
    evidence.write_text("publisher says these are versions", encoding="utf-8")
    ingestor.ingest(current, source_uri=current_uri)
    ingestor.ingest(archived, source_uri=archived_uri)
    evidence_result = ingestor.ingest(evidence, source_uri=evidence_uri)

    relations = RelationStore(state)
    relation = relations.add(
        source_uri=archived_uri,
        relation_type="historical_version_of",
        related_source_uri=current_uri,
        evidence_artifact_id=evidence_result.artifact_id,
        method="fixture",
        method_version="1",
    )
    assert relation is not None

    with relations.store.connection() as connection:
        try:
            connection.execute(
                "UPDATE source_relations SET relation_type = 'other' WHERE relation_id = ?",
                (relation.relation_id,),
            )
        except sqlite3.IntegrityError as exc:
            assert "append-only" in str(exc)
        else:
            raise AssertionError("source relation update should be rejected")
