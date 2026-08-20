from __future__ import annotations

import importlib.util
from pathlib import Path

from proofline.storage import ProoflineStore


def _load_profile_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "akron-2026"
        / "profile_attachment_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("akron_attachment_evidence_profile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_metadata_uses_current_artifact_schema(tmp_path: Path) -> None:
    module = _load_profile_module()
    store = ProoflineStore(tmp_path / "proofline.db")
    artifact_id = "artifact:test"

    with store.connection() as connection:
        connection.execute(
            """
            INSERT INTO artifacts(
                artifact_id, sha256, byte_size, media_type, stored_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                "0" * 64,
                321,
                "application/pdf",
                "bronze/test.pdf",
                "2026-08-20T00:00:00+00:00",
            ),
        )

    metadata = module._artifact_metadata(store, artifact_id)

    assert metadata == {
        "artifact_id": artifact_id,
        "sha256": "0" * 64,
        "media_type": "application/pdf",
        "byte_size": 321,
        "stored_path": "bronze/test.pdf",
    }
