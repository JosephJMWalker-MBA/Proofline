#!/usr/bin/env python3
"""Probe exact explicit-reference recurrence across preserved Akron evidence.

This is a T21 descriptive experiment. It may identify evidence units that share the
same literal, normalized public-record reference key, but it does not create
SourceRelation rows, alter SourceFamily membership, or assign event/outcome semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from proofline.explicit_references import (
    EXPLICIT_REFERENCE_METHOD,
    extract_explicit_references,
)
from proofline.onbase_attachments import FETCH_STRATEGY, OnBaseAttachmentWatcher
from proofline.storage import ProoflineStore
from proofline.watcher import ManifestResource, SourceManifest

SCHEMA = "proofline-akron-t21-explicit-reference-probe/v1"
EXPECTED_ATTACHMENT_MANIFEST_SHA256 = (
    "7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a"
)


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _uri_hash(source_uri: str) -> str:
    return hashlib.sha256(source_uri.encode("utf-8")).hexdigest()


def _resolve_reference_key(raw_key: str) -> tuple[str, str]:
    references = tuple(
        reference
        for reference in extract_explicit_references(
            raw_key,
            evidence_id="evidence:t21-probe-key",
        )
        if reference.join_eligible
    )
    if len(references) != 1:
        raise ValueError("probe reference key must contain exactly one strong explicit identifier")
    reference = references[0]
    if reference.raw_text != raw_key:
        raise ValueError("probe reference key must consist only of the explicit identifier")
    return reference.kind, reference.normalized_key


def _resolve_target_resource(manifest: dict, source_hash: str) -> dict:
    resources = manifest.get("resources") or []
    matches = [
        item
        for item in resources
        if _uri_hash(str(item.get("source_uri") or "")) == source_hash
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one attachment source for frozen identity hash; found {len(matches)}"
        )
    return matches[0]


def _ingest_target(state_dir: Path, resource: dict) -> dict:
    source_uri = str(resource["source_uri"])
    watcher = OnBaseAttachmentWatcher(state_dir)
    manifest = SourceManifest(
        name="akron-t21-reference-probe-target",
        resources=(
            ManifestResource(
                source_uri=source_uri,
                source_name=resource.get("source_name"),
                native_identifier=resource.get("native_identifier"),
                expected_media_type=resource.get("expected_media_type") or "application/pdf",
                fetch_strategy=resource.get("fetch_strategy") or FETCH_STRATEGY,
            ),
        ),
    )
    result = watcher.run(manifest)
    counts = result.get("counts") or {}
    if counts.get("unavailable"):
        raise RuntimeError(f"T21 target attachment unavailable: {counts}")
    if counts.get("new") not in {0, 1} or counts.get("changed") not in {0, 1}:
        raise RuntimeError(f"unexpected T21 target sync accounting: {counts}")
    return result


def _preferred_evidence_rows(store: ProoflineStore) -> list[dict]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT
                eu.evidence_id,
                eu.artifact_id,
                eu.unit_type,
                eu.locator,
                best.method,
                best.extracted_text,
                best.quality_score,
                best.software_version,
                best.model_version
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
            ORDER BY eu.evidence_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _sources_by_artifact(store: ProoflineStore) -> dict[str, list[dict]]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT ss.artifact_id, s.source_id, s.source_uri, s.source_name
            FROM source_snapshots ss
            JOIN sources s ON s.source_id = ss.source_id
            ORDER BY ss.artifact_id, s.source_uri
            """
        ).fetchall()
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        result[str(row["artifact_id"])].append(
            {
                "source_id": str(row["source_id"]),
                "source_uri": str(row["source_uri"]),
                "source_name": row["source_name"],
                "source_uri_sha256": _uri_hash(str(row["source_uri"])),
            }
        )
    return dict(result)


def probe(
    state_dir: Path,
    *,
    attachment_manifest: dict,
    target_source_hash: str,
    reference_key: str,
) -> dict:
    kind, normalized_key = _resolve_reference_key(reference_key)
    target = _resolve_target_resource(attachment_manifest, target_source_hash)
    _ingest_target(state_dir, target)

    store = ProoflineStore(state_dir / "proofline.db")
    sources_by_artifact = _sources_by_artifact(store)
    matches: list[dict] = []
    target_evidence_count = 0

    for row in _preferred_evidence_rows(store):
        text = str(row.get("extracted_text") or "")
        references = [
            reference
            for reference in extract_explicit_references(
                text,
                evidence_id=str(row["evidence_id"]),
            )
            if reference.join_eligible
            and reference.kind == kind
            and reference.normalized_key == normalized_key
        ]
        if not references:
            continue
        artifact_sources = sources_by_artifact.get(str(row["artifact_id"]), [])
        if any(item["source_uri_sha256"] == target_source_hash for item in artifact_sources):
            target_evidence_count += 1
        matches.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "artifact_id": str(row["artifact_id"]),
                "unit_type": str(row["unit_type"]),
                "locator": str(row["locator"]),
                "preferred_extraction": {
                    "method": str(row["method"]),
                    "quality_score": float(row["quality_score"] or 0.0),
                    "software_version": row["software_version"],
                    "model_version": row["model_version"],
                },
                "references": [reference.to_dict() for reference in references],
                "sources": artifact_sources,
            }
        )

    if target_evidence_count < 1:
        raise RuntimeError(
            "the exact target source was ingested but its preferred evidence did not reproduce the probe key"
        )

    source_ids = {
        source["source_id"]
        for match in matches
        for source in match["sources"]
    }
    artifact_ids = {match["artifact_id"] for match in matches}
    evidence_ids = {match["evidence_id"] for match in matches}

    return {
        "schema": SCHEMA,
        "method": EXPLICIT_REFERENCE_METHOD,
        "stage": "post_blind_audit_descriptive_reference_probe",
        "target_source_uri_sha256": target_source_hash,
        "reference": {
            "kind": kind,
            "normalized_key": normalized_key,
        },
        "counts": {
            "matching_evidence_units": len(evidence_ids),
            "matching_artifacts": len(artifact_ids),
            "matching_sources": len(source_ids),
            "target_matching_evidence_units": target_evidence_count,
        },
        "matches": matches,
        "authority_boundary": {
            "source_relation_created": False,
            "source_family_modified": False,
            "event_identity_assigned": False,
            "outcome_assigned": False,
            "detector_authorized": False,
            "lead_count": None,
        },
        "non_claims": [
            "Shared explicit reference text is a record-family candidate signal, not an authoritative source relation.",
            "This probe performs no fuzzy matching, address matching, or semantic similarity.",
            "Repeated references do not establish approval, denial, causation, agreement, or wrongdoing.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--attachment-manifest", required=True)
    parser.add_argument("--target-source-hash", required=True)
    parser.add_argument("--reference-key", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.attachment_manifest)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest != EXPECTED_ATTACHMENT_MANIFEST_SHA256:
        raise RuntimeError(f"unexpected Akron attachment manifest SHA-256: {digest}")

    result = probe(
        Path(args.state_dir),
        attachment_manifest=_load(manifest_path),
        target_source_hash=args.target_source_hash,
        reference_key=args.reference_key,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
