#!/usr/bin/env python3
"""Resolve and sync the frozen R1.T19 ranks 65-96 attachment holdout.

The holdout was frozen as source-identity hashes before the local-grouping
representation was developed. This script is the first allowed resolution of
those hashes back to publisher source URIs. Selection is identity-only; no
filename, document bytes/text, money facts, layout features, or semantic labels
participate in resolution.
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

SELECTION_SCHEMA = "proofline-akron-t19-future-holdout-source-set/v1"
OUTPUT_SCHEMA = "proofline-akron-t19-frozen-attachment-sync/v1"
EXPECTED_MANIFEST_SHA256 = "7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a"
EXPECTED_MANIFEST_COUNT = 2327
EXPECTED_EXCLUDED_SIGNATURE = "ce876915836a86c914ca837964a95fcc4f4857d423eaadfa91749978eb9715a0"
EXPECTED_SELECTED_SIGNATURE = "5116c4ec5a23346138fc3dd809458fc124e64b79fead51c8bad3e3e08d56807b"
EXPECTED_COMBINED_SIGNATURE = "e6288eeda9d527ffcc9189b01cf0c101e5f42d122070fc563ebe798ce1189b61"
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
        raise ValueError("unexpected T19 future-holdout schema")
    if selection_payload.get("content_inspection_status") != "identity_hash_only_not_resolved_or_inspected":
        raise ValueError("T19 holdout lost its pre-open information-barrier marker")

    provenance = selection_payload.get("provenance") or {}
    if provenance.get("source_manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise ValueError("T19 holdout no longer names the preserved attachment manifest")
    if provenance.get("source_manifest_resource_count") != EXPECTED_MANIFEST_COUNT:
        raise ValueError("T19 holdout manifest resource count changed")

    excluded = selection_payload.get("already_opened_exclusion") or {}
    selected = selection_payload.get("selected") or {}
    selected_hashes = list(selected.get("source_uri_sha256") or [])

    if excluded.get("original_manifest_ranks") != [1, 64]:
        raise ValueError("T19 already-opened exclusion rank boundary changed")
    if excluded.get("count") != 64 or excluded.get("signature_sha256") != EXPECTED_EXCLUDED_SIGNATURE:
        raise ValueError("T19 ranks 1-64 exclusion signature changed")
    if selected.get("original_manifest_ranks") != [65, 96]:
        raise ValueError("T19 future holdout rank boundary changed")
    if selected.get("count") != EXPECTED_SELECTED:
        raise ValueError("T19 future holdout count changed")
    if len(selected_hashes) != EXPECTED_SELECTED or len(set(selected_hashes)) != EXPECTED_SELECTED:
        raise ValueError("T19 future holdout must contain 32 unique identity hashes")
    if selected_hashes != sorted(selected_hashes):
        raise ValueError("T19 future holdout hashes are not in deterministic rank order")
    if _signature(selected_hashes) != EXPECTED_SELECTED_SIGNATURE:
        raise ValueError("T19 future holdout selected signature changed")
    if selected.get("signature_sha256") != EXPECTED_SELECTED_SIGNATURE:
        raise ValueError("T19 stored selected signature is inconsistent")
    if selection_payload.get("combined_rank_1_96_signature_sha256") != EXPECTED_COMBINED_SIGNATURE:
        raise ValueError("T19 combined ranks 1-96 signature changed")

    resources = manifest_payload.get("resources")
    if not isinstance(resources, list) or len(resources) != EXPECTED_MANIFEST_COUNT:
        raise ValueError("live attachment manifest does not contain the preserved 2,327-source population")

    by_hash: dict[str, dict] = {}
    ranked: list[tuple[str, str]] = []
    for resource in resources:
        source_uri = resource.get("source_uri")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("attachment manifest contains a resource without source_uri")
        digest = _uri_hash(source_uri)
        previous = by_hash.get(digest)
        if previous is not None and previous.get("source_uri") != source_uri:
            raise ValueError("source URI SHA-256 collision in attachment manifest")
        by_hash[digest] = resource
        ranked.append((digest, source_uri))

    ranked.sort()
    ranked_hashes = [digest for digest, _ in ranked]
    if _signature(ranked_hashes[:64]) != EXPECTED_EXCLUDED_SIGNATURE:
        raise ValueError("live ranks 1-64 no longer reproduce the frozen opened-data exclusion")
    if ranked_hashes[64:96] != selected_hashes:
        raise ValueError("live ranks 65-96 do not reproduce the frozen T19 holdout identities")
    if _signature(ranked_hashes[64:96]) != EXPECTED_SELECTED_SIGNATURE:
        raise ValueError("live ranks 65-96 signature changed")
    if _signature(ranked_hashes[:96]) != EXPECTED_COMBINED_SIGNATURE:
        raise ValueError("live combined ranks 1-96 signature changed")

    selected_resources = [by_hash[digest] for digest in selected_hashes]
    metadata = {
        "selected_source_hashes": selected_hashes,
        "selected_signature_sha256": EXPECTED_SELECTED_SIGNATURE,
        "excluded_signature_sha256": EXPECTED_EXCLUDED_SIGNATURE,
        "combined_rank_1_96_signature_sha256": EXPECTED_COMBINED_SIGNATURE,
        "original_selected_ranks": [65, 96],
        "live_selected_ranks": list(range(65, 97)),
        "live_manifest_resource_count": len(resources),
        "selection_basis": "sha256(source_uri) only; frozen before local-grouping-v1 development",
        "holdout_opened_by_this_execution": True,
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
        name="akron-t19-frozen-ranks-65-96",
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
    matching_relations = [item for item in relation_payload if item.get("source_uri") in selected_uris]
    related_sources = {item.get("source_uri") for item in matching_relations}
    missing_relations = sorted(selected_uris - related_sources)
    if missing_relations:
        raise RuntimeError(f"T19 holdout sources lack publisher-backed parent relations: {missing_relations}")

    relation_store = RelationStore(args.state_dir)
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
        raise SystemExit("one or more frozen T19 attachments were unavailable")
    if counts.get("new") != EXPECTED_SELECTED:
        raise SystemExit(f"T19 fresh-state holdout sync did not ingest 32 new sources: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
