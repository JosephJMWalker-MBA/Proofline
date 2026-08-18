"""Local artifact acquisition and native evidence extraction."""

from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .extractors import extract_native
from .hashing import (
    artifact_id_from_sha256,
    evidence_id_from_locator,
    sha256_file,
    sha256_text,
    source_id_from_uri,
    stable_id,
)
from .models import Artifact, EvidenceUnit, ProcessingEvent, SourceReference
from .storage import ProoflineStore


@dataclass(frozen=True, slots=True)
class IngestResult:
    artifact_id: str
    sha256: str
    source_id: str
    snapshot_id: str
    byte_size: int
    media_type: str | None
    stored_path: str
    supersedes_artifact_id: str | None
    new_artifact: bool
    new_snapshot: bool
    evidence_units_seen: int
    new_extractions: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["warnings"] = list(self.warnings)
        return data


class Ingestor:
    def __init__(self, state_dir: str | Path = ".proofline"):
        self.state_dir = Path(state_dir)
        self.artifact_root = self.state_dir / "artifacts" / "sha256"
        self.store = ProoflineStore(self.state_dir / "proofline.db")

    def _preserve_bytes(self, source_path: Path, digest: str) -> tuple[Path, bool]:
        relative = Path("artifacts") / "sha256" / digest[:2] / digest
        destination = self.state_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(destination) != digest:
                raise RuntimeError(f"artifact store collision at {destination}")
            return relative, False

        temp = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with source_path.open("rb") as src, temp.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp) != digest:
                raise RuntimeError("artifact hash changed while copying")
            os.replace(temp, destination)
        finally:
            if temp.exists():
                temp.unlink()
        return relative, True

    def ingest(
        self,
        path: str | Path,
        *,
        source_uri: str | None = None,
        source_name: str | None = None,
        native_identifier: str | None = None,
        retrieved_at: datetime | None = None,
        media_type: str | None = None,
    ) -> IngestResult:
        input_path = Path(path).expanduser().resolve()
        if not input_path.is_file():
            raise FileNotFoundError(input_path)

        retrieved_at = retrieved_at or datetime.now(UTC)
        source_uri = source_uri or input_path.as_uri()
        source_name = source_name or input_path.name
        media_type = media_type or mimetypes.guess_type(input_path.name)[0] or "application/octet-stream"

        digest = sha256_file(input_path)
        artifact_id = artifact_id_from_sha256(digest)
        relative_path, _ = self._preserve_bytes(input_path, digest)
        source_id = self.store.add_source(source_uri, source_name)
        previous = self.store.latest_artifact_for_source(source_id)
        supersedes = previous if previous and previous != artifact_id else None

        artifact = Artifact(
            artifact_id=artifact_id,
            sha256=digest,
            byte_size=input_path.stat().st_size,
            source=SourceReference(
                source_uri=source_uri,
                retrieved_at=retrieved_at,
                native_identifier=native_identifier,
                source_name=source_name,
            ),
            media_type=media_type,
            supersedes_artifact_id=supersedes,
        )
        new_artifact = self.store.add_artifact(artifact, relative_path.as_posix())
        snapshot_id = stable_id("snapshot", source_id, artifact_id)
        new_snapshot = self.store.add_source_snapshot(
            snapshot_id=snapshot_id,
            source_id=source_id,
            artifact_id=artifact_id,
            retrieved_at=retrieved_at,
            native_identifier=native_identifier,
            supersedes_artifact_id=supersedes,
        )

        ingest_warnings: list[str] = []
        if not new_snapshot:
            ingest_warnings.append("source already mapped to this artifact")
        self.store.add_processing_event(
            ProcessingEvent(
                event_id=f"event:{uuid.uuid4()}",
                occurred_at=retrieved_at,
                stage="retrieved",
                method="local_file_ingest",
                artifact_id=artifact_id,
                warnings=tuple(ingest_warnings),
            )
        )

        evidence_count = 0
        new_extractions = 0
        try:
            units = extract_native(input_path, media_type)
            for extracted in units:
                evidence_count += 1
                evidence_id = evidence_id_from_locator(
                    artifact_id, extracted.unit_type.value, extracted.locator
                )
                unit = EvidenceUnit(
                    evidence_id=evidence_id,
                    artifact_id=artifact_id,
                    unit_type=extracted.unit_type,
                    locator=extracted.locator,
                )
                self.store.add_evidence_unit(unit)
                extraction_id = stable_id(
                    "extraction",
                    evidence_id,
                    extracted.method,
                    sha256_text(extracted.text or ""),
                )
                added = self.store.add_evidence_extraction(
                    extraction_id=extraction_id,
                    evidence_id=evidence_id,
                    occurred_at=retrieved_at,
                    method=extracted.method,
                    extracted_text=extracted.text,
                    quality_score=extracted.quality_score,
                    warnings=extracted.warnings,
                )
                if added:
                    new_extractions += 1
                    self.store.add_processing_event(
                        ProcessingEvent(
                            event_id=f"event:{uuid.uuid4()}",
                            occurred_at=retrieved_at,
                            stage="extracted",
                            method=extracted.method,
                            artifact_id=artifact_id,
                            evidence_id=evidence_id,
                            quality_score=extracted.quality_score,
                            warnings=extracted.warnings,
                        )
                    )
        except Exception as exc:
            ingest_warnings.append(f"native extraction failed: {exc}")
            self.store.add_processing_event(
                ProcessingEvent(
                    event_id=f"event:{uuid.uuid4()}",
                    occurred_at=datetime.now(UTC),
                    stage="extraction_failed",
                    method="native_extraction",
                    artifact_id=artifact_id,
                    warnings=(str(exc),),
                )
            )

        return IngestResult(
            artifact_id=artifact_id,
            sha256=digest,
            source_id=source_id_from_uri(source_uri),
            snapshot_id=snapshot_id,
            byte_size=artifact.byte_size,
            media_type=media_type,
            stored_path=relative_path.as_posix(),
            supersedes_artifact_id=supersedes,
            new_artifact=new_artifact,
            new_snapshot=new_snapshot,
            evidence_units_seen=evidence_count,
            new_extractions=new_extractions,
            warnings=tuple(ingest_warnings),
        )
