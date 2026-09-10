#!/usr/bin/env python3
"""Build the deterministic research-owned Proofline R0/R1 measurement package.

The archive intentionally excludes underlying third-party municipal source bytes
and Proofline software as a software publication. It contains the frozen
benchmark/evaluation records and publication-governance material needed to
inspect the measurements reported by the first Proofline research report.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "dist"
PACKAGE = "proofline-r0-r1-measurement-package-v1.tar.gz"

INCLUDE = [
    "experiments/canton-2026/retrieval/R1_CANONICAL_V2_FREEZE.md",
    "experiments/canton-2026/retrieval/R1_CANONICAL_V2_SCORE.md",
    "experiments/canton-2026/retrieval/source-policy.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-unscored.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-raw-pool.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/evaluation.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/scorable-report.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/summary.json",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/sync.json",
    "experiments/akron-2026/retrieval/R1_TRANSFER_V1_FREEZE.md",
    "experiments/akron-2026/retrieval/R1_TRANSFER_V1_SCORE.md",
    "experiments/akron-2026/source-policy.json",
    "experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz",
    "experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz",
    "docs/REVIEW_RECORDS.md",
    "experiments/canton-2026/reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json",
    "experiments/canton-2026/reviews/lead-ab70a8e49322a7662e31fa1331926d34358a549527b293427c96ade005206a51.json",
    "research/publications/proofline-r0-r1/ARTIFACT_MANIFEST.md",
    "research/publications/proofline-r0-r1/CLAIM_EVIDENCE_MATRIX.md",
    "research/publications/proofline-r0-r1/R0_REVIEW_LINEAGE.md",
    "research/publications/proofline-r0-r1/RIGHTS_DECISION.md",
    "research/publications/proofline-r0-r1/verify_artifacts.py",
]

README = """# Proofline R0/R1 Measurement Package\n\nThis archive accompanies the first Proofline research report, \"Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems.\"\n\nIt contains research-owned benchmark definitions, freeze/score receipts, durable evaluation outputs, R0 review-lineage records, and publication verification material for the Canton canonical and Akron transfer experiments.\n\n## Scope\n\nThe package is bounded to the completed Canton R0/R1 and Akron R1 retrieval-transfer work used by the report. Akron T21 is excluded.\n\n## Rights boundary\n\nThe included research-owned package is intended for deposit under CC BY 4.0. Underlying third-party municipal source bytes are not bundled. Proofline software is not licensed or published as software by this archive. See `research/publications/proofline-r0-r1/RIGHTS_DECISION.md`.\n\n## Reproducibility\n\nRun:\n\n```bash\npython research/publications/proofline-r0-r1/verify_artifacts.py\n```\n\nto verify the historical benchmark and score identities against the durable Git-resident bytes.\n\n`measurement-package-manifest.json` records SHA-256 for every included repository file and the source commit used to build this archive.\n"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_bytes(tar: tarfile.TarFile, name: str, data: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = mode
    tar.addfile(info, io.BytesIO(data))


def source_commit() -> str:
    value = os.environ.get("GITHUB_SHA", "").strip()
    if value:
        return value
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    OUT.mkdir(exist_ok=True)

    file_entries = []
    payloads: list[tuple[str, bytes]] = []
    for relative in sorted(INCLUDE):
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing package input: {relative}")
        data = path.read_bytes()
        payloads.append((relative, data))
        file_entries.append({
            "path": relative,
            "sha256": sha256(data),
            "size_bytes": len(data),
        })

    manifest = {
        "schema": "proofline-measurement-package/v1",
        "title": "Proofline R0/R1 Measurement Package: Canton Canonical and Akron Transfer Benchmarks",
        "source_repository": "https://github.com/JosephJMWalker-MBA/Proofline",
        "source_commit": source_commit(),
        "orcid": "0009-0005-5099-807X",
        "rights": "CC BY 4.0 for included research-owned files; no license grant over excluded municipal source bytes or Proofline software.",
        "excluded": [
            "underlying third-party municipal source bytes",
            "Proofline software as a software publication",
            "Akron T21 ongoing-investigation materials",
        ],
        "files": file_entries,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        add_bytes(tar, "README.md", README.encode())
        add_bytes(tar, "measurement-package-manifest.json", manifest_bytes)
        for relative, data in payloads:
            mode = 0o755 if relative.endswith(".py") else 0o644
            add_bytes(tar, relative, data, mode)

    archive_path = OUT / PACKAGE
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(tar_buffer.getvalue())

    digest = sha256(archive_path.read_bytes())
    sha_path = OUT / f"{PACKAGE}.sha256"
    sha_path.write_text(f"{digest}  {PACKAGE}\n", encoding="utf-8")
    manifest_path = OUT / "measurement-package-manifest.json"
    manifest_path.write_bytes(manifest_bytes)

    print(f"PACKAGE {archive_path}")
    print(f"SHA256 {digest}")
    print(f"FILES {len(file_entries)} repository files + README + generated manifest")


if __name__ == "__main__":
    main()
