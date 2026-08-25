from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

AGENDA_SCHEMA = "proofline-akron-t21-agenda-status-sequence-receipt/v1"
RELATIONSHIP_SCHEMA = "proofline-akron-t21-evidence-relationship-receipt/v1"
MARKED_SCAN_SCHEMA = "proofline-akron-t21-terminal-record-candidate-scan-receipt/v1"
NARROW_SEARCH_SCHEMA = "proofline-akron-t21-public-access-eastwood-search-receipt/v1"
EXPANDED_SEARCH_SCHEMA = "proofline-akron-t21-passed-legislation-recall-expansion-receipt/v1"
CHRONOLOGY_SCHEMA = "proofline-evidence-chronology/v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _unknown(receipt: dict) -> bool:
    outcome = receipt.get("outcome", {})
    value = outcome.get("status", receipt.get("interpretation", {}).get("disposition", ""))
    return str(value).lower() == "unknown"


def _utc(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_sources(agenda: dict, relationships: dict, marked: dict, narrow: dict, expanded: dict) -> None:
    expected = (
        (agenda, AGENDA_SCHEMA, "agenda status"),
        (relationships, RELATIONSHIP_SCHEMA, "relationship"),
        (marked, MARKED_SCAN_SCHEMA, "marked-agenda scan"),
        (narrow, NARROW_SEARCH_SCHEMA, "narrow Passed Legislation search"),
        (expanded, EXPANDED_SEARCH_SCHEMA, "expanded Passed Legislation search"),
    )
    for receipt, schema, label in expected:
        if receipt.get("schema") != schema:
            raise ValueError(f"unexpected {label} receipt schema")
        if not _unknown(receipt):
            raise ValueError(f"{label} no longer has Unknown outcome; chronology-only authority is insufficient")

    if agenda.get("authority_boundary", {}).get("outcome_assigned") is not False:
        raise ValueError("agenda sequence exceeded procedural-only authority")
    if agenda.get("authority_boundary", {}).get("status_is_procedural_evidence_only") is not True:
        raise ValueError("agenda status must remain procedural evidence only")
    if relationships.get("authority_boundary", {}).get("terminal_semantics_authorized") is not False:
        raise ValueError("relationship graph unexpectedly authorizes terminal semantics")
    if marked.get("counts", {}).get("target_exact_title_match_count") != 0:
        raise ValueError("marked-agenda scan now contains a target candidate; chronology-only authority is insufficient")
    if narrow.get("candidate_population", {}).get("count") != 0:
        raise ValueError("narrow Passed Legislation search now contains a target candidate")
    screening = expanded.get("screening_observations", {})
    for key in ("street_number_and_location_group_count", "distinctive_use_tokens_group_count", "use_and_location_group_count"):
        if screening.get(key) != 0:
            raise ValueError("expanded Passed Legislation search now contains a strong target-identity candidate")
    for receipt, label in ((marked, "marked scan"), (narrow, "narrow search"), (expanded, "expanded search")):
        if receipt.get("authority_boundary", {}).get("terminal_outcome_assigned") is not False:
            raise ValueError(f"{label} exceeded non-terminal authority")
        if receipt.get("authority_boundary", {}).get("absence_treated_as_disposition") is not False:
            raise ValueError(f"{label} treats absence as disposition")


def _relationship_indexes(relationships: dict) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
    nodes_by_meeting: dict[int, list[str]] = {}
    node_meeting: dict[str, int] = {}
    for node in relationships.get("nodes", []):
        meeting_id = int(node["meeting_id"])
        nodes_by_meeting.setdefault(meeting_id, []).append(node["id"])
        node_meeting[node["id"]] = meeting_id

    rels_by_meeting: dict[int, set[str]] = {}
    for relation in relationships.get("relationships", []):
        mids = {node_meeting[relation[side]] for side in ("source", "target")}
        for meeting_id in mids:
            rels_by_meeting.setdefault(meeting_id, set()).add(relation["id"])
    return (
        {mid: sorted(ids) for mid, ids in nodes_by_meeting.items()},
        {mid: sorted(ids) for mid, ids in rels_by_meeting.items()},
    )


def _publisher_placements(agenda: dict, relationships: dict) -> tuple[list[dict], list[dict]]:
    nodes_by_meeting, rels_by_meeting = _relationship_indexes(relationships)
    observed: list[dict] = []
    future: list[dict] = []
    for row in agenda.get("sequence_rows", []):
        meeting_id = int(row[0])
        placement = {
            "meeting_id": meeting_id,
            "publisher_time": row[1],
            "publisher_time_relation_to_observation": row[2],
            "normalized_status": row[7],
            "procedural_category": row[8],
            "target_evidence_node_ids": nodes_by_meeting.get(meeting_id, []),
            "evidence_relationship_ids": rels_by_meeting.get(meeting_id, []),
            "target_evidence_present": meeting_id in nodes_by_meeting,
            "publisher_time_asserts_event_occurrence": False,
        }
        if row[2] == "after_observation":
            future.append(placement)
        elif row[2] == "at_or_before_observation":
            observed.append(placement)
        else:
            raise ValueError(f"unexpected publisher time relation: {row[2]}")
    return observed, future


def _search_checkpoints(marked: dict, narrow: dict, expanded: dict) -> list[dict]:
    checkpoints = [
        {
            "id": "search-checkpoint:marked-agenda-numbered-vote-scan",
            "observed_at_utc": _utc(marked["observation_time"]),
            "surface": "marked_agendas",
            "bounded_population": {"marked_agenda_count": marked["counts"]["marked_agenda_count"], "numbered_vote_candidate_count": marked["counts"]["numbered_vote_candidate_count"]},
            "target_result": {"exact_title_match_count": 0},
            "authority": "bounded_nonfinding_only_not_disposition",
        },
        {
            "id": "search-checkpoint:passed-legislation-narrow",
            "observed_at_utc": _utc(narrow["canonical_measurement"]["observed_at_utc"]),
            "surface": "passed_legislation",
            "bounded_population": {"request_count": narrow["plan"]["eastwood_request_count"]},
            "target_result": {"candidate_count": narrow["candidate_population"]["count"]},
            "authority": "bounded_nonfinding_only_not_disposition",
        },
        {
            "id": "search-checkpoint:passed-legislation-expanded",
            "observed_at_utc": _utc(expanded["canonical_measurement"]["observed_at_utc"]),
            "surface": "passed_legislation",
            "bounded_population": {"request_count": expanded["counts"]["request_count"], "stable_candidate_group_count": expanded["counts"]["stable_candidate_group_count"], "plan_screened_group_count": expanded["counts"]["target_screened_candidate_group_count"]},
            "target_result": {
                "street_number_and_location_group_count": expanded["screening_observations"]["street_number_and_location_group_count"],
                "distinctive_use_tokens_group_count": expanded["screening_observations"]["distinctive_use_tokens_group_count"],
                "use_and_location_group_count": expanded["screening_observations"]["use_and_location_group_count"],
                "broad_action_and_location_group_count": expanded["screening_observations"]["action_and_location_group_count"],
                "broad_matches_are_target_identity": False,
            },
            "authority": "bounded_screening_observation_only_not_disposition",
        },
    ]
    return sorted(checkpoints, key=lambda row: (row["observed_at_utc"], row["id"]))


def build_chronology(agenda: dict, relationships: dict, marked: dict, narrow: dict, expanded: dict) -> dict:
    validate_sources(agenda, relationships, marked, narrow, expanded)
    observed, future = _publisher_placements(agenda, relationships)
    checkpoints = _search_checkpoints(marked, narrow, expanded)
    chronology = {
        "schema": CHRONOLOGY_SCHEMA,
        "agenda_observation_time": agenda["observation_time"],
        "publisher_placements": observed,
        "future_publisher_metadata": future,
        "search_checkpoints": checkpoints,
        "counts": {
            "observed_publisher_placement_count": len(observed),
            "future_publisher_metadata_count": len(future),
            "observed_referred_count": sum(row["normalized_status"] == "referred" for row in observed),
            "observed_time_count": sum(row["normalized_status"] == "time" for row in observed),
            "placements_with_target_evidence_count": sum(row["target_evidence_present"] for row in observed),
            "target_evidence_node_count": relationships["counts"]["evidence_node_count"],
            "evidence_relationship_count": relationships["counts"]["relationship_count"],
            "search_checkpoint_count": len(checkpoints),
        },
        "authority_boundary": {
            "chronology_orders_evidence_only": True,
            "publisher_time_is_not_event_occurrence": True,
            "future_publisher_metadata_is_not_future_event_proof": True,
            "referred_is_not_terminal_disposition": True,
            "time_is_not_terminal_disposition": True,
            "bounded_nonfinding_is_not_legislative_event": True,
            "bounded_nonfinding_is_not_disposition": True,
            "relationship_structure_is_not_causality": True,
            "terminal_outcome_assigned": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "The chronology orders frozen procedural placements, target-local provenance, and bounded search observations without converting any of them into terminal legislative disposition.",
        },
    }
    chronology["publisher_placement_population_signature_sha256"] = sha256_json(observed)
    chronology["future_metadata_population_signature_sha256"] = sha256_json(future)
    chronology["search_checkpoint_population_signature_sha256"] = sha256_json(checkpoints)
    chronology["chronology_signature_sha256"] = sha256_json({
        "publisher_placements": observed,
        "future_publisher_metadata": future,
        "search_checkpoints": checkpoints,
        "authority_boundary": chronology["authority_boundary"],
        "outcome": chronology["outcome"],
    })
    return chronology
