from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pymupdf

from proofline import Ingestor
from proofline.onbase import OnBaseAgendaPlan
from proofline.onbase_attachments import (
    FETCH_STRATEGY,
    RELATION_TYPE,
    OnBaseAttachmentDiscoverer,
    OnBaseAttachmentWatcher,
    _byte_transport_uri,
)
from proofline.relations import RelationStore
from proofline.watcher import ManifestResource, SourceManifest


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


_PDF = _pdf_bytes("Proofline OnBase supporting document fixture")


def _wrapper() -> str:
    return """
    <!DOCTYPE html>
    <html><body>
    <script>
      $(document).ready(function () {
        if (window.location.toString().indexOf("DownloadFileBytes") < 0) {
          window.location = window.location.toString().replace("DownloadFile", "DownloadFileBytes");
        }
      });
    </script>
    </body></html>
    """


class _AttachmentHandler(BaseHTTPRequestHandler):
    server_version = "ProoflineOnBaseAttachmentFixture/1"
    byte_requests = 0

    def log_message(self, format, *args):
        return

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if "/Documents/DownloadFileBytes/" in path:
            type(self).byte_requests += 1
            self._send(_PDF, "application/pdf")
            return
        if "/Documents/DownloadFile/bad.pdf" in path:
            self._send(b"<html><body>No byte transport declaration</body></html>", "text/html")
            return
        if "/Documents/DownloadFile/" in path:
            self._send(_wrapper().encode("utf-8"), "text/html; charset=utf-8")
            return
        self.send_response(404)
        self.end_headers()


def _serve():
    _AttachmentHandler.byte_requests = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _AttachmentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_wrapper_declares_same_identity_byte_transport() -> None:
    source = (
        "https://records.example.gov/OnBaseAgendaOnline/Documents/DownloadFile/doc.pdf"
        "?documentType=1&meetingId=10&itemId=20&publishId=30"
        "&isSection=False&isAttachment=True"
    )
    result = _byte_transport_uri(source, _wrapper())
    assert result == source.replace("/DownloadFile/", "/DownloadFileBytes/")
    try:
        _byte_transport_uri(source, "<html>no declaration</html>")
    except ValueError as exc:
        assert "did not declare" in str(exc)
    else:
        raise AssertionError("wrapper without publisher declaration should be rejected")


