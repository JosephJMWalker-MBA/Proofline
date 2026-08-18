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

### Progressive extraction — M2 complete

- native PDF/text/JSON/XML extraction
- stable page/row evidence identities
- preferred extraction selected by quality without deleting prior attempts
- optional OCR escalation
- low-quality review queue
- streaming CSV and XLSX evidence
- formulas preserved but never locally evaluated

### Search & retrieval — M3 in progress

- disposable SQLite FTS5 index over preferred evidence
- deterministic lexical query normalization
- BM25 ranking
- exact publisher-native identifier lookup
- versioned retrieval benchmark format
- hit-rate / target-recall / provenance-validity metrics
- deterministic structured index for:
  - monetary values
  - dates
  - identifiers in semantically named spreadsheet fields
- range queries for amounts and dates
- exact content-identifier lookup

## Current CLI surface

```bash
proofline ingest <path>
proofline status
proofline trace <observation-id>

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

The generated difficult corpus currently gives Proofline known evidence targets across born-digital PDFs, image-only scans, corruption, duplicate bytes, revisions, conflicting CSV records, and a formula-bearing workbook.

The retrieval test suite asserts 100% hit rate, target recall, and provenance validity for its current three lexical sanity cases. These are **unit/integration benchmark assertions**, not evidence that lexical retrieval is sufficient for real investigative corpora.

Structured-search tests assert that:

- an `amount` spreadsheet field can be queried numerically even when it contains no currency symbol;
- prose numbers are not automatically treated as money unless explicit currency syntax is present;
- recognized source dates normalize to ISO dates;
- query date ranges require unambiguous `YYYY-MM-DD` boundaries;
- identifiers are extracted only from semantically identified fields rather than guessed from every token.

## Validation caveat

The repository contains GitHub Actions pytest CI. The ChatGPT execution environment currently cannot resolve `github.com` for a local clone, so the newest commits have not been independently executed inside that environment. Do not interpret implementation claims as a substitute for passing CI.

## Deliberately deferred

### Semantic/vector retrieval

Not justified yet.

The current synthetic benchmark does not demonstrate a repeatable lexical failure class. Proofline will add semantic retrieval only after a real or expanded evaluation suite shows evidence targets that deterministic lexical/structured retrieval consistently misses.

### LLM-generated answers

Also deferred.

The immediate problem is reliable evidence discovery and provenance, not fluent narrative generation.

## Next experiment — real public records

The next product-level question is no longer whether the architecture can represent evidence.

It is:

> Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected?

A successful result does **not** require misconduct. A discrepancy that has a routine explanation is still a successful investigative lead if Proofline can show why it surfaced and provide the exact source evidence a human should inspect.

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
