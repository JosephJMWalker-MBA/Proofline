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
from urllib.parse import urlparse, urlsplit
from urllib.request import Request, urlopen

from .ingest import Ingestor
from .storage import ProoflineStore
from .watch_storage import WatcherStore

_MANIFEST_SCHEMA = "proofline-source-manifest/v1"
_USER_AGENT = "Proofline/0.1 public-record watcher"
_CIVICCLERK_BLOB_STRATEGY = "civicclerk_blob"
_ALLOWED_FETCH_STRATEGIES = {None, _CIVICCLERK_BLOB_STRATEGY}
_MAX_ENVELOPE_BYTES = 1024 * 1024


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
    sequence_group: str | None = None
    sequence_number: int | None = None
    fetch_strategy: str | None = None


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


@dataclass(frozen=True, slots=True)
class _DownloadMetadata:
    http_status: int
    content_type: str | None
    etag: str | None
    last_modified: str | None


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
        sequence_group = item.get("sequence_group")
        sequence_number = item.get("sequence_number")
        if (sequence_group is None) != (sequence_number is None):
            raise ValueError("sequence_group and sequence_number must be provided together")
        if sequence_group is not None and (not isinstance(sequence_group, str) or not sequence_group):
            raise ValueError("sequence_group must be a non-empty string")
        if sequence_number is not None and (not isinstance(sequence_number, int) or sequence_number < 0):
            raise ValueError("sequence_number must be a non-negative integer")
        fetch_strategy = item.get("fetch_strategy")
        if fetch_strategy not in _ALLOWED_FETCH_STRATEGIES:
            raise ValueError(f"unsupported fetch_strategy: {fetch_strategy!r}")
        resources.append(
            ManifestResource(
                source_uri=source_uri,
                source_name=item.get("source_name"),
                native_identifier=item.get("native_identifier"),
                expected_media_type=item.get("expected_media_type"),
                sequence_group=sequence_group,
                sequence_number=sequence_number,
                fetch_strategy=fetch_strategy,
            )
        )
    return SourceManifest(name=name, resources=tuple(resources))


