"""Resolve tightly constrained public-record indirection without general web crawling."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pymupdf

from .storage import ProoflineStore
from .watcher import ManifestResource, SourceManifest

_UUID_PATH_RE = re.compile(
    r"^/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/?$"
)


def _normalized_host(uri: str) -> str:
    host = (urlparse(uri).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _safe_pointer_target(source_uri: str, target_uri: str) -> bool:
    source = urlparse(source_uri)
    target = urlparse(target_uri)
    if source.scheme not in {"http", "https"} or target.scheme not in {"http", "https"}:
        return False
    if _normalized_host(source_uri) != _normalized_host(target_uri):
        return False
    return bool(_UUID_PATH_RE.fullmatch(target.path))


def discover_pointer_pdf_resources(
    state_dir: str | Path,
    manifest: SourceManifest,
    watch_result: dict,
) -> tuple[ManifestResource, ...]:
    """Find same-site UUID targets in otherwise empty one-page PDF wrappers.

    This deliberately does *not* follow arbitrary PDF links. A candidate must:

    - be a successfully preserved PDF from the supplied manifest;
    - contain exactly one page;
    - contain no visible text and no images;
    - expose exactly one URI link;
    - point to the same normalized host; and
    - use a UUID-only path, matching the CivicEngage wrapper shape observed in R0.

    The wrapper remains immutable evidence. The returned target becomes a separate
    source and can be watched/ingested through the normal Proofline path.
    """
    root = Path(state_dir)
    store = ProoflineStore(root / "proofline.db")
    by_uri = {resource.source_uri: resource for resource in manifest.resources}
    discovered: dict[str, ManifestResource] = {}

    for item in watch_result.get("results", []):
        source_uri = item.get("source_uri")
        artifact_id = item.get("artifact_id")
        parent = by_uri.get(source_uri)
        if parent is None or not artifact_id:
            continue

        with store.connection() as connection:
            row = connection.execute(
                "SELECT media_type, stored_path FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None or row["media_type"] != "application/pdf":
            continue

        path = root / row["stored_path"]
        try:
            with pymupdf.open(path) as document:
                if len(document) != 1:
                    continue
                page = document[0]
                if (page.get_text("text") or "").strip():
                    continue
                if page.get_images(full=True):
                    continue
                uri_links = [
                    link.get("uri")
                    for link in page.get_links()
                    if isinstance(link.get("uri"), str) and link.get("uri")
                ]
        except Exception:
            continue

        unique_links = tuple(dict.fromkeys(uri_links))
        if len(unique_links) != 1:
            continue
        target_uri = unique_links[0]
        if not _safe_pointer_target(source_uri, target_uri):
            continue

        uuid_value = urlparse(target_uri).path.strip("/").casefold()
        parent_name = parent.source_name or source_uri
        discovered[target_uri] = ManifestResource(
            source_uri=target_uri,
            source_name=f"{parent_name} — LINKED RECORD",
            native_identifier=f"linked-record-{uuid_value}",
            expected_media_type=None,
        )

    return tuple(discovered[uri] for uri in sorted(discovered))
