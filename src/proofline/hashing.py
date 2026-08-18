"""Content-addressing helpers for Proofline source artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path


_CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for bytes."""

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash a file without loading the entire artifact into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_id_from_sha256(sha256: str) -> str:
    """Create a stable artifact identifier from a validated SHA-256 digest."""

    if len(sha256) != 64:
        raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
    try:
        int(sha256, 16)
    except ValueError as exc:
        raise ValueError("sha256 must be hexadecimal") from exc
    return f"artifact:{sha256}"
