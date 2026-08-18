from __future__ import annotations

import pymupdf

from proofline import Ingestor
from proofline.indirection import discover_pointer_pdf_resources
from proofline.watcher import ManifestResource, SourceManifest


def _make_pointer_pdf(path, target: str, *, visible_text: str | None = None) -> None:
    document = pymupdf.open()
    page = document.new_page()
    if visible_text:
        page.insert_text((72, 72), visible_text)
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(47.5, 81.25, 47.5, 81.25),
            "uri": target,
        }
    )
    document.save(path)
    document.close()


def _discover(tmp_path, target: str, *, visible_text: str | None = None):
    state = tmp_path / "state"
    source_uri = "https://city.example.gov/AgendaCenter/ViewFile/Agenda/_07132026-1158"
    pdf = tmp_path / "wrapper.pdf"
    _make_pointer_pdf(pdf, target, visible_text=visible_text)
    ingested = Ingestor(state).ingest(
        pdf,
        source_uri=source_uri,
        source_name="City Council — Jul 13, 2026 — PDF",
    )
    manifest = SourceManifest(
        name="fixture",
        resources=(
            ManifestResource(
                source_uri=source_uri,
                source_name="City Council — Jul 13, 2026 — PDF",
                expected_media_type="application/pdf",
            ),
        ),
    )
    watch_result = {
        "results": [
            {
                "source_uri": source_uri,
                "artifact_id": ingested.artifact_id,
                "state": "new",
            }
        ]
    }
    return discover_pointer_pdf_resources(state, manifest, watch_result)


def test_empty_same_site_uuid_pointer_becomes_separate_source(tmp_path) -> None:
    target = "https://www.city.example.gov/b4feedda-7fbb-4f5e-9820-0ede5257feff"
    resources = _discover(tmp_path, target)

    assert len(resources) == 1
    assert resources[0].source_uri == target
    assert resources[0].source_name.endswith("LINKED RECORD")
    assert resources[0].native_identifier == (
        "linked-record-b4feedda-7fbb-4f5e-9820-0ede5257feff"
    )
    assert resources[0].expected_media_type is None


def test_pointer_resolution_rejects_external_hosts_and_non_uuid_paths(tmp_path) -> None:
    assert _discover(
        tmp_path / "external",
        "https://other.example.gov/b4feedda-7fbb-4f5e-9820-0ede5257feff",
    ) == ()
    assert _discover(
        tmp_path / "ordinary",
        "https://city.example.gov/documents/minutes.pdf",
    ) == ()


def test_pointer_resolution_rejects_pdf_with_visible_content(tmp_path) -> None:
    resources = _discover(
        tmp_path,
        "https://city.example.gov/b4feedda-7fbb-4f5e-9820-0ede5257feff",
        visible_text="This is already a substantive public record.",
    )
    assert resources == ()
