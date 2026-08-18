"""Content-addressing and deterministic identifier helpers for Proofline."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024
_SEPARATOR = "\x1f"


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest of UTF-8 text."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    """Hash a file without loading the entire artifact into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(sha256: str) -> None:
    if len(sha256) != 64:
        raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
    try:
        int(sha256, 16)
    except ValueError as exc:
        raise ValueError("sha256 must be hexadecimal") from exc


def artifact_id_from_sha256(sha256: str) -> str:
    """Create a stable artifact identifier from a validated SHA-256 digest."""
    _validate_sha256(sha256)
    return f"artifact:{sha256}"


def stable_id(namespace: str, *parts: str) -> str:
    """Build a deterministic namespaced identifier from ordered string parts."""
    if not namespace or ":" in namespace:
        raise ValueError("namespace must be non-empty and cannot contain ':'")
    digest = sha256_text(_SEPARATOR.join(parts))
    return f"{namespace}:{digest}"


def source_id_from_uri(source_uri: str) -> str:
    return stable_id("source", source_uri)


def evidence_id_from_locator(artifact_id: str, unit_type: str, locator: str) -> str:
    return stable_id("evidence", artifact_id, unit_type, locator)
