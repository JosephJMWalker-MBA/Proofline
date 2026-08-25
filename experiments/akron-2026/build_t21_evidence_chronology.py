#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from proofline.evidence_chronology import build_chronology


def load(path: str) -> dict:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit(
            "usage: build_t21_evidence_chronology.py AGENDA RELATIONSHIPS MARKED_SCAN NARROW_SEARCH EXPANDED_SEARCH OUTPUT_DIR"
        )
    agenda_path, relationship_path, marked_path, narrow_path, expanded_path, output_dir = sys.argv[1:]
    chronology = build_chronology(
        load(agenda_path), load(relationship_path), load(marked_path), load(narrow_path), load(expanded_path)
    )
    chronology["source_receipts"] = {
        "agenda_status_sequence": {"path": agenda_path, "file_sha256": file_sha256(agenda_path)},
        "evidence_relationships": {"path": relationship_path, "file_sha256": file_sha256(relationship_path)},
        "marked_agenda_terminal_candidate_scan": {"path": marked_path, "file_sha256": file_sha256(marked_path)},
        "passed_legislation_narrow_search": {"path": narrow_path, "file_sha256": file_sha256(narrow_path)},
        "passed_legislation_expanded_search": {"path": expanded_path, "file_sha256": file_sha256(expanded_path)},
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "t21-evidence-chronology.json"
    target.write_text(json.dumps(chronology, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"counts": chronology["counts"], "chronology_signature_sha256": chronology["chronology_signature_sha256"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