def test_discovery_sync_and_relation_preserve_stable_downloadfile_identity(tmp_path) -> None:
    server, thread = _serve()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}/OnBaseAgendaOnline"
        parent_uri = (
            f"{base}/Meetings/ViewMeetingAgendaItem"
            "?meetingId=10&itemId=101&isSection=false&type=agenda"
        )
        good_href = (
            "/OnBaseAgendaOnline/Documents/DownloadFile/support.pdf"
            "?documentType=1&meetingId=10&itemId=101&publishId=500"
            "&isSection=False&isAttachment=True"
        )
        bad_href = (
            "/OnBaseAgendaOnline/Documents/DownloadFile/wrong.pdf"
            "?documentType=1&meetingId=10&itemId=999&publishId=501"
            "&isSection=False&isAttachment=True"
        )
        parent = tmp_path / "parent.html"
        parent.write_text(
            "<html><body><h2>Supporting Documents</h2>"
            f'<a href="{good_href}">Supporting Document A</a>'
            f'<a href="{bad_href}">Supporting Document mismatch</a>'
            '<a href="/outline">Back to Meeting Outline</a>'
            "</body></html>",
            encoding="utf-8",
        )

        state = tmp_path / "state"
        parent_ingest = Ingestor(state).ingest(
            parent,
            source_uri=parent_uri,
            media_type="text/html",
        )
        canonical = SourceManifest(
            name="fixture:onbase-agenda-items",
            resources=(
                ManifestResource(
                    source_uri=parent_uri,
                    source_name="Fixture agenda item",
                    expected_media_type="text/html",
                ),
            ),
        )
        plan = OnBaseAgendaPlan(
            name="fixture",
            source_uri=f"{base}/Meetings",
            meeting_type_ids=(101,),
            years=(2026,),
        )

        discoverer = OnBaseAttachmentDiscoverer(state)
        discovered = discoverer.discover(plan, canonical)
        assert discovered.parent_item_count == 1
        assert discovered.items_with_support_marker == 1
        assert discovered.items_with_accepted_links == 1
        assert len(discovered.manifest.resources) == 1
        assert len(discovered.relations) == 1
        assert len(discovered.rejected_links) == 1
        assert "itemId does not match" in discovered.rejected_links[0].reason

        resource = discovered.manifest.resources[0]
        assert "/Documents/DownloadFile/" in resource.source_uri
        assert "/DownloadFileBytes/" not in resource.source_uri
        assert resource.expected_media_type == "application/pdf"
        assert resource.fetch_strategy == FETCH_STRATEGY
        relation = discovered.relations[0]
        assert relation.parent_source_uri == parent_uri
        assert relation.parent_artifact_id == parent_ingest.artifact_id
        assert relation.publish_id == 500

        first = discoverer.sync(discovered, limit=1)
        assert first["resource_count"] == 1
        assert first["watch"]["counts"]["new"] == 1
        assert first["watch"]["counts"]["unavailable"] == 0
        assert first["relations_created"] == 1
        assert first["relations_total"] == 1
        assert _AttachmentHandler.byte_requests == 1

        stored_relations = RelationStore(state).list(relation_type=RELATION_TYPE)
        assert len(stored_relations) == 1
        stored = stored_relations[0]
        assert stored.source_uri == resource.source_uri
        assert stored.related_source_uri == parent_uri
        assert stored.evidence_artifact_id == parent_ingest.artifact_id

        with discoverer.watcher.store.connection() as connection:
            attachment_sources = connection.execute(
                "SELECT source_uri FROM sources WHERE source_uri LIKE '%/Documents/DownloadFile/%'"
            ).fetchall()
            byte_sources = connection.execute(
                "SELECT source_uri FROM sources WHERE source_uri LIKE '%/DownloadFileBytes/%'"
            ).fetchall()
            pdf_artifacts = connection.execute(
                """
                SELECT a.media_type
                FROM sources s
                JOIN source_snapshots ss ON ss.source_id = s.source_id
                JOIN artifacts a ON a.artifact_id = ss.artifact_id
                WHERE s.source_uri = ?
                """,
                (resource.source_uri,),
            ).fetchall()
        assert [row["source_uri"] for row in attachment_sources] == [resource.source_uri]
        assert byte_sources == []
        assert pdf_artifacts and all(row["media_type"] == "application/pdf" for row in pdf_artifacts)

        second = discoverer.sync(discovered, limit=1)
        assert second["watch"]["counts"]["unchanged"] == 1
        assert second["watch"]["counts"]["unavailable"] == 0
        assert second["relations_created"] == 0
        assert second["relations_total"] == 1
        assert _AttachmentHandler.byte_requests == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_missing_wrapper_declaration_fails_closed_as_unavailable(tmp_path) -> None:
    server, thread = _serve()
    try:
        host, port = server.server_address
        source_uri = (
            f"http://{host}:{port}/OnBaseAgendaOnline/Documents/DownloadFile/bad.pdf"
            "?documentType=1&meetingId=10&itemId=101&publishId=500"
            "&isSection=False&isAttachment=True"
        )
        watcher = OnBaseAttachmentWatcher(tmp_path / "state", retries=1)
        result = watcher.run(
            SourceManifest(
                name="bad-wrapper",
                resources=(
                    ManifestResource(
                        source_uri=source_uri,
                        expected_media_type="application/pdf",
                        fetch_strategy=FETCH_STRATEGY,
                    ),
                ),
            )
        )
        assert result["counts"]["unavailable"] == 1
        assert "did not declare DownloadFileBytes transport" in result["results"][0]["error"]
        assert _AttachmentHandler.byte_requests == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
