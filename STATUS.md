# Proofline — Live Status

This file answers three questions that the roadmap and architecture documents do not answer clearly enough:

1. What is implemented **right now**?
2. What has actually been **measured or validated**?
3. What is Proofline trying to prove **next**?

## Implemented

### Evidence core — M0 complete

- immutable SHA-256 source artifacts
- stable evidence units with source locators
- append-only extraction and processing history
- observation/lead persistence that requires evidence references
- deterministic trace from derived observation back to source

### Corpus watcher — M1 complete

- versioned source manifests
- repeated HTTP source checks
- `new`, `unchanged`, `changed`, and `unavailable` states
- response provenance including HTTP status, Content-Type, ETag, and Last-Modified
- prior-byte preservation
- append-only visit chronology
- correct `A -> B -> A` reversion semantics
- explicit sequence-gap primitives
- bounded indirect fetch strategies for stable publisher APIs that return short-lived transport URLs
- CivicClerk file acquisition that keeps the stable file API as source identity and never persists signed blob query tokens

### Progressive extraction — M2 complete

- native PDF/text/HTML/JSON/XML extraction
- visible-text HTML extraction that excludes script/style/template content
- stable page/row evidence identities
- preferred extraction selected by quality without deleting prior attempts
- optional OCR escalation
- low-quality review queue
- streaming CSV and XLSX evidence
- formulas preserved but never locally evaluated

### Search & retrieval — M3 complete and real-corpus validated

- disposable SQLite FTS5 index over preferred evidence
- deterministic lexical query normalization
- BM25 ranking
- exact publisher-native identifier lookup
- versioned retrieval benchmark format
- hit-rate / target-recall / provenance-validity metrics
- deterministic structured index for:
  - explicit monetary values in prose
  - semantically named monetary spreadsheet fields
  - dates
  - identifiers in semantically named spreadsheet fields
- range queries for amounts and dates
- exact content-identifier lookup
- semantic/vector retrieval explicitly deferred until a measured lexical/structured failure class justifies it

### Source discovery — implemented and live-validated

- versioned `proofline-discovery-plan/v1` plans
- official discovery pages preserved before link interpretation
- bounded CivicEngage Agenda Center adapter
- category/year/format filtering
- published `Previous Versions` listing discovery
- publisher-linked `ArchivedAgenda` enumeration
- bounded official Calendar → CivicClerk discovery adapter
- stable CivicClerk event/file identities derived from preserved publisher pages and metadata rather than hardcoded IDs
- deterministic generated watch manifests
- `proofline discover`

See [docs/DISCOVERY.md](docs/DISCOVERY.md).

### Provenance-gated version analysis — implemented and live-validated

- append-only `historical_version_of` source relations backed by preserved publisher version-listing artifacts
- chronology-safe latest-artifact resolution, including `A -> B -> A` source reversions
- deterministic artifact version comparator
- Gold observation IDs tied to the exact preferred Silver extraction fingerprint used for analysis
- blank/empty Silver evidence is skipped rather than interpreted as deletion
- `proofline analyze-versions`
- `proofline sync` = discover → watch/ingest → analyze publisher-backed versions → rebuild indexes
- `proofline trace` includes both evidence and the source relation that authorized a version observation

## Current CLI surface

```bash
proofline ingest <path>
proofline status
proofline trace <observation-id>

proofline discover <plan.json>
proofline sync <plan.json>
proofline analyze-versions
proofline watch <manifest>
proofline changes

proofline review
proofline extract <artifact-id> --ocr tesseract

proofline index
proofline search "terms"
proofline lookup <publisher-native-id>
proofline amounts --min 250000 --max 500000
proofline dates --from 2026-01-01 --to 2026-12-31
proofline identifier C-001
proofline evaluate <suite.json> --k 5
```

## What is measured

### Synthetic/integration corpus

The generated difficult corpus gives Proofline known evidence targets across born-digital PDFs, image-only scans, corruption, duplicate bytes, revisions, conflicting CSV records, and a formula-bearing workbook.

