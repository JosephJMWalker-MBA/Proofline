"""Core immutable domain models for Proofline.

These models intentionally separate source artifacts, reproducible evidence,
and probabilistic/interpretive outputs. They are small by design so Milestone 0
can prove provenance before adding storage, OCR, retrieval, or LLM layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class EvidenceUnitType(StrEnum):
    PAGE = "page"
    SPREADSHEET_RANGE = "spreadsheet_range"
    TRANSCRIPT_INTERVAL = "transcript_interval"
    EMAIL = "email"
    IMAGE_REGION = "image_region"
    RECORD = "record"
    OTHER = "other"


class ObservationStatus(StrEnum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    CORROBORATED = "corroborated"


class LeadStatus(StrEnum):
    CANDIDATE = "candidate"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    EXPLAINED = "explained"
    CORROBORATED = "corroborated"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


def _validate_sha256(value: str) -> None:
    if len(value) != 64:
        raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("sha256 must be hexadecimal") from exc


def _validate_score(name: str, value: float | None) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Where an artifact came from in the public record."""

    source_uri: str
    retrieved_at: datetime
    native_identifier: str | None = None
    source_name: str | None = None


@dataclass(frozen=True, slots=True)
class Artifact:
    """Immutable byte-level source identity (Bronze)."""

    artifact_id: str
    sha256: str
    byte_size: int
    source: SourceReference
    media_type: str | None = None
    supersedes_artifact_id: str | None = None

    def __post_init__(self) -> None:
        _validate_sha256(self.sha256)
        if self.byte_size < 0:
            raise ValueError("byte_size cannot be negative")


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    """Stable, human-inspectable evidence derived from an artifact (Silver)."""

    evidence_id: str
    artifact_id: str
    unit_type: EvidenceUnitType
    locator: str
    extracted_text: str | None = None
    extraction_method: str | None = None
    quality_score: float | None = None
    char_start: int | None = None
    char_end: int | None = None

    def __post_init__(self) -> None:
        _validate_score("quality_score", self.quality_score)
        if self.char_start is not None and self.char_start < 0:
            raise ValueError("char_start cannot be negative")
        if self.char_end is not None and self.char_end < 0:
            raise ValueError("char_end cannot be negative")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end cannot precede char_start")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A precise backwards pointer from derived material to evidence."""

    evidence_id: str
    artifact_id: str
    locator: str
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingEvent:
    """Append-only record of work performed on an artifact or evidence unit."""

    event_id: str
    occurred_at: datetime
    stage: str
    method: str
    artifact_id: str | None = None
    evidence_id: str | None = None
    software_version: str | None = None
    model_version: str | None = None
    quality_score: float | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_score("quality_score", self.quality_score)
        if self.artifact_id is None and self.evidence_id is None:
            raise ValueError("processing event must reference an artifact or evidence unit")


@dataclass(frozen=True, slots=True)
class Observation:
    """A reproducible machine-derived pattern, discrepancy, or anomaly (Gold)."""

    observation_id: str
    observation_type: str
    explanation: str
    evidence_refs: tuple[EvidenceReference, ...]
    method: str
    score: float | None = None
    uncertainty: str | None = None
    limitations: tuple[str, ...] = ()
    status: ObservationStatus = ObservationStatus.CANDIDATE

    def __post_init__(self) -> None:
        _validate_score("score", self.score)
        if not self.evidence_refs:
            raise ValueError("observation must reference at least one evidence unit")


@dataclass(frozen=True, slots=True)
class Lead:
    """Human-review packet assembled from one or more observations."""

    lead_id: str
    title: str
    why_surfaced: str
    observation_ids: tuple[str, ...]
    evidence_refs: tuple[EvidenceReference, ...]
    questions_worth_asking: tuple[str, ...] = ()
    possible_benign_explanations: tuple[str, ...] = ()
    novelty: float | None = None
    anomaly_strength: float | None = None
    corroboration: float | None = None
    source_quality: float | None = None
    uncertainty: float | None = None
    status: LeadStatus = LeadStatus.CANDIDATE
    reviewer_notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.observation_ids:
            raise ValueError("lead must reference at least one observation")
        if not self.evidence_refs:
            raise ValueError("lead must retain evidence references")
        for name in (
            "novelty",
            "anomaly_strength",
            "corroboration",
            "source_quality",
            "uncertainty",
        ):
            _validate_score(name, getattr(self, name))
