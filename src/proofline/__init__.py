"""Proofline public API."""

from .hashing import (
    artifact_id_from_sha256,
    evidence_id_from_locator,
    sha256_bytes,
    sha256_file,
    sha256_text,
    source_id_from_uri,
    stable_id,
)
from .ingest import IngestResult, Ingestor
from .models import (
    Artifact,
    EvidenceReference,
    EvidenceUnit,
    EvidenceUnitType,
    Lead,
    LeadStatus,
    Observation,
    ObservationStatus,
    ProcessingEvent,
    SourceReference,
)
from .ocr import OcrBackend, OcrPageResult, PyMuPDFTesseractBackend
from .progressive import ProgressiveExtractionResult, ProgressiveExtractor
from .review import (
    ReviewItem,
    extraction_attempts,
    preferred_extraction,
    review_count,
    review_queue,
)
from .storage import ProoflineStore
from .watcher import (
    CorpusWatcher,
    ManifestResource,
    SourceManifest,
    WatchResult,
    WatchState,
    load_manifest,
    manifest_sequence_gaps,
)

__all__ = [
    "Artifact",
    "CorpusWatcher",
    "EvidenceReference",
    "EvidenceUnit",
    "EvidenceUnitType",
    "IngestResult",
    "Ingestor",
    "Lead",
    "LeadStatus",
    "ManifestResource",
    "Observation",
    "ObservationStatus",
    "OcrBackend",
    "OcrPageResult",
    "ProcessingEvent",
    "ProgressiveExtractionResult",
    "ProgressiveExtractor",
    "ProoflineStore",
    "PyMuPDFTesseractBackend",
    "ReviewItem",
    "SourceManifest",
    "SourceReference",
    "WatchResult",
    "WatchState",
    "artifact_id_from_sha256",
    "evidence_id_from_locator",
    "extraction_attempts",
    "load_manifest",
    "manifest_sequence_gaps",
    "preferred_extraction",
    "review_count",
    "review_queue",
    "sha256_bytes",
    "sha256_file",
    "sha256_text",
    "source_id_from_uri",
    "stable_id",
]
