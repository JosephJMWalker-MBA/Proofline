# Proofline Roadmap

This roadmap separates **platform capability milestones** from the **R0/R1 empirical validation program**. A capability may be implemented before it is broadly validated, and a successful bounded experiment does not imply universal completeness.

For the most detailed current implementation and validation record, see [STATUS.md](STATUS.md).

## Milestone 0 — Evidence Core ✅

**Status: complete.**

Goal: prove source integrity and evidence traceability before adding sophisticated AI.

Delivered:

- [x] immutable artifact identity using SHA-256
- [x] source and retrieval metadata
- [x] page/row/logical evidence units
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

## Milestone 2 — Progressive Extraction ✅

**Status: complete.**

Goal: reliably turn heterogeneous records into stable evidence units while controlling extraction cost.

Delivered:

- [x] native PDF/text/HTML/JSON/XML extraction
- [x] Unicode-aware per-unit quality heuristics
- [x] software/model version metadata for extraction attempts
- [x] append-only producer upgrades even when output text is identical
- [x] optional OCR backend interface
- [x] PyMuPDF/Tesseract OCR backend without a hard Tesseract requirement
- [x] threshold-gated OCR escalation
- [x] retained native extraction alongside OCR attempts
- [x] preferred-extraction rule that resists later quality regression
- [x] `proofline review` review queue
- [x] streaming CSV row evidence
- [x] streaming XLSX/XLSM row evidence with formulas preserved, not evaluated
- [x] difficult fixture corpus with scans, corruption, structured conflicts, and formula workbook
- [x] extraction/review documentation

Exit criterion:

> Every extracted evidence unit has a stable source locator, records how each extraction attempt was produced, exposes whether the preferred extraction meets the configured quality threshold, and can be reprocessed without rewriting prior evidence history.

See [docs/EXTRACTION.md](docs/EXTRACTION.md).

## Milestone 3 — Search & Retrieval Evaluation ✅ for deterministic retrieval

**Status: deterministic lexical/structured scope implemented and real-corpus validated. Semantic/vector retrieval remains intentionally deferred.**

Goal: find the right evidence, not merely generate plausible answers.

Delivered:

- [x] SQLite FTS5 lexical retrieval
- [x] publisher-native identifier lookup
- [x] structured identifier/date/value search where source semantics justify the field
- [x] deliberately difficult generated retrieval fixtures
- [x] research-question evaluation format
- [x] exact evidence-target and provenance checks
- [x] retrieval recall / expectation metrics
- [x] scorable reporting that separates target drift from retrieval failure
- [x] frozen real-corpus Canton benchmark
- [x] retrieval-blind frozen Akron transfer benchmark
- [ ] semantic/vector retrieval experiment

The optional semantic/vector experiment is not blocked by implementation effort; it is blocked by the project's complexity gate. Neither frozen real-corpus benchmark has exposed a deterministic retrieval failure class that justifies adding vector infrastructure.

Exit criterion for the current deterministic scope:

> Retrieval quality is measured against known evidence targets, and added retrieval complexity is justified by measured failures of simpler methods.

**Current result:** satisfied for the bounded Canton and Akron benchmarks. This is not a claim of universal retrieval completeness.

See [docs/RETRIEVAL.md](docs/RETRIEVAL.md) and [docs/RETRIEVAL_EVALUATION.md](docs/RETRIEVAL_EVALUATION.md).

## Milestone 4 — Entity & Relationship Layer ◐

**Status: partially implemented. Broad entity resolution remains future work.**

Goal: support cross-record investigation without creating guilt-by-association machinery.

Implemented foundations:

- [x] explicit source/version relationships tied to preserved provenance
- [x] watcher chronology distinct from artifact identity
- [x] policy-scoped matter identity for bounded Canton comparisons
- [x] explicit separation of resolved / ambiguous / insufficient identity
- [x] financial field-role semantics gated by resolved matter identity
- [x] relationship provenance used to authorize specific downstream comparisons

Still future or incomplete:

- [ ] general entity mentions tied to evidence units
- [ ] alias system across heterogeneous source families
- [ ] probabilistic entity resolution
- [ ] generalized source-independence graph
- [ ] entity timeline and neighbor queries
- [ ] user-facing distinction among explicit, deterministic, co-occurrence, and probabilistic edges across the full system

Current discipline:

> A matter key or relationship is permission to perform a bounded comparison under a stated policy, not a universal declaration that two records refer to the same real-world entity.

Exit criterion remains:

> Every relationship shown to a user distinguishes explicit evidence, deterministic derivation, co-occurrence, and probabilistic inference.

## Milestone 5 — Detector Framework ◐

**Status: actively implemented for several bounded deterministic detectors; broader detector catalog remains future work.**

Goal: surface reproducible anomalies and contradictions without converting pattern detection into accusation.

Implemented / validated paths include:

