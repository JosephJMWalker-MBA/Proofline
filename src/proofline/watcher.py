"""Manifest-driven public source watcher for reproducible change detection."""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .ingest import Ingestor
from .storage import ProoflineStore
from .watch_storage import WatcherStore

_MANIFEST_SCHEMA = "proofline-source-manifest/v1"
_USER_AGENT = "Proofline/0.1 public-record watcher"


class WatchState(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ManifestResource:
    source_uri: str
    source_name: str | None = None
    native_identifier: str | None = None
    expected_media_type: str | None = None


@dataclass(frozen=True, slots=True)
class SourceManifest:
    name: str
    resources: tuple[ManifestResource, ...]
    schema: str = _MANIFEST_SCHEMA


@dataclass(frozen=True, slots=True)
class WatchResult:
    run_id: str
    source_uri: str
    source_id: str
    state: WatchState
    checked_at: datetime
    artifact_id: str | None = None
    previous_artifact_id: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None
    attempts: int = 1

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        data["checked_at"] = self.checked_at.isoformat()
        return data


def load_manifest(path: str | Path) -> SourceManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != _MANIFEST_SCHEMA:
        raise ValueError(f"manifest schema must be {_MANIFEST_SCHEMA!r}")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("manifest name must be a non-empty string")
    raw_resources = payload.get("resources")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise ValueError("manifest resources must be a non-empty list")

    resources: list[ManifestResource] = []
    seen: set[str] = set()
    for item in raw_resources:
        if not isinstance(item, dict):
            raise ValueError("each manifest resource must be an object")
        source_uri = item.get("source_uri")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("resource source_uri must be a non-empty string")
        parsed = urlparse(source_uri)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("M1 watcher currently supports http/https source_uri values")
        if source_uri in seen:
            raise ValueError(f"duplicate source_uri in manifest: {source_uri}")
        seen.add(source_uri)
        resources.append(
            ManifestResource(
                source_uri=source_uri,
                source_name=item.get("source_name"),
                native_identifier=item.get("native_identifier"),
                expected_media_type=item.get("expected_media_type"),
            )
        )
    return SourceManifest(name=name, resources=tuple(resources))


class CorpusWatcher:
    def __init__(
        self,
        state_dir: str | Path = ".proofline",
        *,
        timeout: float = 30.0,
        retries: int = 3,
        retry_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retries < 1:
            raise ValueError("retries must be at least 1")
        self.state_dir = Path(state_dir)
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.sleep = sleep
        db_path = self.state_dir / "proofline.db"
        self.store = ProoflineStore(db_path)
        self.watch_store = WatcherStore(db_path)
        self.ingestor = Ingestor(self.state_dir)

    @staticmethod
    def _base_content_type(value: str | None) -> str | None:
        return value.split(";", 1)[0].strip().lower() if value else None

    @staticmethod
    def _validate_download(path: Path, *, content_type: str | None, expected: str | None) -> None:
        actual = CorpusWatcher._base_content_type(content_type)
        expected = CorpusWatcher._base_content_type(expected)
        if expected and actual and expected != actual:
            raise ValueError(f"expected media type {expected}, received {actual}")
        if expected == "application/pdf" or actual == "application/pdf":
            with path.open("rb") as handle:
                if handle.read(5) != b"%PDF-":
                    raise ValueError("response declared as PDF but PDF magic bytes are missing")

    def _record(self, result: WatchResult, *, manifest_name: str) -> None:
        self.watch_store.add_source_check(
            check_id=f"check:{uuid.uuid4()}",
            run_id=result.run_id,
            source_id=result.source_id,
            checked_at=result.checked_at,
            state=result.state.value,
            artifact_id=result.artifact_id,
            previous_artifact_id=result.previous_artifact_id,
            http_status=result.http_status,
            content_type=result.content_type,
            etag=result.etag,
            last_modified=result.last_modified,
            error=result.error,
            attempts=result.attempts,
            manifest_name=manifest_name,
        )

    def check_resource(self, resource: ManifestResource, *, run_id: str, manifest_name: str) -> WatchResult:
        checked_at = datetime.now(UTC)
        source_id = self.store.add_source(resource.source_uri, resource.source_name)
        previous = self.store.latest_artifact_for_source(source_id)
        last_error: str | None = None
        last_status: int | None = None

        for attempt in range(1, self.retries + 1):
            request = Request(
                resource.source_uri,
                headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
                method="GET",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    status = getattr(response, "status", 200)
                    last_status = int(status)
                    content_type = response.headers.get("Content-Type")
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")

                    temp_dir = self.state_dir / "tmp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    temp_path: Path | None = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            dir=temp_dir, prefix="watch-", suffix=".download", delete=False
                        ) as handle:
                            temp_path = Path(handle.name)
                            while chunk := response.read(1024 * 1024):
                                handle.write(chunk)
                            handle.flush()

                        self._validate_download(
                            temp_path,
                            content_type=content_type,
                            expected=resource.expected_media_type,
                        )
                        media_type = self._base_content_type(content_type) or resource.expected_media_type
                        ingested = self.ingestor.ingest(
                            temp_path,
                            source_uri=resource.source_uri,
                            source_name=resource.source_name,
                            native_identifier=resource.native_identifier,
                            retrieved_at=checked_at,
                            media_type=media_type,
                        )
                    finally:
                        if temp_path is not None and temp_path.exists():
                            temp_path.unlink()

                if previous is None:
                    state = WatchState.NEW
                elif ingested.artifact_id == previous:
                    state = WatchState.UNCHANGED
                else:
                    state = WatchState.CHANGED

                result = WatchResult(
                    run_id=run_id,
                    source_uri=resource.source_uri,
                    source_id=source_id,
                    state=state,
                    checked_at=checked_at,
                    artifact_id=ingested.artifact_id,
                    previous_artifact_id=previous,
                    http_status=last_status,
                    content_type=self._base_content_type(content_type),
                    etag=etag,
                    last_modified=last_modified,
                    attempts=attempt,
                )
                self._record(result, manifest_name=manifest_name)
                return result

            except HTTPError as exc:
                last_status = exc.code
                last_error = f"HTTP {exc.code}: {exc.reason}"
                retryable = exc.code == 429 or 500 <= exc.code <= 599
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = str(exc)
                retryable = not isinstance(exc, ValueError)

            if not retryable or attempt == self.retries:
                result = WatchResult(
                    run_id=run_id,
                    source_uri=resource.source_uri,
                    source_id=source_id,
                    state=WatchState.UNAVAILABLE,
                    checked_at=checked_at,
                    previous_artifact_id=previous,
                    http_status=last_status,
                    error=last_error,
                    attempts=attempt,
                )
                self._record(result, manifest_name=manifest_name)
                return result

            self.sleep(self.retry_delay * (2 ** (attempt - 1)))

        raise AssertionError("watch retry loop exited unexpectedly")

    def run(self, manifest: SourceManifest) -> dict:
        run_id = f"watch:{uuid.uuid4()}"
        results = [
            self.check_resource(resource, run_id=run_id, manifest_name=manifest.name)
            for resource in manifest.resources
        ]
        counts = {state.value: 0 for state in WatchState}
        for result in results:
            counts[result.state.value] += 1
        return {
            "run_id": run_id,
            "manifest": manifest.name,
            "counts": counts,
            "results": [result.to_dict() for result in results],
        }
