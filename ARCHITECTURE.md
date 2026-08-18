# Proofline Architecture

## System objective

Proofline converts heterogeneous public records into a provenance-preserving evidence substrate that can support search, comparison, anomaly detection, corroboration, and human-led investigation.

The architecture intentionally separates **source preservation**, **reproducible extraction**, and **probabilistic interpretation**.

## Pipeline

```text
Watcher
  -> Acquisition
  -> Artifact Store
  -> Extractor
  -> Evidence Store
  -> Normalizer
  -> Indexers
  -> Detectors
  -> Observations
  -> Lead Builder
  -> Human Review
```

### 1. Watcher

Knows where public records live and whether a source has changed.

Responsibilities:

- poll or revisit configured public sources
- record retrieval timestamps and response metadata
- identify newly published resources
- detect changed or removed resources
- preserve source-specific identifiers and sequence information

The Watcher should answer *what changed in the public record?* before any LLM is involved.

### 2. Acquisition

Downloads source material defensively.

Requirements:

- write to temporary storage first
- validate expected file/media type where possible
- compute SHA-256 from received bytes
- atomically promote completed artifacts
- retry transient failures
- never silently replace an existing artifact with different bytes

### 3. Artifact Store — Bronze

An artifact is an immutable byte-level source object.

Minimum identity:

```text
artifact_id
sha256
source_uri
retrieved_at
media_type
native_identifier
byte_size
```

If the same URI later returns different bytes, Proofline creates a new artifact/version relationship rather than overwriting history.

### 4. Extractor

Extraction is progressive and quality-aware.

Recommended escalation:

```text
embedded/native text
  -> conventional OCR
  -> layout-aware OCR
  -> VLM / specialized extraction
  -> human review
```

The cheapest adequate method wins. Every attempt may emit method, confidence, warnings, timing, and software/model version.

### 5. Evidence Store — Silver

The evidence unit is the smallest stable unit a human can independently inspect and cite: usually a page, spreadsheet row/range, transcript interval, email message, image region, or similar logical record.

Evidence must retain a locator into the original artifact.

```text
EvidenceUnit
  artifact_id
  unit_type
  unit_index / locator
  extracted_text
  extraction_method
  quality_score
  content offsets / geometry when available
```

A retrieval chunk is **not** an evidence unit. Chunks are disposable search structures that point to evidence units.

### 6. Normalization

Normalization creates comparable representations without destroying source fidelity.

Examples:

- normalized dates
- normalized currency values
- canonical whitespace
- names and aliases
- organization identifiers
- addresses
- case / docket / accession / contract numbers

Raw extracted values remain preserved alongside normalized values.

### 7. Indexers

Proofline should support multiple retrieval modes because no single index is sufficient.

- lexical / full-text search for exact names and identifiers
- vector retrieval for concepts and paraphrases
- structured indexes for dates, values, organizations, and native identifiers
- graph traversal for evidence-backed relationships

Indexes are regenerated artifacts, never the system of record.

### 8. Detectors

Detectors produce **observations**, not conclusions.

Examples:

- source changed after initial publication
- identifier sequence contains unexplained gap
- monetary amount differs across related records
- nominally separate entities share address/contact data
- contract value or amendment frequency is statistically unusual
- entity disappears from a later version
- record appears in one authoritative source but not another

A detector should emit:

```text
observation_type
inputs / evidence references
method
score
uncertainty
human-readable explanation
possible limitations
```

### 9. Corroboration

Observations gain investigative value when independently supported.

Corroboration should distinguish:

- repeated copies of the same underlying record
- records derived from a common source
- genuinely independent sources

Three mirrors of one filing are not three-source corroboration.

### 10. Lead Builder

A lead packages evidence for human attention.

Suggested fields:

```text
title
why_surfaced
novelty
anomaly_strength
corroboration
source_quality
uncertainty
possible_benign_explanations
questions_worth_asking
evidence_refs
status
```

A lead is explicitly **not** a finding of wrongdoing.

## Provenance graph

The most important relationship in Proofline is backwards:

```text
Lead
  -> Observation(s)
      -> EvidenceUnit(s)
          -> Artifact
              -> Source URI / native identifier
```

A user should be able to traverse this chain without depending on an LLM-generated explanation.

## Processing state

Long-running ingestion must be restartable. Processing should be modeled as state over immutable artifacts rather than as one monolithic batch job.

Example states:

```text
discovered
retrieved
verified
extracted
needs_review
normalized
indexed
```

Derived stages should be independently rerunnable when extraction software, models, thresholds, or schemas change.

## Initial storage strategy

Milestone 0 should prefer boring, inspectable infrastructure:

- filesystem/object store for immutable artifact bytes
- SQLite initially for metadata/evidence
- SQLite FTS5 for lexical retrieval
- SHA-256 for content identity

Vector infrastructure should be added only after an evaluation set demonstrates retrieval failures that lexical/structured search cannot solve adequately.

## Evaluation target

Proofline should optimize first for:

1. source completeness and integrity
2. extraction quality
3. retrieval recall
4. provenance accuracy
5. lead reproducibility

A fluent summary with the wrong evidence is a failure.
