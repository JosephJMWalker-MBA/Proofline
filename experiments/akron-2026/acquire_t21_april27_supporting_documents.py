#!/usr/bin/env python3
"""Acquire the frozen T21 April 27 publisher supporting-document set.

The selected publisher-relation identities are frozen before this stage. This
program verifies the current canonical graph against that identity-only set,
syncs exactly those sources, and emits Bronze/native-Silver inventory metadata
without contextual interpretation or outcome authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from proofline.onbase_attachments import FETCH_STRATEGY, OnBaseAttachmentWatcher
from proofline.storage import ProoflineStore
from proofline.watcher import ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-april27-supporting-document-acquisition/v1"
SELECTION_SCHEMA = "proofline-akron-t21-april27-supporting-document-selection/v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def selection_rows(selection: dict) -> tuple[dict, ...]:
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError(f"selection schema must be {SELECTION_SCHEMA!r}")
    rows = selection.get("selected_documents")
    if not isinstance(rows, list) or not rows:
        raise ValueError("selection must contain selected_documents")

    normalized: list[dict] = []
    seen: set[tuple[int, int, int]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("selected document entry must be an object")
        meeting_id = row.get("meeting_id")
        item_id = row.get("item_id")
        publish_id = row.get("publish_id")
        source_hash = row.get("source_uri_sha256")
        link_hash = row.get("link_text_sha256")
        if not all(isinstance(value, int) and value > 0 for value in (meeting_id, item_id, publish_id)):
            raise ValueError("selected meeting/item/publish IDs must be positive integers")
        for name, value in (("source_uri_sha256", source_hash), ("link_text_sha256", link_hash)):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(ch not in "0123456789abcdef" for ch in value)
            ):
                raise ValueError(f"{name} must be lowercase SHA-256")
        identity = (meeting_id, item_id, publish_id)
        if identity in seen:
            raise ValueError(f"duplicate selected document identity: {identity}")
        seen.add(identity)
        normalized.append(
            {
                "meeting_id": meeting_id,
                "item_id": item_id,
                "publish_id": publish_id,
                "source_uri_sha256": source_hash,
                "link_text_sha256": link_hash,
            }
        )

    normalized.sort(key=lambda row: (row["publish_id"], row["source_uri_sha256"]))
    if selection.get("selected_document_count") != len(normalized):
        raise ValueError("selected_document_count does not match selected_documents")
    if _sha256_json(normalized) != selection.get("selection_signature_sha256"):
        raise ValueError("selection signature does not match selected_documents")
    return tuple(normalized)


def verify_publisher_relations(selection: dict, relations: list[dict]) -> tuple[dict, ...]:
    selected = selection_rows(selection)
    basis = selection.get("basis") or {}
    meeting_id = basis.get("parent_meeting_id")
    item_id = basis.get("parent_item_id")
    expected_count = basis.get("publisher_declared_relation_count")
    if not isinstance(meeting_id, int) or not isinstance(item_id, int):
        raise ValueError("selection parent identity is incomplete")
    if expected_count != len(selected):
        raise ValueError("selection parent relation count disagrees with selected set")

    current = [
        relation
        for relation in relations
        if relation.get("meeting_id") == meeting_id and relation.get("item_id") == item_id
    ]
    current.sort(key=lambda relation: (int(relation.get("publish_id") or 0), str(relation.get("source_uri") or "")))
    if len(current) != expected_count:
        raise ValueError(
            f"publisher relation count drifted for meeting={meeting_id} item={item_id}: "
            f"expected={expected_count} current={len(current)}"
        )

    normalized_current = []
    for relation in current:
        publish_id = relation.get("publish_id")
        source_uri = relation.get("source_uri")
        link_text = relation.get("link_text")
        if not isinstance(publish_id, int) or publish_id <= 0:
            raise ValueError("publisher relation has invalid publish_id")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("publisher relation has empty source_uri")
        if not isinstance(link_text, str):
            raise ValueError("publisher relation has invalid link_text")
        normalized_current.append(
            {
                "meeting_id": meeting_id,
                "item_id": item_id,
                "publish_id": publish_id,
                "source_uri_sha256": _sha256_text(source_uri),
                "link_text_sha256": _sha256_text(link_text),
            }
        )

    normalized_current.sort(key=lambda row: (row["publish_id"], row["source_uri_sha256"]))
    if tuple(normalized_current) != selected:
        raise ValueError("current publisher relation identities no longer match frozen selection")
    return tuple(current)


def _resource_map(attachment_manifest: dict) -> dict[str, dict]:
    if attachment_manifest.get("schema") != "proofline-source-manifest/v1":
        raise ValueError("unexpected attachment manifest schema")
    resources: dict[str, dict] = {}
    for resource in attachment_manifest.get("resources") or []:
        source_uri = resource.get("source_uri")
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("attachment manifest contains empty source_uri")
        if source_uri in resources:
            raise ValueError(f"duplicate attachment source: {source_uri}")
        resources[source_uri] = resource
    return resources


def selected_manifest(
    selection: dict,
    verified_relations: tuple[dict, ...],
    attachment_manifest: dict,
) -> SourceManifest:
    selected = selection_rows(selection)
    relation_by_publish = {int(relation["publish_id"]): relation for relation in verified_relations}
    resources_by_uri = _resource_map(attachment_manifest)
    resources: list[ManifestResource] = []

    for row in selected:
        relation = relation_by_publish.get(row["publish_id"])
        if relation is None:
            raise ValueError(f"missing verified relation for publish_id={row['publish_id']}")
        source_uri = str(relation["source_uri"])
        resource = resources_by_uri.get(source_uri)
        if resource is None:
            raise ValueError(f"selected source missing from attachment manifest: publish_id={row['publish_id']}")
        if resource.get("fetch_strategy") != FETCH_STRATEGY:
            raise ValueError(f"selected source must retain {FETCH_STRATEGY!r} fetch strategy")
        resources.append(
            ManifestResource(
                source_uri=source_uri,
                source_name=resource.get("source_name"),
                native_identifier=resource.get("native_identifier"),
                expected_media_type=resource.get("expected_media_type"),
                sequence_group=resource.get("sequence_group"),
                sequence_number=resource.get("sequence_number"),
                fetch_strategy=resource.get("fetch_strategy"),
            )
        )

    return SourceManifest(
        name="akron-t21-frozen-april27-supporting-documents",
        resources=tuple(resources),
    )


def _page_sort(locator: str) -> tuple[int, str]:
    if locator.startswith("page:"):
        try:
            return int(locator.split(":", 1)[1]), locator
        except ValueError:
            pass
    return 10**9, locator


def _artifact_profile(store: ProoflineStore, artifact_id: str, *, threshold: float) -> dict:
    with store.connection() as connection:
        artifact = connection.execute(
            "SELECT sha256, byte_size, media_type FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if artifact is None:
            raise ValueError(f"unknown supporting-document artifact: {artifact_id}")
        rows = connection.execute(
            """
            SELECT eu.locator, best.extracted_text, best.quality_score, best.method
            FROM evidence_units eu
            JOIN evidence_extractions best
              ON best.extraction_id = (
                SELECT ee.extraction_id
                FROM evidence_extractions ee
                WHERE ee.evidence_id = eu.evidence_id
                ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                         ee.occurred_at DESC,
                         ee.rowid DESC
                LIMIT 1
              )
            WHERE eu.artifact_id = ? AND eu.unit_type = 'page'
            """,
            (artifact_id,),
        ).fetchall()

    page_meta = []
    nonblank = 0
    low_quality = 0
    methods = Counter()
    for row in sorted(rows, key=lambda value: _page_sort(str(value["locator"]))):
        text = str(row["extracted_text"] or "")
        quality = row["quality_score"]
        method = str(row["method"] or "")
        nonblank += int(bool(text.strip()))
        low_quality += int(quality is None or float(quality) < threshold)
        methods[method] += 1
        page_meta.append(
            {
                "locator": str(row["locator"]),
                "text_sha256": _sha256_text(text),
                "quality_score": float(quality) if quality is not None else None,
                "method": method,
                "nonblank": bool(text.strip()),
            }
        )

    return {
        "artifact_id": artifact_id,
        "sha256": str(artifact["sha256"]),
        "byte_size": int(artifact["byte_size"]),
        "media_type": artifact["media_type"],
        "page_count": len(rows),
        "native_nonblank_page_count": nonblank,
        "native_low_quality_page_count": low_quality,
        "preferred_method_counts": dict(sorted(methods.items())),
        "page_metadata_signature_sha256": _sha256_json(page_meta),
    }


def acquire(
    *,
    state_dir: Path,
    selection: dict,
    relations: list[dict],
    attachment_manifest: dict,
    threshold: float,
) -> dict:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")

    selected = selection_rows(selection)
    verified = verify_publisher_relations(selection, relations)
    manifest = selected_manifest(selection, verified, attachment_manifest)
    watch = OnBaseAttachmentWatcher(state_dir).run(manifest)
    watched = {str(result.get("source_uri") or ""): result for result in watch.get("results") or []}
    store = ProoflineStore(state_dir / "proofline.db")

    relation_by_publish = {int(relation["publish_id"]): relation for relation in verified}
    profiles: dict[str, dict] = {}
    documents = []
    available = 0
    unavailable = 0
    artifact_sources: dict[str, list[dict]] = defaultdict(list)

    for row in selected:
        relation = relation_by_publish[row["publish_id"]]
        source_uri = str(relation["source_uri"])
        result = watched.get(source_uri)
        artifact_id = str(result.get("artifact_id")) if result and result.get("artifact_id") else None
        document = {
            "meeting_id": row["meeting_id"],
            "item_id": row["item_id"],
            "publish_id": row["publish_id"],
            "source_uri_sha256": row["source_uri_sha256"],
            "link_text_sha256": row["link_text_sha256"],
            "watch_state": result.get("state") if result else "missing_watch_result",
            "artifact": None,
        }
        if artifact_id is None:
            unavailable += 1
        else:
            available += 1
            profile = profiles.setdefault(
                artifact_id,
                _artifact_profile(store, artifact_id, threshold=threshold),
            )
            document["artifact"] = profile
            artifact_sources[artifact_id].append(
                {
                    "publish_id": row["publish_id"],
                    "source_uri_sha256": row["source_uri_sha256"],
                }
            )
        documents.append(document)

    groups = []
    for artifact_id in sorted(artifact_sources):
        profile = profiles[artifact_id]
        sources = sorted(artifact_sources[artifact_id], key=lambda item: item["publish_id"])
        groups.append(
            {
                "artifact_id": artifact_id,
                "artifact_sha256": profile["sha256"],
                "source_identity_count": len(sources),
                "source_identities": sources,
                "profile": profile,
            }
        )

    total_pages = sum(group["profile"]["page_count"] for group in groups)
    total_nonblank = sum(group["profile"]["native_nonblank_page_count"] for group in groups)
    total_low_quality = sum(group["profile"]["native_low_quality_page_count"] for group in groups)

    return {
        "schema": SCHEMA,
        "stage": "raw_publisher_bounded_bronze_inventory_before_document_contextual_reading",
        "selection": {
            "selection_signature_sha256": selection["selection_signature_sha256"],
            "selected_document_count": len(selected),
            "parent_meeting_id": selection["basis"]["parent_meeting_id"],
            "parent_item_id": selection["basis"]["parent_item_id"],
        },
        "acquisition": {
            "requested_source_count": len(selected),
            "watch_result_count": len(watch.get("results") or []),
            "available_source_count": available,
            "unavailable_source_count": unavailable,
            "content_opened_by_this_execution": available > 0,
            "watch_counts": watch.get("counts") or {},
        },
        "inventory": {
            "unique_bronze_artifact_count": len(groups),
            "duplicate_bronze_artifact_group_count": sum(group["source_identity_count"] > 1 for group in groups),
            "unique_artifact_page_count": total_pages,
            "unique_artifact_native_nonblank_page_count": total_nonblank,
            "unique_artifact_native_low_quality_page_count": total_low_quality,
            "quality_floor": threshold,
        },
        "documents": documents,
        "artifact_groups": groups,
        "authority_boundary": {
            "publisher_relations_reused": True,
            "source_relation_created": False,
            "source_family_modified": False,
            "supporting_document_content_interpreted": False,
            "event_identity_assigned": False,
            "meeting_occurrence_asserted": False,
            "hearing_occurrence_asserted": False,
            "outcome_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "Availability or repeated bytes do not establish document meaning or disposition.",
            "Native extraction quality is inventory metadata, not semantic correctness.",
            "No selected document is contextually interpreted by this stage."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--relations", type=Path, required=True)
    parser.add_argument("--attachment-manifest", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = acquire(
        state_dir=args.state_dir,
        selection=_load(args.selection),
        relations=_load(args.relations),
        attachment_manifest=_load(args.attachment_manifest),
        threshold=args.threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
