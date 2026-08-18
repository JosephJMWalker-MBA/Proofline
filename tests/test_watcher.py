from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from proofline import CorpusWatcher, ProoflineStore, WatchState, load_manifest
from proofline.watch_storage import WatcherStore


class _State:
    body = b"version one"
    status = 200
    content_type = "text/plain"
    failures_remaining = 0
    calls = 0


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _State.calls += 1
        if _State.failures_remaining > 0:
            _State.failures_remaining -= 1
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(_State.status)
        self.send_header("Content-Type", _State.content_type)
        self.send_header("ETag", '"fixture-etag"')
        self.end_headers()
        if _State.status == 200:
            self.wfile.write(_State.body)

    def log_message(self, *args):
        pass


def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _manifest(tmp_path, url: str):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-source-manifest/v1",
                "name": "local fixture",
                "resources": [
                    {
                        "source_uri": url,
                        "source_name": "fixture record",
                        "native_identifier": "FIXTURE-001",
                        "expected_media_type": "text/plain",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_manifest(path)


def test_watcher_reports_new_unchanged_changed_and_unavailable(tmp_path) -> None:
    server, thread = _server()
    try:
        url = f"http://127.0.0.1:{server.server_port}/record.txt"
        manifest = _manifest(tmp_path, url)
        watcher = CorpusWatcher(tmp_path / "state", retry_delay=0)

        _State.body = b"version one"
        _State.status = 200
        first = watcher.run(manifest)
        assert first["results"][0]["state"] == WatchState.NEW.value

        second = watcher.run(manifest)
        assert second["results"][0]["state"] == WatchState.UNCHANGED.value

        _State.body = b"version two"
        third = watcher.run(manifest)
        assert third["results"][0]["state"] == WatchState.CHANGED.value
        assert third["results"][0]["previous_artifact_id"] == first["results"][0]["artifact_id"]

        _State.status = 404
        fourth = watcher.run(manifest)
        assert fourth["results"][0]["state"] == WatchState.UNAVAILABLE.value
        assert fourth["results"][0]["previous_artifact_id"] == third["results"][0]["artifact_id"]

        store = ProoflineStore(tmp_path / "state" / "proofline.db")
        status = store.status()
        assert status["artifacts"] == 2
        watcher_store = WatcherStore(tmp_path / "state" / "proofline.db")
        assert watcher_store.count_checks() == 4
        changes = watcher_store.recent_changes(include_unchanged=False)
        assert {item["state"] for item in changes} == {"new", "changed", "unavailable"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        _State.status = 200
        _State.body = b"version one"
        _State.failures_remaining = 0


def test_watcher_retries_transient_server_errors(tmp_path) -> None:
    server, thread = _server()
    try:
        url = f"http://127.0.0.1:{server.server_port}/retry.txt"
        manifest = _manifest(tmp_path, url)
        _State.status = 200
        _State.body = b"eventual success"
        _State.failures_remaining = 2
        _State.calls = 0

        result = CorpusWatcher(tmp_path / "state", retries=3, retry_delay=0).run(manifest)
        assert result["results"][0]["state"] == "new"
        assert result["results"][0]["attempts"] == 3
        assert _State.calls == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        _State.status = 200
        _State.body = b"version one"
        _State.failures_remaining = 0
