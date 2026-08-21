#!/usr/bin/env python3
"""Export one frozen T20b audit candidate as a neutrally named PDF.

This is post-result audit tooling. It resolves a source only by its already-opened
SHA-256 identity, downloads that exact publisher-backed PDF through the existing
OnBase watcher transport, verifies the stored artifact digest, and copies only the
PDF bytes to the requested output path. It emits no machine result or annotation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from evaluate_local_grouping_holdout import _artifact_metadata
from proofline.hashing import source_id_from_uri
from proofline.onbase_attachments import FETCH_STRATEGY, OnBaseAttachmentWatcher
from proofline.storage import ProoflineStore
from proofline.watcher import ManifestResource, SourceManifest
from proofline.watch_storage import WatcherStore


def _uri_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-hash", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    resources = payload.get("resources") or []
    matches = [item for item in resources if _uri_hash(str(item.get("source_uri") or "")) == args.source_hash]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one source for frozen identity hash; found {len(matches)}")
    item = matches[0]
    source_uri = str(item["source_uri"])

    manifest = SourceManifest(
        name="t20b-blind-audit-single-source",
        resources=(
            ManifestResource(
                source_uri=source_uri,
                source_name=None,
                native_identifier=None,
                expected_media_type=item.get("expected_media_type") or "application/pdf",
                fetch_strategy=item.get("fetch_strategy") or FETCH_STRATEGY,
            ),
        ),
    )
    state_dir = Path(args.state_dir)
    watcher = OnBaseAttachmentWatcher(state_dir)
    result = watcher.run(manifest)
    counts = result.get("counts") or {}
    if counts.get("unavailable") or counts.get("new") != 1:
        raise RuntimeError(f"single-source blind export did not ingest exactly one PDF: {counts}")

    source_id = source_id_from_uri(source_uri)
    watch_store = WatcherStore(state_dir / "proofline.db")
    store = ProoflineStore(state_dir / "proofline.db")
    artifact_id = watch_store.latest_successful_artifact(source_id) or store.latest_artifact_for_source(source_id)
    if artifact_id is None:
        raise RuntimeError("blind export source has no successful artifact")
    metadata = _artifact_metadata(store, artifact_id)
    if metadata["media_type"] != "application/pdf":
        raise RuntimeError("blind export artifact is not a PDF")

    source_path = state_dir / metadata["stored_path"]
    actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if actual_sha != metadata["sha256"]:
        raise RuntimeError("stored blind export bytes do not reproduce artifact SHA-256")

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