The retrieval test suite asserts 100% hit rate, target recall, and provenance validity for its current lexical sanity cases. Structured-search tests additionally verify that:

- an `amount` spreadsheet field can be queried numerically even when it contains no currency symbol;
- prose numbers are not automatically treated as money unless explicit currency syntax is present;
- recognized source dates normalize to ISO dates;
- query date ranges require unambiguous `YYYY-MM-DD` boundaries;
- identifiers are extracted only from semantically identified fields rather than guessed from every token;
- serialized spreadsheet rows do not create duplicate prose facts from their own JSON representation.

### R0 Canton 2026 live corpus

The August 19, 2026 GitHub Actions validation run rebuilt the corpus from official public sources with no hand-maintained Council file list.

Measured final-corpus state from that run:

- **61 final discovered meeting resources**
- **0 unavailable final-resource downloads**
- **16 City Council Agenda PDFs** discovered through the official Canton Calendar → CivicClerk chain
- **75 City Council page evidence units, 75/75 nonblank**
- roughly **148,000 extracted City Council characters**
- **174 total evidence units**, of which **172** entered the lexical index
- **982 structured facts** overall
- **331 structured City Council facts** (282 money, 49 date)
- **2 review-queue items**, both Board of Control pages; no City Council page remained in review
- **0 City Council AgendaCenter wrapper records** in the final corpus

The same live sync executed provenance-gated version analysis and produced:

- **11 publisher-backed `historical_version_of` relations**
- **7 substantive version comparisons**
- **7 new version-change observations**
- **4 relations skipped as `same_artifact`**
- **0 detector failures**

These counts are a measured R0 snapshot, not contractual corpus sizes. Public publishers can add, remove, or revise records.

## Validation authority

GitHub Actions is currently the execution authority for full repository tests plus live-network R0 validation. The R0 workflow now fails if:

- the Council discovery path falls below a conservative resource floor;
- a final resource is unavailable;
- Council page evidence becomes blank/title-only again;
- extracted Council text or structured facts collapse below conservative floors;
- the known blank CivicEngage Council wrappers re-enter the final corpus;
- `sync` omits `version_analysis`;
- no publisher-backed historical version relation is derived;
- version analysis reports a deterministic detector failure.

## Deliberately deferred

### Semantic/vector retrieval

Not justified yet.

The current synthetic and R0 work has not demonstrated a repeatable evidence target that deterministic lexical/structured retrieval consistently misses badly enough to justify the additional index/model complexity.

### LLM-generated answers

Also deferred.

The immediate problem is reliable evidence discovery, comparison, provenance, and lead triage—not fluent narrative generation.

## Active experiment — R0 Canton 2026

See [experiments/canton-2026/README.md](experiments/canton-2026/README.md) and GitHub Issue #5.

Current source policy:

- **Board of Control** — official CivicEngage Agenda Center PDFs plus publisher `Previous Versions` / `ArchivedAgenda` history.
- **City Council** — official Canton Calendar event pages → publisher-linked CivicClerk event metadata → published Agenda files.
- canonical meeting evidence remains page-level PDF evidence; discovery/supporting HTML/JSON is preserved separately as provenance.

The product-level question remains:

> Can Proofline ingest this real corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected?

A successful result does **not** require misconduct. A discrepancy that has a routine explanation is still useful if Proofline can show why it surfaced, preserve the ordinary explanation when found, and provide the exact source evidence a human should inspect.

## Human-input threshold

Development should continue without product-owner input while choices are implementation-reversible and governed by the existing architecture.

Explicit human input becomes necessary when a decision materially changes one of these:

- public accusation or publication policy;
- privacy/redaction policy for real people;
- source-selection priorities where editorial judgment matters;
- acceptable false-positive/false-negative tradeoffs for lead surfacing;
- external deployment, credentials, paid infrastructure, or legal terms;
- irreversible data publication or outreach to a person/organization.

Until one of those thresholds is reached, implementation can continue autonomously.
