#!/usr/bin/env python3
"""Verify durable Proofline R0/R1 publication artifacts against frozen receipts.

This script verifies only research artifacts committed to Git and named by the
first publication package. It does not fetch live municipal data and does not
depend on expired GitHub Actions artifacts.
"""
from __future__ import annotations

import gzip
import hashlib
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

EXPECTED_FILES = {
    "experiments/canton-2026/retrieval/r1-canonical-v2-unscored.json":
        "aee4d01b3b7fa505d008296e226bbaff43af6022c025ad9764f14b412e9cfbbc",
    "experiments/canton-2026/retrieval/r1-canonical-v2-raw-pool.json":
        "60807ca48ce44f5fd400b5509fedaec5a34e99b34b8619bfe3f8b3674207c0b3",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/evaluation.json":
        "09a2a40fd86a7b66be8f87487fa45ff015b24826cde73ac40b964852c79ebe17",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/scorable-report.json":
        "5a0b8a7e773fdc75fbb74eb8fb0a4b34a8d632070419f9bb5aa199a69fd8e97d",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/summary.json":
        "26dfaba3ae44a527829666da4c69fe86e70efda90fd0711965ec8ea03d2f55eb",
    "experiments/canton-2026/retrieval/r1-canonical-v2-score/sync.json":
        "02d66d49c5c28e4b60889dd263b3138547452515f8b0761c384e3abdb12a9b72",
    "experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz":
        "2beb620c3421389575175349e28f16dd4ef75364fcf675efe7933d298c49da78",
    "experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz":
        "afb475dc59c57056155776e54c97cf9eb33e62c55c8d66a35ba4f59c7f143af2",
}

EXPECTED_AKRON_DECOMPRESSED = (
    "fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681"
)

EXPECTED_AKRON_SCORE_MEMBERS = {
    "evaluation.json": "3793ef6cabfc0643a3b5f76bfcd5dc81de7d9b1662264288f3442d7ea5d691ce",
    "scorable-report.json": "5bf5f5fb0f2ae4f4b7fd6dfdc0f4b79e8fad24ef1270ca14e163e5741a110826",
    "summary.json": "f8e7957c348dc78b6a6df8fd2e6f8e0e4e5c6a69155687aff958ad3e8029a292",
    "index.json": "74e8d665e0b8f74ee3083a5cf42f79b1b7531c80a67985abccce462b9c49329f",
    "status.json": "abf3a1d681aae2363983ee53d1aa03610b3931f0af62b8fd71d947d2b0a7aaa0",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise SystemExit(
            f"FAIL {label}\n  expected {expected}\n  actual   {actual}"
        )
    print(f"PASS {label} {actual}")


def main() -> None:
    for relative, expected in EXPECTED_FILES.items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"FAIL missing durable artifact: {relative}")
        check(relative, sha256_bytes(path.read_bytes()), expected)

    akron_gzip = ROOT / "experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz"
    with gzip.open(akron_gzip, "rb") as handle:
        decompressed = handle.read()
    check(
        "Akron decompressed frozen benchmark",
        sha256_bytes(decompressed),
        EXPECTED_AKRON_DECOMPRESSED,
    )

    score_archive = ROOT / "experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz"
    with tarfile.open(score_archive, "r:gz") as archive:
        files = [m for m in archive.getmembers() if m.isfile()]
        by_basename: dict[str, list[tarfile.TarInfo]] = {}
        for member in files:
            by_basename.setdefault(Path(member.name).name, []).append(member)

        for basename, expected in EXPECTED_AKRON_SCORE_MEMBERS.items():
            matches = by_basename.get(basename, [])
            if len(matches) != 1:
                raise SystemExit(
                    f"FAIL expected exactly one {basename} in Akron score archive; found {len(matches)}"
                )
            extracted = archive.extractfile(matches[0])
            if extracted is None:
                raise SystemExit(f"FAIL could not read {matches[0].name}")
            check(
                f"Akron score member {matches[0].name}",
                sha256_bytes(extracted.read()),
                expected,
            )

    print("\nALL PUBLICATION ARTIFACT HASHES VERIFIED")


if __name__ == "__main__":
    main()
