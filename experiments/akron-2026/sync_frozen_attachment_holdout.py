#!/usr/bin/env python3
"""Sync the exact frozen R1.T13 attachment holdout by source identity only.

The holdout was frozen in R1.T12 before document content was inspected. Resolution uses
only SHA-256(source_uri) against the live OnBase attachment manifest. Document bytes,
source names, and extracted text do not participate in sample selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from proofline.onbase_attachments import (
    FETCH_STRATEGY,
    RELATION_METHOD,
    RELATION_METHOD_VERSION,
    RELATION_TYPE,
    OnBaseAttachmentWatcher,
)
from proofline.relations import RelationStore
from proofline.watcher import ManifestResource, SourceManifest

SELECTION_SCHEMA = "proofline-akron-t13-disjoint-source-set/v1"
OUTPUT_SCHEMA = "proofline-akron-t13-frozen-attachment-sync/v1"
EXPECTED_EXCLUDED = 32
EXPECTED_SELECTED = 32


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _uri_hash(source_uri: str) -> str:
    return hashlib.sha256(source_uri.encode("utf-8")).hexdigest()


def _signature(hashes: list[str]) -> str:
    payload = "\n".join(hashes) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_selection(manifest_payload: dict, selection_payload: dict) -> tuple[list[dict], dict]:
    if selection_payload.get("schema") != SELECTION_SCHEMA:
        raise ValueError("unexpected T13 frozen selection schema")
    if selection_payload.get("content_inspection_status") != "not_inspected_at_freeze":
        raise ValueError("T13 holdout lost its pre-inspection freeze marker")

    resources = manifest_payload.get("resources")
    if not isinstance(resources, list):
        raise ValueError("attachment manifest has no resources list")

    excluded_block = selection_payload.get("excluded") or {}
    selected_block = selection_payload.get("selected") or {}
    excluded = list(excluded_block.get("source_uri_sha256") or [])
    selected = list(selected_block.get("source_uri_sha256") or [])

    if excluded_block.get("original_manifest_ranks") != [1, 32]:
        raise ValueError("T13 exclusion rank boundary changed")
    if selected_block.get("original_manifest_ranks") != [33, 64]:
        raise ValueError("T13 holdout rank boundary changed")
    if len(excluded) != EXPECTED_EXCLUDED or len(set(excluded)) != EXPECTED_EXCLUDED:
        raise ValueError("T13 exclusion set must contain exactly 32 unique source hashes")
    if len(selected) != EXPECTED_SELECTED or len(set(selected)) != EXPECTED_SELECTED:
        raise ValueError("T13 holdout must contain exactly 32 unique source hashes")
    if set(excluded) & set(selected):
        raise ValueError("T13 development and holdout source sets overlap")
    if excluded != sorted(excluded) or selected != sorted(selected):
        raise ValueError("T13 frozen source hashes are not in deterministic rank order")
    if excluded[-1] >= selected[0]:
        raise ValueError("T13 original rank boundary is not strictly disjoint")

    by_hash: dict[str, dict] = {}
    live_ranked: list[tuple[str, str]] = []
    for resource in resources:
        source_uri = resource.get("source_uri")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("attachment manifest contains a resource without source_uri")
        digest = _uri_hash(source_uri)
        previous = by_hash.get(digest)
        if previous is not None and previous.get("source_uri") != source_uri:
            raise ValueError("source URI SHA-256 collision in attachment manifest")
        by_hash[digest] = resource
        live_ranked.append((digest, source_uri))

    missing_excluded = [digest for digest in excluded if digest not in by_hash]
    missing_selected = [digest for digest in selected if digest not in by_hash]
    if missing_excluded or missing_selected:
        raise ValueError(
            "live discovery cannot reproduce frozen T13 source identities: "
            f"missing_excluded={missing_excluded}, missing_selected={missing_selected}"
        )

    live_ranked.sort()
    live_position = {digest: index + 1 for index, (digest, _) in enumerate(live_ranked)}
    selected_resources = [by_hash[digest] for digest in selected]
    metadata = {
        "excluded_source_hashes": excluded,
        "selected_source_hashes": selected,
        "excluded_signature_sha256": _signature(excluded),
        "selected_signature_sha256": _signature(selected),
        "original_excluded_ranks": [1, 32],
        "original_selected_ranks": [33, 64],
        "live_excluded_ranks": [live_position[digest] for digest in excluded],
        "live_selected_ranks": [live_position[digest] for digest in selected],
        "live_manifest_resource_count": len(resources),
        "selection_basis": "sha256(source_uri) only",
    }
    return selected_resources, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--relations", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest_payload = _load(args.manifest)
    relation_payload = _load(args.relations)
    selection_payload = _load(args.selection)
    selected_resources, selection = resolve_selection(manifest_payload, selection_payload)

    manifest = SourceManifest(
        name="akron-t13-disjoint-32",
        resources=tuple(
            ManifestResource(
                source_uri=item["source_uri"],
                source_name=item.get("source_name"),
                native_identifier=item.get("native_identifier"),
                expected_media_type=item.get("expected_media_type") or "application/pdf",
                fetch_strategy=item.get("fetch_strategy") or FETCH_STRATEGY,
            )
            for item in selected_resources
        ),
    )
    watcher = OnBaseAttachmentWatcher(args.state_dir)
    watched = watcher.run(manifest)

    selected_uris = {item["source_uri"] for item in selected_resources}
    relation_store = RelationStore(args.state_dir)
    matching_relations = [item for item in relation_payload if item.get("source_uri") in selected_uris]
    related_sources = {item.get("source_uri") for item in matching_relations}
    missing_relations = sorted(selected_uris - related_sources)
    if missing_relations:
        raise RuntimeError(f"T13 selected sources lack publisher-backed parent relations: {missing_relations}")

    created = 0
    for relation in matching_relations:
        added = relation_store.add(
            source_uri=relation["source_uri"],
            relation_type=RELATION_TYPE,
            related_source_uri=relation["parent_source_uri"],
            evidence_artifact_id=relation["parent_artifact_id"],
            method=RELATION_METHOD,
            method_version=RELATION_METHOD_VERSION,
            details={
                "meeting_id": relation["meeting_id"],
                "item_id": relation["item_id"],
                "publish_id": relation["publish_id"],
                "link_text": relation.get("link_text") or "",
                "parent_artifact_sha256": relation["parent_artifact_sha256"],
                "evidence_kind": "publisher_supporting_documents_anchor",
            },
        )
        created += int(added is not None)

    output = {
        "schema": OUTPUT_SCHEMA,
        "selection": selection,
        "selected_sources": [
            {
                "source_uri": item["source_uri"],
                "source_uri_sha256": _uri_hash(item["source_uri"]),
                "source_name": item.get("source_name"),
                "native_identifier": item.get("native_identifier"),
            }
            for item in selected_resources
        ],
        "watch": watched,
        "publisher_relation_count": len(matching_relations),
        "relations_created": created,
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))

    counts = watched.get("counts") or {}
    if counts.get("unavailable"):
        raise SystemExit("one or more frozen T13 attachments were unavailable")
    if counts.get("new") != EXPECTED_SELECTED:
        raise SystemExit(f"T13 exact sync did not ingest 32 new sources: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