def manifest_sequence_gaps(manifest: SourceManifest) -> list[dict]:
    """Return explicit numeric gaps from manifest-declared sequence metadata."""
    groups: dict[str, set[int]] = {}
    for resource in manifest.resources:
        if resource.sequence_group is None or resource.sequence_number is None:
            continue
        groups.setdefault(resource.sequence_group, set()).add(resource.sequence_number)

    gaps: list[dict] = []
    for group, observed_set in sorted(groups.items()):
        observed = sorted(observed_set)
        if len(observed) < 2:
            continue
        missing = [number for number in range(observed[0], observed[-1] + 1) if number not in observed_set]
        if missing:
            gaps.append(
                {
                    "sequence_group": group,
                    "observed_min": observed[0],
                    "observed_max": observed[-1],
                    "missing": missing,
                }
            )
    return gaps


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

    @staticmethod
    def _civicclerk_blob_uri(source_uri: str, payload: object) -> str:
        """Return a validated ephemeral CivicClerk blob transport without persisting it."""
        source = urlsplit(source_uri)
        hostname = (source.hostname or "").lower()
        suffix = ".api.civicclerk.com"
        if source.scheme != "https" or not hostname.endswith(suffix):
            raise ValueError("civicclerk_blob requires an HTTPS *.api.civicclerk.com source_uri")
        tenant = hostname[: -len(suffix)]
        if not tenant or "." in tenant:
            raise ValueError("civicclerk_blob source_uri must identify one CivicClerk tenant")
        if not isinstance(payload, dict):
            raise ValueError("CivicClerk file response must be a JSON object")
        blob_uri = payload.get("blobUri")
        if not isinstance(blob_uri, str) or not blob_uri:
            raise ValueError("CivicClerk file response did not include blobUri")
        blob = urlsplit(blob_uri)
        if blob.scheme != "https" or (blob.hostname or "").lower() != "civicclerk.blob.core.windows.net":
            raise ValueError("CivicClerk blobUri host is not allowed")
        expected_prefix = f"/stream/{tenant.upper()}/"
        if not blob.path.startswith(expected_prefix):
            raise ValueError("CivicClerk blobUri tenant path does not match source tenant")
        return blob_uri

    @staticmethod
    def _write_response(response, destination: Path) -> _DownloadMetadata:
        status = int(getattr(response, "status", 200))
        content_type = response.headers.get("Content-Type")
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        with destination.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
            handle.flush()
        return _DownloadMetadata(
            http_status=status,
            content_type=content_type,
            etag=etag,
            last_modified=last_modified,
        )

    def _download_direct(self, resource: ManifestResource, destination: Path) -> _DownloadMetadata:
        request = Request(
            resource.source_uri,
            headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
            method="GET",
        )
        with urlopen(request, timeout=self.timeout) as response:
            return self._write_response(response, destination)

    def _download_civicclerk_blob(
        self,
        resource: ManifestResource,
        destination: Path,
    ) -> _DownloadMetadata:
        envelope_request = Request(
            resource.source_uri,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            method="GET",
        )
        with urlopen(envelope_request, timeout=self.timeout) as response:
            envelope_status = int(getattr(response, "status", 200))
            raw = response.read(_MAX_ENVELOPE_BYTES + 1)
            if len(raw) > _MAX_ENVELOPE_BYTES:
                raise ValueError("CivicClerk file envelope exceeded size limit")
            content_type = self._base_content_type(response.headers.get("Content-Type"))
            if content_type != "application/json":
                raise ValueError(
                    f"CivicClerk file envelope must be application/json, received {content_type or 'unknown'}"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("CivicClerk file envelope was not valid UTF-8 JSON") from exc
            if envelope_status < 200 or envelope_status >= 300:
                raise ValueError(f"CivicClerk file envelope returned HTTP {envelope_status}")

        blob_uri = self._civicclerk_blob_uri(resource.source_uri, payload)
        blob_request = Request(
            blob_uri,
            headers={"User-Agent": _USER_AGENT, "Accept": resource.expected_media_type or "*/*"},
            method="GET",
        )
        with urlopen(blob_request, timeout=self.timeout) as response:
            return self._write_response(response, destination)

    def _download_resource(self, resource: ManifestResource, destination: Path) -> _DownloadMetadata:
        if resource.fetch_strategy is None:
            return self._download_direct(resource, destination)
        if resource.fetch_strategy == _CIVICCLERK_BLOB_STRATEGY:
            return self._download_civicclerk_blob(resource, destination)
        raise ValueError(f"unsupported fetch_strategy: {resource.fetch_strategy!r}")

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
        previous = self.watch_store.latest_successful_artifact(source_id)
        if previous is None:
            previous = self.store.latest_artifact_for_source(source_id)
        last_error: str | None = None
        last_status: int | None = None

        for attempt in range(1, self.retries + 1):
            temp_dir = self.state_dir / "tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=temp_dir, prefix="watch-", suffix=".download", delete=False
                ) as handle:
                    temp_path = Path(handle.name)

                metadata = self._download_resource(resource, temp_path)
                last_status = metadata.http_status
                self._validate_download(
                    temp_path,
                    content_type=metadata.content_type,
                    expected=resource.expected_media_type,
                )
                media_type = self._base_content_type(metadata.content_type) or resource.expected_media_type
                ingested = self.ingestor.ingest(
                    temp_path,
                    source_uri=resource.source_uri,
                    source_name=resource.source_name,
                    native_identifier=resource.native_identifier,
                    retrieved_at=checked_at,
                    media_type=media_type,
                )

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
                    content_type=self._base_content_type(metadata.content_type),
                    etag=metadata.etag,
                    last_modified=metadata.last_modified,
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
            finally:
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink()

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
            "sequence_gaps": manifest_sequence_gaps(manifest),
            "results": [result.to_dict() for result in results],
        }
