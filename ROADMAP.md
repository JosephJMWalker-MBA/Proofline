# Proofline Roadmap

## Milestone 0 — Evidence Core ✅

**Status: complete.**

Goal: prove source integrity and evidence traceability before adding sophisticated AI.

Delivered:

- [x] immutable artifact identity using SHA-256
- [x] source and retrieval metadata
- [x] page/logical evidence units
- [x] extraction method and quality metadata
- [x] append-only processing events
- [x] observation objects that require evidence references
- [x] SQLite persistence
- [x] a minimal CLI for ingest/status/trace
- [x] tests proving that observations can be traced back to original artifacts
- [x] deliberately difficult generated fixture corpus
- [x] stable evidence-reference v1 contract

Exit criterion:

> Given a derived observation, Proofline can deterministically identify the exact source artifact and evidence unit(s) from which it was produced.

See [docs/EVIDENCE_REFERENCE.md](docs/EVIDENCE_REFERENCE.md).

## Milestone 1 — Corpus Watcher ✅

**Status: complete.**

Goal: detect what changed in a monitored public source without interpreting motive.

Delivered:

- [x] versioned JSON source manifests
- [x] repeatable deterministic watcher runs compatible with external schedulers
- [x] HTTP acquisition with retry/backoff, timeout, User-Agent, and defensive media validation
- [x] new/unchanged/changed/unavailable source-state detection
- [x] content-addressed version preservation
- [x] append-only watcher check history
- [x] HTTP status, Content-Type, ETag, and Last-Modified provenance
- [x] correct chronology when a source reverts to previously seen bytes
- [x] optional native identifiers
- [x] explicit identifier-sequence/gap primitives
- [x] `proofline watch` and `proofline changes`
- [x] local HTTP tests for change, reversion, unavailability, and retries
- [x] watcher semantics and source-manifest documentation

Scheduling policy is intentionally outside the evidence core. Cron, systemd timers, container schedulers, or hosted runners can invoke one deterministic watcher run at any desired cadence without changing evidence semantics.

Exit criterion:

> Proofline can compare repeated source checks and produce a reproducible change set without interpreting motive, while preserving complete prior artifact history.

See [docs/SOURCE_MANIFEST.md](docs/SOURCE_MANIFEST.md).

## Milestone 2 — Progressive Extraction

Goal: reliably turn heterogeneous records into evidence units while controlling cost.

Deliverables:

- native PDF/text extraction
- per-page quality heuristics
- OCR fallback interface
- review queue for low-confidence pages
- spreadsheet/native-file adapters
- extraction version metadata

Exit criterion:

> Every evidence unit identifies how it was extracted and whether its quality crosses configured thresholds.

## Milestone 3 — Search & Retrieval Evaluation

Goal: find the right evidence, not merely generate plausible answers.

Deliverables:

- SQLite FTS5 lexical retrieval
- structured identifier/date/value search
- benchmark corpus containing deliberately difficult records
- research-question evaluation set
- retrieval recall and provenance-accuracy metrics
- optional semantic retrieval experiment

Exit criterion:

> Retrieval quality is measured against known evidence targets, and any vector infrastructure is justified by measured failures of simpler methods.

## Milestone 4 — Entity & Relationship Layer

Goal: support cross-record investigation without creating guilt-by-association machinery.

Deliverables:

- entity mentions tied to evidence units
- aliases and probabilistic resolution
- explicit relationship evidence types
- source-independence tracking
- entity timeline and neighbor queries

Exit criterion:

> Every relationship shown to a user distinguishes explicit evidence, deterministic derivation, co-occurrence, and probabilistic inference.

## Milestone 5 — Detector Framework

Goal: surface reproducible anomalies and contradictions.

Initial detectors:

- source/version changes
- identifier sequence gaps
- conflicting structured values
- repeated addresses/contact details across entities
- unusual amendment/value changes
- entity appearance/disappearance across versions
- cross-source presence/absence discrepancies

Exit criterion:

> Each detector produces an observation with method, evidence, uncertainty, and known limitations.

## Milestone 6 — Lead Desk

Goal: convert observations into investigation-ready packets for human review.

Deliverables:

- lead scoring dimensions: novelty, anomaly, corroboration, source quality, uncertainty
- benign-explanation field
- questions-worth-asking generation
- evidence packet assembly
- lead lifecycle and reviewer notes
- append-only disposition history

Exit criterion:

> A journalist can understand why a lead surfaced, inspect its evidence, reject it, explain it, or pursue it without trusting an opaque model conclusion.

## Milestone 7 — LLM / MCP Research Interface

Goal: let reasoning models interact with Proofline without making the model the system of record.

Candidate tools:

```text
search
fetch_evidence
fetch_artifact_metadata
compare_versions
entity_lookup
entity_neighbors
timeline
evidence_pack
trace_observation
```

Exit criterion:

> Model outputs can cite stable Proofline evidence references, and the same evidence can be independently retrieved without the model.

## Reference test corpus

The development corpus should intentionally contain ugly cases:

- born-digital PDF
- scanned PDF
- poor OCR
- multi-column layout
- table
- spreadsheet
- handwriting
- duplicate document
- OCR-variant duplicate
- corrupted artifact
- missing identifier in a sequence
- same URL returning a revised artifact
- audio/transcript pair
- conflicting values across authoritative records

The generated corpus currently covers born-digital PDF, image-only scan, exact duplicate, corrupted PDF, source revision pair, and conflicting structured records. Later milestones will extend it as new adapters and detectors arrive.
