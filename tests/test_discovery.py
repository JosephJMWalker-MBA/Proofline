from __future__ import annotations

from proofline.discovery import DiscoverySpec, discover_civicengage_resources
from proofline.extractors import extract_html


_FIXTURE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Agenda Center</title>
    <style>.hidden { color: red; }</style>
    <script>window.secret = '$999999';</script>
  </head>
  <body>
    <h2>Board of Control</h2>
    <h3>May 26, 2026 — Amended May 27, 2026 10:40 AM</h3>
    <a href="/AgendaCenter/ViewFile/Agenda/_05262026-1147?html=true">HTML</a>
    <a href="/AgendaCenter/ViewFile/Agenda/_05262026-1147">PDF</a>
    <a href="/AgendaCenter/ViewFile/Agenda/_05262026-1147?packet=true">Packet</a>
    <a href="/AgendaCenter/PreviousVersions/_05262026-1147">Previous Versions</a>

    <h3>May 21, 2025 — Posted May 20, 2025</h3>
    <a href="/AgendaCenter/ViewFile/Agenda/_05212025-900?html=true">HTML</a>

    <h2>City Council</h2>
    <h3>Jun 1, 2026 — Posted Jun 2, 2026</h3>
    <a href="/AgendaCenter/ViewFile/Agenda/_06012026-1154?html=true">HTML</a>
    <a href="/AgendaCenter/ViewFile/Agenda/_06012026-1154">PDF</a>

    <h2>Records Commission</h2>
    <h3>Jun 1, 2026</h3>
    <a href="/AgendaCenter/ViewFile/Agenda/_06012026-9999?html=true">HTML</a>

    <main>
      <p>Enter into a contract for $250,000.</p>
      <p>Vendor: Northstar Civic Systems</p>
    </main>
  </body>
</html>
"""


def test_civicengage_discovery_is_scoped_and_deterministic() -> None:
    spec = DiscoverySpec(
        kind="civicengage_agenda_center",
        source_uri="https://city.example.gov/AgendaCenter",
        categories=("Board of Control", "City Council"),
        years=(2026,),
        formats=("html", "pdf"),
        include_previous_versions=True,
    )

    resources = discover_civicengage_resources(_FIXTURE_HTML, spec)
    uris = [item.source_uri for item in resources]

    assert uris == sorted(uris)
    assert len(resources) == 5
    assert all("2025" not in uri for uri in uris)
    assert all("9999" not in uri for uri in uris)
    assert any("PreviousVersions" in uri for uri in uris)

    html_resource = next(
        item for item in resources if item.source_uri.endswith("_05262026-1147?html=true")
    )
    assert html_resource.expected_media_type == "text/html"
    assert html_resource.native_identifier == "civicengage-05262026-1147-html"

    previous = next(item for item in resources if "PreviousVersions" in item.source_uri)
    assert previous.expected_media_type == "text/html"
    assert previous.native_identifier == "civicengage-05262026-1147-versions"


def test_html_extraction_keeps_visible_record_text_without_script_or_style(tmp_path) -> None:
    path = tmp_path / "agenda.html"
    path.write_text(_FIXTURE_HTML, encoding="utf-8")

    units = list(extract_html(path))
    assert len(units) == 1
    unit = units[0]
    assert unit.locator == "record:1"
    assert unit.method == "python_html_visible_text"
    assert "Enter into a contract for $250,000." in unit.text
    assert "Vendor: Northstar Civic Systems" in unit.text
    assert "window.secret" not in unit.text
    assert ".hidden" not in unit.text
    assert unit.quality_score >= 0.70
