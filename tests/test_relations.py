from __future__ import annotations

import sqlite3

from proofline import Ingestor
from proofline.relations import RelationStore, derive_civicengage_version_relations


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
