from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

COUNCIL_SCHEMA = "proofline-akron-t21-council-minutes-content-audit-receipt/v1"
COMMITTEE_SCHEMA = "proofline-akron-t21-committee-minutes-content-audit-receipt/v1"
DATE_SCHEMA = "proofline-akron-t21-committee-minutes-date-search-receipt/v1"
GRAPH_SCHEMA = "proofline-evidence-relationship-graph/v1"

STRONG_TARGET_ANCHORS = {
    "exact_address",
    "distinctive_title_phrase",
    "training_eastwood_cooccurrence",
}

COUNCIL_PHASES = {
    "referred_to_committee": "referral",
    "public_hearing_declared": "public_hearing",
    "public_hearing_closed": "public_hearing",
    "substitute_read": "amendment",
    "committee_favorable_poll": "committee_recommendation_poll",
    "committee_time_poll": "committee_time",
}

COMMITTEE_PHASES = {
    "referred": "referral",
    "public_hearing": "public_hearing",
    "hearing_closed": "public_hearing",
    "recommended_approval": "planning_recommendation",
    "recommended_denial": "planning_recommendation",
    "held": "discussion",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _unknown(receipt: dict) -> bool:
    return str(receipt.get("outcome", {}).get("status", "")).lower() == "unknown"


def validate_sources(council: dict, committee: dict, date_receipt: dict) -> None:
    if council.get("schema") != COUNCIL_SCHEMA:
        raise ValueError("unexpected Council content-audit receipt schema")
    if committee.get("schema") != COMMITTEE_SCHEMA:
        raise ValueError("unexpected Committee content-audit receipt schema")
    if date_receipt.get("schema") != DATE_SCHEMA:
        raise ValueError("unexpected Committee date-search receipt schema")
    if council.get("terminal_candidate_blocks") != []:
        raise ValueError("Council receipt contains terminal candidates; relationship-only authority is insufficient")
    if committee.get("terminal_candidate_blocks") != []:
        raise ValueError("Committee receipt contains terminal candidates; relationship-only authority is insufficient")
    if not _unknown(council) or not _unknown(committee):
        raise ValueError("relationship layer requires both upstream outcomes to remain Unknown")
    if council.get("authority_boundary", {}).get("terminal_outcome_assigned") is not False:
        raise ValueError("Council receipt exceeded relationship-layer authority")
    if committee.get("authority_boundary", {}).get("terminal_outcome_assigned") is not False:
        raise ValueError("Committee receipt exceeded relationship-layer authority")


def _date_map(date_receipt: dict) -> dict[int, str]:
    rows = date_receipt.get("eastwood_searches", [])
    result: dict[int, str] = {}
    for row in rows:
        meeting_id = int(row["meeting_id"])
        if meeting_id in result:
            raise ValueError(f"duplicate date mapping for meeting {meeting_id}")
        result[meeting_id] = row["meeting_date"]
    if len(result) != 22:
        raise ValueError("frozen Committee date receipt must contain exactly 22 Eastwood dates")
    return result


def _node_id(surface: str, block: dict) -> str:
    locality = block.get("block_index", block.get("paragraph_index"))
    raw = {
        "surface": surface,
        "meeting_id": block["meeting_id"],
        "document_sha256": block["document_sha256"],
        "page": block["page"],
        "locality": locality,
        "evidence_sha256": block["block_text_sha256"],
    }
    return f"evidence:{surface}:{sha256_json(raw)}"


def _nodes(council: dict, committee: dict, dates: dict[int, str]) -> list[dict]:
    result: list[dict] = []
    for surface, blocks in (
        ("council_minutes", council["target_record_block_receipts"]),
        ("committee_minutes", committee["target_block_receipts"]),
    ):
        for block in blocks:
            meeting_id = int(block["meeting_id"])
            result.append(
                {
                    "id": _node_id(surface, block),
                    "surface": surface,
                    "meeting_id": meeting_id,
                    "meeting_date": dates.get(meeting_id),
                    "document_sha256": block["document_sha256"],
                    "page": block["page"],
                    "locality_index": block.get("block_index", block.get("paragraph_index")),
                    "anchor_hits": sorted(block["anchor_hits"]),
                    "procedural_phrase_hits": sorted(block["procedural_phrase_hits"]),
                    "evidence_sha256": block["block_text_sha256"],
                }
            )
    return sorted(result, key=lambda row: (row["meeting_id"], row["surface"], row["document_sha256"], row["page"], row["locality_index"]))


def _relation_id(kind: str, source_id: str, target_id: str, detail: dict) -> str:
    return f"relationship:{kind}:{sha256_json({'source': source_id, 'target': target_id, 'detail': detail})}"


def _phase_set(node: dict) -> set[str]:
    mapping = COUNCIL_PHASES if node["surface"] == "council_minutes" else COMMITTEE_PHASES
    return {mapping[hit] for hit in node["procedural_phrase_hits"] if hit in mapping}


def _same_target_relations(nodes: list[dict]) -> tuple[list[dict], list[tuple[dict, dict]]]:
    council = [node for node in nodes if node["surface"] == "council_minutes"]
    committee = [node for node in nodes if node["surface"] == "committee_minutes"]
    relations: list[dict] = []
    pairs: list[tuple[dict, dict]] = []
    for cmt in committee:
        for ccl in council:
            if cmt["meeting_id"] != ccl["meeting_id"]:
                continue
            shared = sorted(
                STRONG_TARGET_ANCHORS
                & set(cmt["anchor_hits"])
                & set(ccl["anchor_hits"])
            )
            if len(shared) < 2:
                continue
            detail = {
                "meeting_id": cmt["meeting_id"],
                "meeting_date": cmt["meeting_date"],
                "shared_strong_anchor_ids": shared,
                "authority": "same_target_same_meeting_corroboration_only",
            }
            relations.append(
                {
                    "id": _relation_id("same_target_same_meeting", cmt["id"], ccl["id"], detail),
                    "type": "same_target_same_meeting",
                    "source": cmt["id"],
                    "target": ccl["id"],
                    "detail": detail,
                }
            )
            pairs.append((cmt, ccl))
    return relations, pairs


def _phase_relations(pairs: list[tuple[dict, dict]]) -> list[dict]:
    result: list[dict] = []
    for committee, council in pairs:
        shared_phases = sorted(_phase_set(committee) & _phase_set(council))
        if not shared_phases:
            continue
        detail = {
            "meeting_id": committee["meeting_id"],
            "meeting_date": committee["meeting_date"],
            "shared_procedural_phases": shared_phases,
            "authority": "independent_procedural_corroboration_only",
        }
        result.append(
            {
                "id": _relation_id("procedural_phase_corroboration", committee["id"], council["id"], detail),
                "type": "procedural_phase_corroboration",
                "source": committee["id"],
                "target": council["id"],
                "detail": detail,
            }
        )
    return result


def _scheduled_date(committee: dict) -> str:
    text = committee.get("observations", {}).get("february_23", "")
    match = re.search(r"Public Hearing on ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if not match:
        raise ValueError("frozen Committee observation no longer contains explicit Public Hearing date")
    return datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()


def _scheduling_relation(nodes: list[dict], committee: dict, dates: dict[int, str]) -> dict:
    scheduled = _scheduled_date(committee)
    meeting_ids = sorted(mid for mid, date in dates.items() if date == scheduled)
    if meeting_ids != [671]:
        raise ValueError("explicit March 9 hearing date no longer resolves uniquely to frozen meeting 671")
    source_candidates = [n for n in nodes if n["surface"] == "committee_minutes" and n["meeting_id"] == 669]
    target_candidates = [n for n in nodes if n["surface"] == "committee_minutes" and n["meeting_id"] == 671]
    if len(source_candidates) != 1 or len(target_candidates) != 1:
        raise ValueError("explicit scheduling relationship requires one Committee evidence block at meetings 669 and 671")
    source, target = source_candidates[0], target_candidates[0]
    detail = {
        "scheduled_event": "public_hearing",
        "scheduled_date": scheduled,
        "resolved_meeting_id": 671,
        "resolution_source": "frozen_committee_minutes_date_search_receipt",
        "authority": "explicit_schedule_reference_only_not_causality_or_disposition",
    }
    return {
        "id": _relation_id("explicit_scheduling", source["id"], target["id"], detail),
        "type": "explicit_scheduling",
        "source": source["id"],
        "target": target["id"],
        "detail": detail,
    }


def build_relationship_graph(council: dict, committee: dict, date_receipt: dict) -> dict:
    validate_sources(council, committee, date_receipt)
    dates = _date_map(date_receipt)
    nodes = _nodes(council, committee, dates)
    same_target, pairs = _same_target_relations(nodes)
    phase = _phase_relations(pairs)
    scheduling = _scheduling_relation(nodes, committee, dates)
    relationships = sorted(same_target + phase + [scheduling], key=lambda row: (row["type"], row["source"], row["target"]))

    paired_ids = {relation[side] for relation in same_target for side in ("source", "target")}
    unpaired = sorted(node["id"] for node in nodes if node["id"] not in paired_ids)
    counts_by_type = {
        kind: sum(row["type"] == kind for row in relationships)
        for kind in ("same_target_same_meeting", "procedural_phase_corroboration", "explicit_scheduling")
    }
    graph = {
        "schema": GRAPH_SCHEMA,
        "nodes": nodes,
        "relationships": relationships,
        "unpaired_target_evidence_node_ids": unpaired,
        "counts": {
            "evidence_node_count": len(nodes),
            "council_evidence_node_count": sum(n["surface"] == "council_minutes" for n in nodes),
            "committee_evidence_node_count": sum(n["surface"] == "committee_minutes" for n in nodes),
            "relationship_count": len(relationships),
            **{f"{key}_count": value for key, value in counts_by_type.items()},
            "unpaired_target_evidence_node_count": len(unpaired),
        },
        "authority_boundary": {
            "relationships_are_provenance_only": True,
            "same_date_is_not_causality": True,
            "committee_recommendation_is_not_final_disposition": True,
            "time_language_is_not_terminal_disposition": True,
            "absence_is_not_disposition": True,
            "terminal_semantics_authorized": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "outcome": {
            "status": "unknown",
            "reason": "Cross-source relationships corroborate target identity and non-terminal procedural chronology only; they do not establish final legislative disposition.",
        },
    }
    graph["node_population_signature_sha256"] = sha256_json(nodes)
    graph["relationship_population_signature_sha256"] = sha256_json(relationships)
    return graph
