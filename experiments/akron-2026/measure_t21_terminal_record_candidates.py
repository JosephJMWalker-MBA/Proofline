#!/usr/bin/env python3
"""Measure numbered-vote terminal-record candidates for the frozen Eastwood target.

This experiment scans only publisher-declared Akron marked-agenda PDFs from the
tracked ordinance's introduction date through a frozen observation boundary.
Candidates are extracted with ``proofline-numbered-vote-record-candidate/v1``.
An Eastwood relationship is assigned only when the numbered ordinance body is
an exact whitespace-normalized match to the frozen target title.

No candidate, vote count, exact title match, or absence is interpreted as a
terminal disposition in this stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

import fitz

from proofline.onbase import OnBaseAgendaDiscoverer, OnBaseAgendaPlan, load_onbase_agenda_plan
from proofline.storage import ProoflineStore
from proofline.terminal_record_candidates import (
    NumberedVoteRecordCandidate,
    extract_numbered_vote_record_candidates,
)
from proofline.watcher import CorpusWatcher, ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-terminal-record-candidate-measurement/v1"
TARGET_SCHEMA = "proofline-akron-t21-terminal-record-target/v1"

# Keep this prefix grammar coextensive with the frozen candidate primitive:
# numbered instrument + four-digit year boundary. Any punctuation after the
# identifier remains part of the legislative body and therefore cannot create a
# false exact-title match.
_PREFIX_RE = re.compile(
    r"^(?P<kind>ORDINANCE|RESOLUTION)\s+NO\.?\s+\d+-\d{4}\b\s*",
    re.IGNORECASE,
)
_VOTE_SUFFIX_RE = re.compile(r"\s+Vote\s*:\s*\d+\s*-\s*\d+\s*$", re.IGNORECASE)


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(serialized)


def _parse_observation(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("observation time must include a timezone offset")
    return parsed


def _parse_meeting_time(value: str | None) -> datetime:
    if not value:
        raise ValueError("publisher meeting time is required for bounded scan")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"publisher meeting time must include a timezone offset: {value!r}")
    return parsed


def _instance_root(plan: OnBaseAgendaPlan) -> str:
    parsed = urlsplit(plan.source_uri)
    path = parsed.path.rstrip("/")
    if not path.casefold().endswith("/meetings"):
        raise ValueError("OnBase source URI must end in /Meetings")
    root_path = path[: -len("/Meetings")] + "/"
    return urlunsplit((parsed.scheme, parsed.netloc, root_path, "", ""))


def agenda_pdf_uri(plan: OnBaseAgendaPlan, *, meeting_id: int, agenda_unique_name: str) -> str:
    """Derive the marked-agenda PDF from publisher-declared meeting metadata.

    Akron currently serves marked-agenda bytes through ``DownloadFileBytes``.
    The path uses only the publisher-declared ``AgendaUniqueName`` plus the
    publisher meeting ID. No numeric ID sweep or guessed filename is used.
    """
    if meeting_id <= 0:
        raise ValueError("meeting_id must be positive")
    if not agenda_unique_name.strip():
        raise ValueError("agenda_unique_name must be non-empty")
    root = _instance_root(plan)
    path = "Documents/DownloadFileBytes/" + quote(agenda_unique_name, safe="") + ".pdf"
    query = urlencode({"documentType": "1", "meetingId": str(meeting_id)})
    return urljoin(root, path) + "?" + query


def candidate_legislative_body(candidate: NumberedVoteRecordCandidate) -> str:
    """Return a candidate's title/body without numbered prefix or vote suffix."""
    normalized = _normalize(candidate.normalized_record_text)
    without_prefix = _PREFIX_RE.sub("", normalized, count=1)
    if without_prefix == normalized:
        raise ValueError("candidate did not begin with expected numbered-instrument prefix")
    without_vote = _VOTE_SUFFIX_RE.sub("", without_prefix, count=1)
    if without_vote == without_prefix:
        raise ValueError("candidate did not end with expected exact two-part vote")
    return without_vote.strip()


def candidate_matches_target(candidate: NumberedVoteRecordCandidate, target: dict) -> bool:
    """Exact relationship test; never an outcome test."""
    if candidate.instrument_type != "ordinance":
        return False
    target_title = target.get("ordinance_title")
    if not isinstance(target_title, str) or not target_title.strip():
        raise ValueError("target ordinance_title must be non-empty")
    expected = _normalize(target_title)
    if _sha256_text(expected) != target.get("ordinance_title_sha256"):
        raise ValueError("target ordinance title hash does not match target text")
    return candidate_legislative_body(candidate).casefold() == expected.casefold()


