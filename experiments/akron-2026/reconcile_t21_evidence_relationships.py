#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from proofline.evidence_relationships import build_relationship_graph, sha256_json

SCHEMA = "proofline-akron-t21-evidence-relationship-measurement/v1"


def load(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: reconcile_t21_evidence_relationships.py "
            "COUNCIL_RECEIPT COMMITTEE_RECEIPT DATE_RECEIPT OUTPUT_DIR"
        )
    council_path, committee_path, date_path, output_dir = sys.argv[1:]
    council = load(council_path)
    committee = load(committee_path)
    dates = load(date_path)
    graph = build_relationship_graph(council, committee, dates)

    measurement = {
        "schema": SCHEMA,
        "stage": "deterministic_cross_source_provenance_relationships_before_terminal_semantics",
        "source_receipts": {
            "council_minutes_content": {
                "schema": council["schema"],
                "file_sha256": sha256_file(council_path),
                "target_block_population_signature_sha256": council["target_record_block_population_signature_sha256"],
                "terminal_candidate_count": len(council["terminal_candidate_blocks"]),
            },
            "committee_minutes_content": {
                "schema": committee["schema"],
                "file_sha256": sha256_file(committee_path),
                "target_block_population_signature_sha256": committee["target_block_population_signature_sha256"],
                "terminal_candidate_count": len(committee["terminal_candidate_blocks"]),
            },
            "committee_minutes_dates": {
                "schema": dates["schema"],
                "file_sha256": sha256_file(date_path),
                "stable_candidate_population_signature_sha256": dates["candidate_population"]["stable_population_signature_sha256"],
                "response_population_signature_sha256": dates["candidate_population"]["response_population_signature_sha256"],
            },
        },
        "graph": graph,
        "graph_signature_sha256": sha256_json({
            "nodes": graph["nodes"],
            "relationships": graph["relationships"],
            "authority_boundary": graph["authority_boundary"],
            "outcome": graph["outcome"],
        }),
        "authority_boundary": graph["authority_boundary"],
        "outcome": graph["outcome"],
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "evidence-relationship-measurement.json"
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": graph["counts"], "outcome": graph["outcome"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