- [x] publisher-backed version differences
- [x] watcher-authorized source changes
- [x] recurrence / fact-variation candidate analysis
- [x] bounded financial-conflict comparison over resolved matter + assigned field role
- [x] evidence references, method identity, and deterministic detector provenance
- [x] acceptance of valid negative results without retuning to manufacture findings

Still future or incomplete:

- [ ] generalized identifier-sequence anomaly detector across publisher families
- [ ] repeated-address/contact detector across resolved entities
- [ ] generalized unusual amendment/value-change detector
- [ ] entity appearance/disappearance detector across resolved identities
- [ ] generalized cross-source presence/absence discrepancy detector
- [ ] calibrated uncertainty model across detector families

Exit criterion:

> Each detector produces an observation with method, evidence, uncertainty/limits, and enough provenance for independent reproduction.

The current detector families satisfy this boundary in their implemented scopes; the milestone is not complete as a general detector framework.

## Milestone 6 — Lead Desk ◐

**Status: core lead identity, evidence packaging, lifecycle, and append-only human review are implemented; richer desk/product behavior remains future work.**

Goal: convert observations into investigation-ready packets for human review.

Implemented foundations:

- [x] deterministic candidate-lead packaging
- [x] evidence-backed immutable lead identity
- [x] exact lead/evidence traceability
- [x] append-only disposition history
- [x] reviewer identity and rationale
- [x] lifecycle states for triage / investigation / explanation / corroboration / rejection / archival
- [x] protection against silently transferring a review when deterministic derivation identity changes
- [x] benign-explanation discipline demonstrated in the R0 Canton lead

Still future or incomplete:

- [ ] generalized lead-scoring dimensions such as novelty / anomaly / corroboration / source quality / uncertainty
- [ ] richer questions-worth-asking generation
- [ ] full corroboration workflow with explicit source-independence accounting
- [ ] reporter/editor-oriented review interface
- [ ] publication-oriented workflow and legal/editorial handoff

Exit criterion:

> A journalist can understand why a lead surfaced, inspect its evidence, reject it, explain it, or pursue it without trusting an opaque model conclusion.

The current CLI/review-record path demonstrates this boundary for the validated R0 workflow, but the broader Lead Desk product is not complete.

See [docs/REVIEW_RECORDS.md](docs/REVIEW_RECORDS.md).

## Milestone 7 — LLM / MCP Research Interface

**Status: future.**

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

This layer remains intentionally downstream of deterministic evidence, retrieval, and review contracts.

# Empirical validation program

The R-series validates claims about the platform against bounded real publisher corpora. Results are retained even when they are negative, benign, or expose an invalid earlier assumption.

## R0 — Canton 2026 ✅

**Status: complete.**

Validated that a real municipal corpus can flow through acquisition, reproducible evidence, deterministic analysis, candidate-lead promotion, and explicit human disposition.

The first non-preselected lead was ultimately explained by an ordinary administrative explanation. That outcome remains positive validation of the epistemic workflow rather than a failed attempt to find wrongdoing.

See [experiments/canton-2026/README.md](experiments/canton-2026/README.md).

## R1 — Canton semantic gates ✅ for current bounded policies

**Status: current bounded validations complete.**

Validated:

- canonical-evidence-only retrieval benchmark
- corrected Board segmentation
- conservative matter-key contract
- financial field-role assignment boundaries
- authorized same-matter/same-role financial comparison
- acceptance of a zero-conflict detector result

These policies are source/profile scoped and are not automatically transferable to another publisher.

## R1 — Akron transfer T1–T5 ✅

**Status: complete through T5.**

Validated transfer of the evidence and retrieval architecture to Hyland OnBase Agenda Online with a materially different canonical evidence boundary.

The transfer established publisher-led agenda-item discovery, 1,475 canonical atomic records, and a retrieval-blind frozen benchmark whose first score recovered all explicit positive targets while passing all negative controls.

No measured retrieval failure class currently justifies semantic/vector retrieval.

See [experiments/akron-2026/README.md](experiments/akron-2026/README.md).

## Current R1 edge — Akron supporting documents ◐

**Status: active bounded experiment; not yet an established production capability.**

Current question:

> Can publisher-declared supporting-document relationships be followed and preserved as provenance-bearing evidence without guessing IDs, broad crawling, or silently treating link labels as trustworthy media evidence?

The active experiment should remain bounded to publisher-declared relationships, deterministic sampling, actual response-byte/media validation, and explicit attachment-to-agenda-item provenance.

Only after that contract is validated should richer Akron matter-key, financial-role, recurrence, or detector policies be considered.

## Reference test corpus

The development corpus intentionally includes ugly cases such as:

- born-digital PDF
- scanned PDF
- poor OCR
- multi-column layout
- table
- spreadsheet
- duplicate document
- corrupted artifact
- source revision pair
- conflicting structured values
- formula-bearing workbook

Future fixture extensions may add handwriting, OCR-variant duplicates, audio/transcript pairs, and other modalities when concrete extraction or retrieval work requires them.
