from __future__ import annotations

import pymupdf

from proofline import Ingestor
from proofline.version_analysis import VersionObservationRunner


def test_publisher_backed_pair_with_empty_silver_is_skipped_not_failed(tmp_path) -> None:
    state = tmp_path / "state"
    ingestor = Ingestor(state)

    current_uri = "https://city.example.gov/AgendaCenter/ViewFile/Agenda/_01052026-1040"
    archived_uri = "https://city.example.gov/AgendaCenter/ViewFile/ArchivedAgenda/_01052026-1026"
    listing_uri = "https://city.example.gov/AgendaCenter/PreviousVersions/_01052026-1040"

    current_path = tmp_path / "current.txt"
    current_path.write_text("Substantive current meeting record.", encoding="utf-8")

    archived_path = tmp_path / "archived.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(archived_path)
    document.close()

    listing_path = tmp_path / "versions.html"
    listing_path.write_text(
        """
        <h2>City Council</h2>
        <h3>Jan 5, 2026 — Current</h3>
        <a href="/AgendaCenter/ViewFile/Agenda/_01052026-1040">PDF</a>
        <h3>Jan 5, 2026 — Archived</h3>
        <a href="/AgendaCenter/ViewFile/ArchivedAgenda/_01052026-1026">PDF</a>
        """,
        encoding="utf-8",
    )

    ingestor.ingest(current_path, source_uri=current_uri)
    ingestor.ingest(archived_path, source_uri=archived_uri)
    ingestor.ingest(listing_path, source_uri=listing_uri)

    result = VersionObservationRunner(state).run()

    assert result.relation_count == 1
    assert result.compared == 0
    assert result.observations_created == 0
    assert result.unchanged == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert result.items[0].status == "insufficient_evidence"
    assert result.items[0].error is None
