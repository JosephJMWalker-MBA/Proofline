#!/usr/bin/env python3
"""Measure byte-level evolution of the frozen T21 publisher-backed packet family.

Source identities are frozen from the completed exact-reference probe. This stage
verifies those identities against publisher-declared ``supporting_document_of``
relations, syncs exactly those packet sources, and measures document evolution.
It does not assign SourceFamily, event, outcome, detector, or lead authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from proofline.explicit_references import extract_explicit_references
from proofline.onbase_attachments import FETCH_STRATEGY, OnBaseAttachmentWatcher
from proofline.storage import ProoflineStore
from proofline.watcher import ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-record-family-evolution/v1"
SELECTION_SCHEMA = "proofline-akron-t21-record-family-packet-selection/v1"
MANIFEST_SCHEMA = "proofline-source-manifest/v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_json(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _selection_rows(selection: dict) -> tuple[dict, ...]:
    if selection.get("schema") != SELECTION_SCHEMA:
        raise ValueError(f"selection schema must be {SELECTION_SCHEMA!r}")
    rows = selection.get("selected_packets")
    if not isinstance(rows, list) or not rows:
        raise ValueError("selection must contain selected_packets")

    normalized: list[dict] = []
    seen: set[tuple[int, int, int]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("selected packet entry must be an object")
        meeting_id = row.get("meeting_id")
        item_id = row.get("item_id")
        publish_id = row.get("publish_id")
        source_hash = row.get("source_uri_sha256")
        if not all(
            isinstance(value, int) and value > 0
            for value in (meeting_id, item_id, publish_id)
        ):
            raise ValueError("selected meeting/item/publish IDs must be positive integers")
        if (
            not isinstance(source_hash, str)
            or len(source_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in source_hash)
        ):
            raise ValueError("source_uri_sha256 must be lowercase SHA-256")
        identity = (meeting_id, item_id, publish_id)
        if identity in seen:
            raise ValueError(f"duplicate selected packet identity: {identity}")
        seen.add(identity)
        normalized.append(
            {
                "meeting_id": meeting_id,
                "item_id": item_id,
                "publish_id": publish_id,
                "source_uri_sha256": source_hash,
            }
        )

    normalized.sort(
        key=lambda row: (
            row["meeting_id"],
            row["item_id"],
            row["publish_id"],
            row["source_uri_sha256"],
        )
    )
    if _sha256_json(normalized) != selection.get("selection_signature_sha256"):
        raise ValueError("selection signature does not match selected_packets")
    if selection.get("selected_packet_count") != len(normalized):
        raise ValueError("selected_packet_count does not match selected_packets")
    return tuple(normalized)


def _has_reference(
    text: str,
    *,
    kind: str,
    normalized_key: str,
    evidence_id: str,
) -> bool:
    return any(
        ref.join_eligible
        and ref.kind == kind
        and ref.normalized_key == normalized_key
        for ref in extract_explicit_references(text, evidence_id=evidence_id)
    )


def verify_publisher_relations(
    selection: dict,
    relations: list[dict],
) -> tuple[dict, ...]:
    selected = _selection_rows(selection)
    reference = selection.get("reference") or {}
    kind = reference.get("kind")
    normalized_key = reference.get("normalized_key")
    if not isinstance(kind, str) or not isinstance(normalized_key, str):
        raise ValueError("selection reference is incomplete")

    by_identity: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    for relation in relations:
        values = (
            relation.get("meeting_id"),
            relation.get("item_id"),
            relation.get("publish_id"),
        )
        if all(isinstance(value, int) for value in values):
            by_identity[values].append(relation)

    verified: list[dict] = []
    for row in selected:
        identity = (row["meeting_id"], row["item_id"], row["publish_id"])
        candidates: list[dict] = []
        for relation in by_identity.get(identity, []):
            source_uri = str(relation.get("source_uri") or "")
            if hashlib.sha256(source_uri.encode("utf-8")).hexdigest() != row[
                "source_uri_sha256"
            ]:
                continue
            if not _has_reference(
                str(relation.get("link_text") or ""),
                kind=kind,
                normalized_key=normalized_key,
                evidence_id=(
                    f"publisher-relation:{relation.get('parent_artifact_id') or 'unknown'}"
                ),
            ):
                continue
            candidates.append(relation)
        if len(candidates) != 1:
            raise ValueError(
                "frozen packet identity must match exactly one current publisher relation; "
                f"meeting_id={row['meeting_id']} matches={len(candidates)}"
            )
        verified.append(candidates[0])
    return tuple(verified)


def _resource_map(attachment_manifest: dict) -> dict[str, dict]:
    if attachment_manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"attachment manifest schema must be {MANIFEST_SCHEMA!r}")
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
    selected = _selection_rows(selection)
    relation_by_identity = {
        (
            int(relation["meeting_id"]),
            int(relation["item_id"]),
            int(relation["publish_id"]),
        ): relation
        for relation in verified_relations
    }
    resources_by_uri = _resource_map(attachment_manifest)
    resources: list[ManifestResource] = []
    for row in selected:
        identity = (row["meeting_id"], row["item_id"], row["publish_id"])
        relation = relation_by_identity.get(identity)
        if relation is None:
            raise ValueError(f"missing verified publisher relation: {identity}")
        source_uri = str(relation["source_uri"])
        raw = resources_by_uri.get(source_uri)
        if raw is None:
            raise ValueError(f"selected source missing from attachment manifest: {source_uri}")
        if raw.get("fetch_strategy") != FETCH_STRATEGY:
            raise ValueError(
                f"selected source must retain {FETCH_STRATEGY!r} transport strategy"
            )
        resources.append(
            ManifestResource(
                source_uri=source_uri,
                source_name=raw.get("source_name"),
                native_identifier=raw.get("native_identifier"),
                expected_media_type=raw.get("expected_media_type"),
                sequence_group=raw.get("sequence_group"),
                sequence_number=raw.get("sequence_number"),
                fetch_strategy=raw.get("fetch_strategy"),
            )
        )
    return SourceManifest(
        name="akron-t21-frozen-publisher-record-family-packets",
        resources=tuple(resources),
    )


def _meetings(discovery: dict) -> dict[int, dict]:
    raw = (discovery.get("canonical") or {}).get("meetings")
    if not isinstance(raw, list) or not raw:
        raise ValueError("attachment discovery must preserve canonical.meetings")
    meetings: dict[int, dict] = {}
    for meeting in raw:
        meeting_id = meeting.get("meeting_id")
        if not isinstance(meeting_id, int) or meeting_id <= 0:
            raise ValueError("structured meeting metadata has invalid meeting_id")
        if meeting_id in meetings and meetings[meeting_id] != meeting:
            raise ValueError(f"conflicting meeting metadata for {meeting_id}")
        meetings[meeting_id] = meeting
    return meetings


def _observation(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("observation time must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("observation time must include a timezone offset")
    return parsed


def _publisher_time_relation(meeting_time: str | None, observation: datetime) -> str:
    if not meeting_time:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(meeting_time)
    except ValueError:
        return "unparseable"
    if parsed.tzinfo is None:
        return "unparseable"
    return "after_observation" if parsed > observation else "at_or_before_observation"


def _page_sort(locator: str) -> tuple[int, str]:
    if locator.startswith("page:"):
        try:
            return int(locator.split(":", 1)[1]), locator
        except ValueError:
            pass
    return 10**9, locator


def _artifact_profile(store: ProoflineStore, artifact_id: str) -> dict:
    with store.connection() as connection:
        artifact = connection.execute(
            "SELECT sha256, byte_size, media_type FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if artifact is None:
            raise ValueError(f"unknown packet artifact: {artifact_id}")
        rows = connection.execute(
            """
            SELECT eu.locator, best.extracted_text, best.quality_score
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

    page_text = []
    low_quality = 0
    nonblank = 0
    for row in sorted(rows, key=lambda value: _page_sort(str(value["locator"]))):
        text = str(row["extracted_text"] or "")
        quality = row["quality_score"]
        nonblank += int(bool(text.strip()))
        low_quality += int(quality is None or float(quality) < 0.70)
        page_text.append(
            {
                "locator": str(row["locator"]),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return {
        "artifact_id": artifact_id,
        "sha256": str(artifact["sha256"]),
        "byte_size": int(artifact["byte_size"]),
        "media_type": artifact["media_type"],
        "page_count": len(rows),
        "nonblank_page_count": nonblank,
        "native_low_quality_page_count": low_quality,
        "native_text_signature_sha256": _sha256_json(page_text),
    }


def measure(
    *,
    state_dir: Path,
    selection: dict,
    relations: list[dict],
    attachment_manifest: dict,
    discovery: dict,
    observation_time: str,
) -> dict:
    observation = _observation(observation_time)
    selected = _selection_rows(selection)
    verified = verify_publisher_relations(selection, relations)
    manifest = selected_manifest(selection, verified, attachment_manifest)
    meetings = _meetings(discovery)

    relation_by_identity = {
        (
            int(relation["meeting_id"]),
            int(relation["item_id"]),
            int(relation["publish_id"]),
        ): relation
        for relation in verified
    }
    watch = OnBaseAttachmentWatcher(state_dir).run(manifest)
    if (watch.get("counts") or {}).get("unavailable"):
        raise RuntimeError(f"selected packet sync incomplete: {watch['counts']}")
    watched = {
        str(result["source_uri"]): result for result in watch.get("results") or []
    }
    store = ProoflineStore(state_dir / "proofline.db")

    packets: list[dict] = []
    for row in selected:
        identity = (row["meeting_id"], row["item_id"], row["publish_id"])
        relation = relation_by_identity[identity]
        source_uri = str(relation["source_uri"])
        result = watched.get(source_uri)
        if result is None or not result.get("artifact_id"):
            raise RuntimeError(f"selected packet has no successful artifact: {source_uri}")
        meeting = meetings.get(row["meeting_id"])
        if meeting is None:
            raise ValueError(f"missing meeting metadata: {row['meeting_id']}")
        packets.append(
            {
                "meeting": {
                    "meeting_id": row["meeting_id"],
                    "name": meeting.get("name"),
                    "meeting_type_name": meeting.get("meeting_type_name"),
                    "time": meeting.get("time"),
                    "agenda_unique_name": meeting.get("agenda_unique_name"),
                    "publisher_time_relation_to_observation": _publisher_time_relation(
                        meeting.get("time"), observation
                    ),
                },
                "publisher_relation": {
                    "relation_type": "supporting_document_of",
                    "parent_source_uri": relation["parent_source_uri"],
                    "parent_artifact_id": relation["parent_artifact_id"],
                    "parent_artifact_sha256": relation["parent_artifact_sha256"],
                    "item_id": int(relation["item_id"]),
                    "publish_id": int(relation["publish_id"]),
                    "link_text": relation["link_text"],
                    "source_uri": source_uri,
                    "source_uri_sha256": row["source_uri_sha256"],
                },
                "watch": {
                    "state": result.get("state"),
                    "checked_at": result.get("checked_at"),
                    "source_id": result.get("source_id"),
                },
                "artifact": _artifact_profile(store, str(result["artifact_id"])),
            }
        )

    packets.sort(
        key=lambda packet: (
            str(packet["meeting"].get("time") or ""),
            int(packet["meeting"]["meeting_id"]),
        )
    )
    for index, packet in enumerate(packets):
        if index == 0:
            packet["comparison_to_previous"] = None
            continue
        previous = packets[index - 1]
        current_artifact = packet["artifact"]
        previous_artifact = previous["artifact"]
        packet["comparison_to_previous"] = {
            "previous_meeting_id": previous["meeting"]["meeting_id"],
            "same_bronze_artifact": (
                current_artifact["artifact_id"] == previous_artifact["artifact_id"]
            ),
            "same_native_text_signature": (
                current_artifact["native_text_signature_sha256"]
                == previous_artifact["native_text_signature_sha256"]
            ),
            "byte_size_delta": current_artifact["byte_size"]
            - previous_artifact["byte_size"],
            "page_count_delta": current_artifact["page_count"]
            - previous_artifact["page_count"],
        }

    artifact_groups: dict[str, list[int]] = defaultdict(list)
    for packet in packets:
        artifact_groups[packet["artifact"]["artifact_id"]].append(
            int(packet["meeting"]["meeting_id"])
        )
    evolution_signature = _sha256_json(
        [
            {
                "meeting_id": packet["meeting"]["meeting_id"],
                "artifact_id": packet["artifact"]["artifact_id"],
                "native_text_signature_sha256": packet["artifact"][
                    "native_text_signature_sha256"
                ],
                "page_count": packet["artifact"]["page_count"],
            }
            for packet in packets
        ]
    )
    return {
        "schema": SCHEMA,
        "stage": "frozen_publisher_edge_expansion_and_byte_level_document_evolution",
        "observation_time": observation.isoformat(),
        "reference": selection["reference"],
        "selection": {
            "schema": selection["schema"],
            "basis": selection.get("basis"),
            "packet_source_count": len(selected),
            "selection_signature_sha256": selection["selection_signature_sha256"],
        },
        "counts": {
            "packet_source_count": len(packets),
            "unique_bronze_artifact_count": len(artifact_groups),
            "repeated_bronze_artifact_group_count": sum(
                int(len(meeting_ids) > 1)
                for meeting_ids in artifact_groups.values()
            ),
            "consecutive_bronze_change_count": sum(
                int(
                    packet["comparison_to_previous"] is not None
                    and not packet["comparison_to_previous"]["same_bronze_artifact"]
                )
                for packet in packets
            ),
            "publisher_times_after_observation_count": sum(
                int(
                    packet["meeting"]["publisher_time_relation_to_observation"]
                    == "after_observation"
                )
                for packet in packets
            ),
        },
        "artifact_groups": [
            {
                "artifact_id": artifact_id,
                "meeting_ids": meeting_ids,
                "meeting_count": len(meeting_ids),
            }
            for artifact_id, meeting_ids in sorted(artifact_groups.items())
        ],
        "packets": packets,
        "evolution_signature_sha256": evolution_signature,
        "authority_boundary": {
            "source_relation_created": False,
            "source_family_modified": False,
            "event_identity_assigned": False,
            "meeting_occurrence_asserted": False,
            "outcome_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "The frozen exact-reference candidate set is not an authoritative SourceFamily.",
            "Packet expansion uses only publisher relations matching frozen source identities.",
            "Publisher timestamps and agenda presence do not by themselves prove a meeting occurred.",
            "Byte or native-text changes do not establish semantic, legal, or policy changes.",
            "No approval, denial, causation, agreement, wrongdoing, detector, or lead semantics are assigned.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--relations", required=True)
    parser.add_argument("--attachment-manifest", required=True)
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--observation-time", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = measure(
        state_dir=Path(args.state_dir),
        selection=_load(args.selection),
        relations=_load(args.relations),
        attachment_manifest=_load(args.attachment_manifest),
        discovery=_load(args.discovery),
        observation_time=args.observation_time,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: result["counts"][key]
                for key in (
                    "packet_source_count",
                    "unique_bronze_artifact_count",
                    "consecutive_bronze_change_count",
                    "publisher_times_after_observation_count",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