def _artifact_record(state_dir: Path, artifact_id: str) -> tuple[str, Path]:
    store = ProoflineStore(state_dir / "proofline.db")
    with store.connection() as connection:
        row = connection.execute(
            "SELECT sha256, stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"artifact missing from store: {artifact_id}")
    path = state_dir / str(row["stored_path"])
    if not path.is_file():
        raise ValueError(f"artifact bytes missing from store: {artifact_id}")
    return str(row["sha256"]), path


def _pdf_text(path: Path) -> tuple[str, int]:
    with fitz.open(path) as document:
        pages = [page.get_text("text") for page in document]
        return "\n".join(pages), len(document)


def _validate_target(target: dict) -> date:
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError(f"target schema must be {TARGET_SCHEMA!r}")
    planning_case = target.get("planning_case") or {}
    if planning_case.get("kind") != "planning_case" or planning_case.get("normalized_key") != "PC-2025-80-CU":
        raise ValueError("target planning case must remain PC-2025-80-CU")
    title = target.get("ordinance_title")
    if not isinstance(title, str) or _sha256_text(_normalize(title)) != target.get("ordinance_title_sha256"):
        raise ValueError("target title/hash boundary failed")
    introduced = target.get("introduced_on_or_after")
    if not isinstance(introduced, str):
        raise ValueError("target introduced_on_or_after must be an ISO date")
    return date.fromisoformat(introduced)


def measure(
    *,
    state_dir: Path,
    plan_path: Path,
    target: dict,
    observation_time: str,
) -> dict:
    introduced = _validate_target(target)
    observation = _parse_observation(observation_time)
    plan = load_onbase_agenda_plan(plan_path)

    discovery = OnBaseAgendaDiscoverer(state_dir).run(plan)
    eligible = []
    excluded_before = 0
    excluded_after = 0
    for meeting in discovery.meetings:
        meeting_time = _parse_meeting_time(meeting.time)
        if meeting_time.date() < introduced:
            excluded_before += 1
            continue
        if meeting_time > observation:
            excluded_after += 1
            continue
        if not meeting.agenda_unique_name:
            raise ValueError(
                "eligible publisher meeting lacks AgendaUniqueName; exhaustive marked-agenda scan cannot proceed: "
                f"meeting_id={meeting.meeting_id}"
            )
        eligible.append((meeting, meeting_time))

    if not eligible:
        raise ValueError("no publisher meetings were eligible for terminal-record candidate scan")

    resources = []
    meeting_by_uri = {}
    for meeting, meeting_time in eligible:
        uri = agenda_pdf_uri(
            plan,
            meeting_id=meeting.meeting_id,
            agenda_unique_name=meeting.agenda_unique_name or "",
        )
        meeting_by_uri[uri] = (meeting, meeting_time)
        resources.append(
            ManifestResource(
                source_uri=uri,
                source_name=f"Akron marked agenda — {meeting.name} — {meeting.time}",
                native_identifier=f"akron-marked-agenda-{meeting.meeting_id}",
                expected_media_type="application/pdf",
            )
        )

    watcher = CorpusWatcher(state_dir)
    watch = watcher.run(
        SourceManifest(name="akron-t21-terminal-record-marked-agendas", resources=tuple(resources))
    )
    unavailable = [row for row in watch["results"] if not row.get("artifact_id")]
    if unavailable:
        raise ValueError(
            "marked-agenda scan requires complete eligible publisher coverage; unavailable meeting PDFs: "
            + ", ".join(str(meeting_by_uri[row["source_uri"]][0].meeting_id) for row in unavailable)
        )

    source_rows = []
    candidate_rows = []
    target_matches = []
    for watch_row in watch["results"]:
        uri = watch_row["source_uri"]
        meeting, meeting_time = meeting_by_uri[uri]
        artifact_id = str(watch_row["artifact_id"])
        artifact_sha256, path = _artifact_record(state_dir, artifact_id)
        text, page_count = _pdf_text(path)
        evidence_id = f"akron-marked-agenda:{meeting.meeting_id}:{artifact_sha256}"
        candidates = extract_numbered_vote_record_candidates(text, evidence_id=evidence_id)

        source_rows.append(
            {
                "meeting_id": meeting.meeting_id,
                "meeting_name": meeting.name,
                "meeting_time": meeting_time.isoformat(),
                "agenda_unique_name_sha256": _sha256_text(meeting.agenda_unique_name or ""),
                "source_uri_sha256": _sha256_text(uri),
                "artifact_id": artifact_id,
                "artifact_sha256": artifact_sha256,
                "page_count": page_count,
                "candidate_count": len(candidates),
            }
        )

        for candidate in candidates:
            target_match = candidate_matches_target(candidate, target)
            row = {
                "meeting_id": meeting.meeting_id,
                "meeting_time": meeting_time.isoformat(),
                "artifact_sha256": artifact_sha256,
                "candidate_id": candidate.candidate_id,
                "evidence_id": candidate.evidence_id,
                "instrument_type": candidate.instrument_type,
                "instrument_number": candidate.instrument_number,
                "instrument_year": candidate.instrument_year,
                "vote_ayes": candidate.vote_ayes,
                "vote_nays": candidate.vote_nays,
                "normalized_record_text": candidate.normalized_record_text,
                "normalized_record_text_sha256": _sha256_text(candidate.normalized_record_text),
                "target_exact_title_match": target_match,
                "terminal_outcome_assigned": candidate.terminal_outcome_assigned,
            }
            candidate_rows.append(row)
            if target_match:
                target_matches.append(row)

    source_rows.sort(key=lambda row: (row["meeting_time"], row["meeting_id"]))
    candidate_rows.sort(
        key=lambda row: (
            row["meeting_time"],
            row["meeting_id"],
            row["instrument_year"],
            row["instrument_number"],
            row["candidate_id"],
        )
    )
    target_matches.sort(
        key=lambda row: (row["meeting_time"], row["meeting_id"], row["candidate_id"])
    )

    candidate_signature_rows = [
        {
            "meeting_id": row["meeting_id"],
            "artifact_sha256": row["artifact_sha256"],
            "candidate_id": row["candidate_id"],
            "target_exact_title_match": row["target_exact_title_match"],
        }
        for row in candidate_rows
    ]
    source_signature_rows = [
        {
            "meeting_id": row["meeting_id"],
            "artifact_sha256": row["artifact_sha256"],
            "page_count": row["page_count"],
            "candidate_count": row["candidate_count"],
        }
        for row in source_rows
    ]

    return {
        "schema": SCHEMA,
        "stage": "bounded_marked_agenda_numbered_vote_candidate_scan",
        "observation_time": observation.isoformat(),
        "target": {
            "planning_case": target["planning_case"],
            "ordinance_title_sha256": target["ordinance_title_sha256"],
            "introduced_on_or_after": target["introduced_on_or_after"],
        },
        "publisher_discovery": {
            "agenda_item_manifest_sha256": discovery.discovery.manifest_sha256,
            "meeting_count": len(discovery.meetings),
            "agenda_tree_count": discovery.agenda_tree_count,
            "agenda_item_count": discovery.agenda_item_count,
        },
        "scan_window": {
            "eligible_marked_agenda_count": len(source_rows),
            "meetings_before_target_introduction_excluded": excluded_before,
            "publisher_meetings_after_observation_excluded": excluded_after,
        },
        "counts": {
            "marked_agenda_count": len(source_rows),
            "numbered_vote_candidate_count": len(candidate_rows),
            "target_exact_title_match_count": len(target_matches),
            "terminal_outcomes_assigned": 0,
        },
        "sources": source_rows,
        "candidates": candidate_rows,
        "target_matches": target_matches,
        "source_population_signature_sha256": _sha256_json(source_signature_rows),
        "candidate_population_signature_sha256": _sha256_json(candidate_signature_rows),
        "authority_boundary": {
            "candidate_is_review_target_only": True,
            "exact_title_match_is_relationship_evidence_only": True,
            "vote_arithmetic_interpreted": False,
            "terminal_outcome_assigned": False,
            "absence_treated_as_disposition": False,
            "meeting_occurrence_asserted": False,
            "causality_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "A numbered-vote record candidate is not itself a terminal outcome assignment.",
            "An exact Eastwood title match proves only a mechanical relationship to the tracked ordinance title at this stage.",
            "Vote counts are preserved but not interpreted as passage, failure, approval, or denial.",
            "No matching candidate is not evidence of denial, withdrawal, failure, non-passage, or any other disposition.",
            "Publisher meeting metadata and marked-agenda publication are not used here to assert meeting occurrence.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--observation-time", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = measure(
        state_dir=Path(args.state_dir),
        plan_path=Path(args.plan),
        target=_load(args.target),
        observation_time=args.observation_time,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
