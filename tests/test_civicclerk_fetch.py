from __future__ import annotations

import io
import json

import pymupdf
import pytest

from proofline import CorpusWatcher, ManifestResource, ProoflineStore, SourceManifest, load_manifest


class _FakeResponse:
    def __init__(self, body: bytes, *, content_type: str, url: str, status: int = 200) -> None:
        self._stream = io.BytesIO(body)
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "ETag": '"fixture-etag"',
            "Last-Modified": "Wed, 19 Aug 2026 12:00:00 GMT",
        }
        self._url = url

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def test_civicclerk_blob_strategy_keeps_stable_source_identity_across_transport_rotation(
    tmp_path, monkeypatch
) -> None:
    source_uri = (
        "https://cantonoh.api.civicclerk.com/v1/Meetings/"
        "GetMeetingFile(fileId=3695,plainText=false)"
    )
    blob_path = "https://civicclerk.blob.core.windows.net/stream/CANTONOH/agenda.pdf"
    state = {
        "blob_uri": f"{blob_path}?sv=one&sp=rw&sig=DO_NOT_PERSIST_ONE",
        "pdf": _pdf_bytes("agenda version one"),
    }

    def fake_urlopen(request, timeout=30):
        uri = request.full_url
        if uri == source_uri:
            body = json.dumps({"blobUri": state["blob_uri"]}).encode("utf-8")
            return _FakeResponse(body, content_type="application/json; charset=utf-8", url=source_uri)
        if uri == state["blob_uri"]:
            return _FakeResponse(state["pdf"], content_type="application/pdf", url=uri)
        raise AssertionError(f"unexpected URL: {uri}")

    monkeypatch.setattr("proofline.watcher.urlopen", fake_urlopen)
    manifest = SourceManifest(
        name="civicclerk fixture",
        resources=(
            ManifestResource(
                source_uri=source_uri,
                source_name="City Council — 2026-01-05 — Agenda",
                native_identifier="civicclerk-cantonoh-file-3695-agenda",
                expected_media_type="application/pdf",
                fetch_strategy="civicclerk_blob",
            ),
        ),
    )
    watcher = CorpusWatcher(tmp_path / "state", retries=1, retry_delay=0)

    first = watcher.run(manifest)
    assert first["results"][0]["state"] == "new"
    assert first["results"][0]["source_uri"] == source_uri
    assert first["results"][0]["content_type"] == "application/pdf"

    # A fresh publisher-issued signed transport for identical PDF bytes must not
    # create a source change. The stable CivicClerk file API URI is the identity.
    state["blob_uri"] = f"{blob_path}?sv=two&sp=rw&sig=DO_NOT_PERSIST_TWO"
    second = watcher.run(manifest)
    assert second["results"][0]["state"] == "unchanged"
    assert second["results"][0]["artifact_id"] == first["results"][0]["artifact_id"]

    # Changed PDF bytes behind the same stable source URI are a real source change.
    state["blob_uri"] = f"{blob_path}?sv=three&sp=rw&sig=DO_NOT_PERSIST_THREE"
    state["pdf"] = _pdf_bytes("agenda version two")
    third = watcher.run(manifest)
    assert third["results"][0]["state"] == "changed"
    assert third["results"][0]["artifact_id"] != first["results"][0]["artifact_id"]

    store = ProoflineStore(tmp_path / "state" / "proofline.db")
    with store.connection() as connection:
        serialized = "\n".join(
            str(value)
            for row in connection.execute("SELECT * FROM source_checks").fetchall()
            for value in tuple(row)
        )
        source_rows = connection.execute("SELECT source_uri FROM sources").fetchall()
    assert all(row["source_uri"] == source_uri for row in source_rows)
    assert "DO_NOT_PERSIST" not in serialized
    assert "civicclerk.blob.core.windows.net" not in serialized


def test_civicclerk_blob_strategy_rejects_untrusted_transport_without_leaking_query(
    tmp_path, monkeypatch
) -> None:
    source_uri = (
        "https://cantonoh.api.civicclerk.com/v1/Meetings/"
        "GetMeetingFile(fileId=3695,plainText=false)"
    )
    hostile = "https://evil.example/agenda.pdf?sig=DO_NOT_LEAK"

    def fake_urlopen(request, timeout=30):
        uri = request.full_url
        if uri == source_uri:
            body = json.dumps({"blobUri": hostile}).encode("utf-8")
            return _FakeResponse(body, content_type="application/json", url=source_uri)
        raise AssertionError("untrusted blob URI must never be fetched")

    monkeypatch.setattr("proofline.watcher.urlopen", fake_urlopen)
    manifest = SourceManifest(
        name="unsafe civicclerk fixture",
        resources=(
            ManifestResource(
                source_uri=source_uri,
                expected_media_type="application/pdf",
                fetch_strategy="civicclerk_blob",
            ),
        ),
    )

    result = CorpusWatcher(tmp_path / "state", retries=3, retry_delay=0).run(manifest)
    item = result["results"][0]
    assert item["state"] == "unavailable"
    assert item["attempts"] == 1
    assert item["error"] == "CivicClerk blobUri host is not allowed"
    assert "DO_NOT_LEAK" not in json.dumps(result)


def test_manifest_rejects_unknown_fetch_strategy(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "proofline-source-manifest/v1",
                "name": "bad fetch strategy",
                "resources": [
                    {
                        "source_uri": "https://example.gov/document.pdf",
                        "fetch_strategy": "follow_any_redirect_from_json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported fetch_strategy"):
        load_manifest(path)
