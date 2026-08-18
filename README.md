# Proofline

**Follow the record.**

Proofline is public-record intelligence infrastructure for provenance-backed investigative leads.

It is designed to continuously ingest large, messy public archives; preserve source integrity; extract searchable evidence; detect changes, anomalies, relationships, and contradictions; and surface reproducible leads for human investigators and journalists.

Proofline does **not** decide that a person or organization has done something wrong. It distinguishes source evidence from machine-derived observations and leaves editorial and investigative judgment with humans.

## The problem

Important facts are often technically public but practically hidden inside volume:

- massive document releases
- scanned or poorly OCR'd PDFs
- spreadsheets and native files
- revisions and quiet replacements
- duplicated records
- inconsistent names and identifiers
- audio and transcripts
- records distributed across multiple agencies or systems

Search alone does not solve this. The harder problem is building a trustworthy corpus that can answer:

- What exists?
- What changed?
- What disappeared?
- What is duplicated?
- What cannot be reliably extracted?
- What patterns recur across independent records?
- What deserves human attention?

## Core model

Proofline separates three truth layers:

### Bronze — Source

Immutable original artifacts and retrieval metadata.

- original bytes
- source URI
- retrieval timestamp
- SHA-256 digest
- native/public identifier
- version relationship

### Silver — Evidence

Stable human-inspectable units with append-only extraction attempts.

- pages or logical records
- extracted text
- layout / offsets
- extraction method
- OCR quality/confidence
- source locator

An evidence unit remains stable while better extraction methods may add new extraction records. A later OCR result does not rewrite the history of an earlier native-text attempt.

### Gold — Derived

Probabilistic or interpretive material that may be regenerated as models improve.

- entities and aliases
- relationships
- classifications
- events
- embeddings
- anomalies
- observations
- investigative leads
- LLM-generated summaries

**Gold may be wrong. Silver must be reproducible. Bronze must remain immutable.**

## Design principles

1. **Evidence before narrative.** The system surfaces observations and leads, not accusations.
2. **Provenance is mandatory.** Every consequential derived claim should be traceable to its source artifact and evidence location.
3. **Cheap extraction first.** Use existing text layers before OCR; escalate only when quality requires it.
4. **Confidence is data.** Low-quality extraction is recorded and reviewable rather than silently accepted.
5. **Indexes are disposable.** Search indexes and embeddings may be rebuilt. Evidence identities should remain stable.
6. **Longitudinal memory matters.** A changed or removed public record can be as important as a newly published one.
7. **Humans retain editorial agency.** Newsworthiness, fairness, publication, and accusation are human decisions.
8. **Seek benign explanations.** Lead generation should preserve uncertainty and make room for ordinary explanations.

## Architecture

```text
public source
    |
    v
watch/acquisition ---> artifact hash/version history
    |
    v
extraction ---> page/record evidence ---> quality review queue
    |
    v
normalization ---> FTS / vector / graph indexes
    |
    v
pattern detectors ---> observations ---> corroboration
    |
    v
lead desk ---> human investigation
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the working technical model and [GOVERNANCE.md](GOVERNANCE.md) for epistemic and editorial boundaries.

## Quick start

```bash
python -m pip install -e ".[dev]"

proofline ingest ./records/report.pdf \
  --source-uri "https://example.gov/reports/report.pdf" \
  --native-id "REPORT-2026-08"

proofline status
proofline trace obs:example
```

### Watch public sources

Proofline uses a versioned JSON source manifest. See [examples/source-manifest.json](examples/source-manifest.json) and [docs/SOURCE_MANIFEST.md](docs/SOURCE_MANIFEST.md).

```bash
proofline watch examples/source-manifest.json
proofline changes
proofline changes --include-unchanged
```

Each visit classifies a resource as:

- `new`
- `unchanged`
- `changed`
- `unavailable`

A `changed` state means the bytes differ from the immediately prior successful observation. It does not explain why they changed. An `unavailable` state records a failed check; it does not by itself establish deletion or intentional removal.

Explicit numeric sequence metadata can also surface structural gaps without guessing identifier semantics from filenames.

## Local state

By default state is written beneath `.proofline/`:

```text
.proofline/
├── proofline.db
└── artifacts/
    └── sha256/
        └── <prefix>/<full-sha256>
```

Original bytes are copied to content-addressed storage before extraction. If the same source URI later returns different bytes, Proofline preserves both artifacts. Watcher visits are recorded separately in an append-only ledger so a sequence such as `A -> B -> A` is represented chronologically rather than collapsed into unique artifact pairs.

## Current implementation

The evidence core includes:

- SHA-256 content-addressed artifacts
- deterministic source/evidence identifiers
- immutable source/artifact lineage
- stable page/logical evidence units
- append-only evidence extraction history
- append-only processing events enforced by SQLite triggers
- native PyMuPDF page extraction with Unicode-aware quality scoring
- text-file extraction
- observation and lead persistence with evidence-reference validation
- `proofline ingest`, `proofline status`, and `proofline trace`
- a generated difficult fixture corpus covering scans, corruption, duplicates, revisions, and conflicting structured records

The corpus watcher includes:

- versioned JSON manifests
- HTTP acquisition with retry/backoff and media validation
- HTTP status, content type, ETag, and Last-Modified capture
- append-only source-check history
- `new`, `unchanged`, `changed`, and `unavailable` states
- correct change chronology across source reversions
- explicit sequence-gap primitives
- `proofline watch` and `proofline changes`

Scheduling is intentionally external to the evidence core: cron, systemd timers, container schedulers, or hosted job runners can invoke the same deterministic `proofline watch` command at the desired cadence.

See [ROADMAP.md](ROADMAP.md), [docs/EVIDENCE_REFERENCE.md](docs/EVIDENCE_REFERENCE.md), and [docs/SOURCE_MANIFEST.md](docs/SOURCE_MANIFEST.md).
