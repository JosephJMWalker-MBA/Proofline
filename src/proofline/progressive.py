"""Quality-gated progressive extraction over existing evidence units."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .hashing import sha256_text, stable_id
from .models import ProcessingEvent
from .ocr import OcrBackend
from .review import preferred_extraction
from .storage import ProoflineStore


@dataclass(frozen=True, slots=True)
class ProgressiveExtractionResult:
    artifact_id: str
    backend: str
    threshold: float
    candidates: int
    attempted: int
    added: int
    skipped: int
    failed: int
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["failures"] = list(self.failures)
        return data


class ProgressiveExtractor:
    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")

    def _artifact(self, artifact_id: str) -> dict:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown artifact: {artifact_id}")
        return dict(row)

    def _page_units(self, artifact_id: str) -> list[dict]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evidence_units
                WHERE artifact_id = ? AND unit_type = 'page'
                ORDER BY locator
                """,
                (artifact_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _page_number(locator: str) -> int:
        if not locator.startswith("page:"):
            raise ValueError(f"unsupported page locator: {locator}")
        return int(locator.split(":", 1)[1])

    def run_ocr(
        self,
        artifact_id: str,
        backend: OcrBackend,
        *,
        threshold: float = 0.70,
        force: bool = False,
    ) -> ProgressiveExtractionResult:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")

        artifact = self._artifact(artifact_id)
        media_type = artifact.get("media_type")
        if media_type != "application/pdf":
            raise ValueError("OCR escalation currently supports PDF artifacts only")
        path = self.state_dir / artifact["stored_path"]
        if not path.exists():
            raise FileNotFoundError(path)

        units = self._page_units(artifact_id)
        attempted = 0
        added = 0
        skipped = 0
        failed = 0
        failures: list[str] = []

        for unit in units:
            preferred = preferred_extraction(self.store, unit["evidence_id"])
            preferred_quality = (
                preferred.get("quality_score") if preferred is not None else None
            )
            if (
                not force
                and preferred_quality is not None
                and float(preferred_quality) >= threshold
            ):
                skipped += 1
                continue

            attempted += 1
            page_number = self._page_number(unit["locator"])
            now = datetime.now(UTC)
            try:
                result = backend.extract_page(path, page_number)
                extraction_id = stable_id(
                    "extraction",
                    unit["evidence_id"],
                    result.method,
                    result.software_version or "",
                    result.model_version or "",
                    sha256_text(result.text),
                )
                was_added = self.store.add_evidence_extraction(
                    extraction_id=extraction_id,
                    evidence_id=unit["evidence_id"],
                    occurred_at=now,
                    method=result.method,
                    extracted_text=result.text,
                    quality_score=result.quality_score,
                    software_version=result.software_version,
                    model_version=result.model_version,
                    warnings=result.warnings,
                )
                if was_added:
                    added += 1
                    self.store.add_processing_event(
                        ProcessingEvent(
                            event_id=f"event:{uuid.uuid4()}",
                            occurred_at=now,
                            stage="ocr_extracted",
                            method=result.method,
                            artifact_id=artifact_id,
                            evidence_id=unit["evidence_id"],
                            software_version=result.software_version,
                            model_version=result.model_version,
                            quality_score=result.quality_score,
                            warnings=result.warnings,
                        )
                    )
            except Exception as exc:
                failed += 1
                message = f"{unit['locator']}: {exc}"
                failures.append(message)
                self.store.add_processing_event(
                    ProcessingEvent(
                        event_id=f"event:{uuid.uuid4()}",
                        occurred_at=now,
                        stage="ocr_failed",
                        method=getattr(backend, "name", backend.__class__.__name__),
                        artifact_id=artifact_id,
                        evidence_id=unit["evidence_id"],
                        warnings=(str(exc),),
                    )
                )

        return ProgressiveExtractionResult(
            artifact_id=artifact_id,
            backend=getattr(backend, "name", backend.__class__.__name__),
            threshold=threshold,
            candidates=len(units),
            attempted=attempted,
            added=added,
            skipped=skipped,
            failed=failed,
            failures=tuple(failures),
        )
