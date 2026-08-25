#!/usr/bin/env python3
"""Measure explicit publisher agenda-status chronology for the frozen T21 case.

The population is the already-frozen 24 meeting/item identities for
``PC-2025-80-CU``. This stage rebuilds current publisher agenda trees, proves each
selected item by exact planning-case reference, and records only structurally
associated procedural status labels. It does not assign meeting occurrence or a
terminal outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from proofline.explicit_references import extract_explicit_references
from proofline.hashing import source_id_from_uri
from proofline.onbase import (
    OnBaseAgendaDiscoverer,
    load_onbase_agenda_plan,
    onbase_agenda_tree_uri,
)
from proofline.onbase_agenda_status import extract_onbase_agenda_status_assignments
from proofline.storage import ProoflineStore
from proofline.watch_storage import WatcherStore

SCHEMA = "proofline-akron-t21-agenda-status-sequence/v1"
SELECTION_SCHEMA = "proofline-akron-t21-record-family-packet-selection/v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
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
        values = (row.get("meeting_id"), row.get("item_id"), row.get("publish_id"))
        if not all(isinstance(value, int) and value > 0 for value in values):
            raise ValueError("selected meeting/item/publish IDs must be positive integers")
        source_hash = row.get("source_uri_sha256")
        if (
            not isinstance(source_hash, str)
            or len(source_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in source_hash)
        ):
            raise ValueError("source_uri_sha256 must be lowercase SHA-256")
        identity = (int(values[0]), int(values[1]), int(values[2]))
        if identity in seen:
            raise ValueError(f"duplicate selected identity: {identity}")
        seen.add(identity)
        normalized.append(
            {
                "meeting_id": identity[0],
                "item_id": identity[1],
                "publish_id": identity[2],
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


def _observation(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
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


def _latest_source_artifact(state_dir: Path, source_uri: str) -> tuple[str, str, str]:
    db_path = state_dir / "proofline.db"
    source_id = source_id_from_uri(source_uri)
    artifact_id = WatcherStore(db_path).latest_successful_artifact(source_id)
    if artifact_id is None:
        raise ValueError(f"no successful artifact for agenda-tree source: {source_uri}")
    store = ProoflineStore(db_path)
    with store.connection() as connection:
        row = connection.execute(
            "SELECT sha256, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"agenda-tree artifact missing from store: {artifact_id}")
    stored_path = str(row["stored_path"])
    html = (state_dir / stored_path).read_text(encoding="utf-8", errors="replace")
    return artifact_id, str(row["sha256"]), html


def _has_target_reference(text: str, *, evidence_id: str, reference: dict) -> bool:
    return any(
        item.join_eligible
        and item.kind == reference.get("kind")
        and item.normalized_key == reference.get("normalized_key")
        for item in extract_explicit_references(text, evidence_id=evidence_id)
    )


def measure(
    *,
    state_dir: Path,
    plan_path: Path,
    selection: dict,
    observation_time: str,
) -> dict:
    selected = _selection_rows(selection)
    reference = selection.get("reference") or {}
    if reference.get("kind") != "planning_case" or not isinstance(
        reference.get("normalized_key"), str
    ):
        raise ValueError("selection must contain the frozen planning-case reference")
    observation = _observation(observation_time)

    plan = load_onbase_agenda_plan(plan_path)
    agenda = OnBaseAgendaDiscoverer(state_dir)
    discovery = agenda.run(plan)
    meeting_by_id = {meeting.meeting_id: meeting for meeting in discovery.meetings}

    sequence: list[dict] = []
    for row in selected:
        meeting_id = row["meeting_id"]
        item_id = row["item_id"]
        meeting = meeting_by_id.get(meeting_id)
        if meeting is None:
            raise ValueError(f"selected meeting absent from current publisher discovery: {meeting_id}")

        tree_uri = onbase_agenda_tree_uri(plan, meeting_id)
        artifact_id, artifact_sha256, html = _latest_source_artifact(state_dir, tree_uri)
        assignments = extract_onbase_agenda_status_assignments(html, meeting_id=meeting_id)
        targets = [item for item in assignments if item.item_id == item_id]
        if len(targets) != 1:
            raise ValueError(
                "selected agenda item must have exactly one structural assignment; "
                f"meeting_id={meeting_id} item_id={item_id} matches={len(targets)}"
            )
        target = targets[0]
        evidence_id = f"onbase-agenda-tree:{meeting_id}:item:{item_id}"
        if not _has_target_reference(target.item_text, evidence_id=evidence_id, reference=reference):
            raise ValueError(
                "selected agenda item no longer carries the frozen exact planning-case reference; "
                f"meeting_id={meeting_id} item_id={item_id}"
            )

        status = target.status.to_dict() if target.status is not None else None
        sequence.append(
            {
                "meeting": {
                    "meeting_id": meeting_id,
                    "name": meeting.name,
                    "meeting_type_name": meeting.meeting_type_name,
                    "time": meeting.time,
                    "publisher_time_relation_to_observation": _publisher_time_relation(
                        meeting.time, observation
                    ),
                },
                "selected_item": {
                    "item_id": item_id,
                    "publish_id": row["publish_id"],
                    "supporting_document_source_uri_sha256": row["source_uri_sha256"],
                    "item_text_sha256": hashlib.sha256(
                        target.item_text.encode("utf-8")
                    ).hexdigest(),
                    "item_block_index": target.item_block_index,
                },
                "agenda_tree": {
                    "source_uri_sha256": hashlib.sha256(tree_uri.encode("utf-8")).hexdigest(),
                    "artifact_id": artifact_id,
                    "artifact_sha256": artifact_sha256,
                },
                "status_block_index": target.status_block_index,
                "status": status,
            }
        )

    sequence.sort(
        key=lambda row: (
            str(row["meeting"].get("time") or ""),
            int(row["meeting"]["meeting_id"]),
        )
    )
    signature_rows = [
        {
            "meeting_id": row["meeting"]["meeting_id"],
            "item_id": row["selected_item"]["item_id"],
            "agenda_tree_artifact_sha256": row["agenda_tree"]["artifact_sha256"],
            "normalized_status": (
                row["status"]["normalized_status"] if row["status"] is not None else None
            ),
            "status_block_index": row["status_block_index"],
        }
        for row in sequence
    ]
    status_counts: dict[str, int] = {}
    for row in sequence:
        key = row["status"]["normalized_status"] if row["status"] else "unresolved"
        status_counts[key] = status_counts.get(key, 0) + 1

    return {
        "schema": SCHEMA,
        "stage": "frozen_exact_reference_population_publisher_agenda_status_measurement",
        "observation_time": observation.isoformat(),
        "reference": reference,
        "selection": {
            "selected_item_count": len(selected),
            "selection_signature_sha256": selection["selection_signature_sha256"],
        },
        "publisher_discovery": {
            "agenda_item_manifest_sha256": discovery.discovery.manifest_sha256,
            "meeting_count": len(discovery.meetings),
            "agenda_tree_count": discovery.agenda_tree_count,
            "agenda_item_count": discovery.agenda_item_count,
        },
        "counts": {
            "selected_item_count": len(sequence),
            "resolved_status_count": sum(int(row["status"] is not None) for row in sequence),
            "unresolved_status_count": sum(int(row["status"] is None) for row in sequence),
            "publisher_times_after_observation_count": sum(
                int(
                    row["meeting"]["publisher_time_relation_to_observation"]
                    == "after_observation"
                )
                for row in sequence
            ),
            "by_normalized_status": dict(sorted(status_counts.items())),
        },
        "sequence": sequence,
        "sequence_signature_sha256": _sha256_json(signature_rows),
        "authority_boundary": {
            "status_is_procedural_evidence_only": True,
            "meeting_occurrence_asserted": False,
            "hearing_occurrence_inferred_from_status": False,
            "outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "Agenda status is assigned only through publisher outer-table structure, not text proximity.",
            "A TIME or referral/hearing status is procedural evidence and not a terminal disposition.",
            "A publisher agenda timestamp after the observation boundary is not evidence that the future meeting occurred.",
            "Disappearance from a later agenda is not interpreted as approval, denial, withdrawal, or other outcome.",
            "No causal explanation, detector authority, anomaly, wrongdoing, or lead semantics are assigned.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--observation-time", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = measure(
        state_dir=Path(args.state_dir),
        plan_path=Path(args.plan),
        selection=_load(args.selection),
        observation_time=args.observation_time,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
