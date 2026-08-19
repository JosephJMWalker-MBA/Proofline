# Proofline — Live Status

This file answers four questions:

1. What is implemented **right now**?
2. What has actually been **measured or validated**?
3. What did the first real-corpus experiment discover?
4. Where does autonomous machine processing stop and human judgment begin?

## Implemented

### Evidence core — M0 complete

- immutable SHA-256 source artifacts
- stable evidence units with source locators
- append-only extraction and processing history
- observation/lead persistence that requires evidence references
- deterministic trace from derived observations back to source evidence

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
- CivicClerk acquisition that keeps the stable file API as source identity and never persists signed blob query tokens

### Progressive extraction — M2 complete

- native PDF/text/HTML/JSON/XML extraction
- visible-text HTML extraction excluding script/style/template content
- stable page/row evidence identities
- preferred extraction selected by quality without deleting prior attempts
- optional OCR escalation
- low-quality review queue
- streaming CSV/XLSX evidence
- formulas preserved but never locally evaluated
- shared Unicode-aware substantive-Silver gate before Gold promotion

### Search & retrieval — M3 complete and real-corpus validated

- disposable SQLite FTS5 index over preferred evidence
- deterministic lexical normalization + BM25 ranking
- exact publisher-native identifier lookup
- versioned retrieval benchmark format
- hit-rate / target-recall / provenance-validity metrics
- deterministic structured indexing for:
  - explicit monetary values in prose
  - semantically named monetary spreadsheet fields
  - dates
  - identifiers in semantically named spreadsheet fields
- amount/date range queries
- exact content-identifier lookup
- semantic/vector retrieval deferred until measured lexical/structured failure justifies it

### Source discovery — implemented and live-validated

- versioned `proofline-discovery-plan/v1` plans
- official discovery/supporting pages preserved before link interpretation
- bounded CivicEngage Board of Control adapter
- publisher `Previous Versions` + `ArchivedAgenda` history
- bounded official Canton Calendar → CivicClerk City Council adapter
- stable CivicClerk event/file identities derived from preserved publisher pages/metadata rather than hardcoded IDs
- deterministic generated watch manifests
- `proofline discover`

See [docs/DISCOVERY.md](docs/DISCOVERY.md).

### Provenance-gated version and watcher analysis — implemented and live-validated

- append-only `historical_version_of` relations backed by preserved publisher version-listing artifacts
- deterministic artifact version comparator
- Gold observation identity tied to exact preferred-Silver inputs
- blank/whitespace-only Silver is skipped rather than interpreted as deletion/change
- watcher `changed` visits are a second explicit Gold authorization path
- exact watcher `check_id` retained for source-change observations
- `A -> B -> A` can produce two directional chronology observations rather than collapsing seen-before bytes
- `proofline analyze-versions`
- `proofline analyze-watch-changes`
- `proofline sync` = discover → watch/ingest → watcher-change analysis → publisher-version analysis → rebuild indexes
- `proofline trace` exposes evidence plus any authorizing source relation, watcher visit, or detector context

### Agenda-item segmentation and recurrence — implemented and live-validated

- deterministic source-profile segmentation with exact evidence character spans
- stable segment IDs across identical rebuilds; random build UUID is metadata only
- publisher-backed version-family connected components
- inverted token-shingle candidate generation rather than O(n²) all-pairs comparison
- exact Jaccard scoring for bounded candidates
- same-version-family suppression before recurrence scoring
- deterministic single-linkage recurrence clusters
- stable recurrence cluster IDs across identical rebuilds
- evidence-local recurrence packets containing only structured facts physically inside each segment span
- complete fact retrieval without hidden presentation truncation
- explicit common-vs-varying structured-value sets
- recurrence packets remain descriptive inspection aids below Gold

### R0.3 candidate observation policy — implemented and live-validated

Detector: `recurrence_fact_variation/v1`.

A recurrence becomes a Gold candidate observation only when it:

- spans multiple publisher-backed source families;
- spans multiple evidence units;
- has structured facts in every occurrence;
- has known preferred-extraction quality at/above the configured threshold;
- retains at least one structured fact value common to all occurrences;
- has at least one structured fact value whose presence varies across occurrences.

Additional safeguards:

- recurrence alone is not promoted;
- no chronology/field-equivalence/causation/materiality inference;
- no scalar suspiciousness score;
- possible ordinary explanations are mandatory;
- questions worth asking are mandatory;
- exact detector/family/input fingerprint is preserved append-only;
- immediate reruns are idempotent;
- `proofline analyze-candidates` exposes the policy.

### R0.4 candidate lead lifecycle — implemented and live-validated

- eligible candidate observations package deterministically into immutable `Lead` packets
- lead packet retains observation IDs, exact evidence references, questions worth asking, and possible ordinary explanations
- all editorial/scalar score fields remain unset in R0
- lead rows, lead→observation links, and lead→evidence links are DB-enforced immutable
- human review/disposition is represented by append-only `lead_review_events`
- current disposition is derived from review history; the original packet is never rewritten
- machine-safe packaging stops at `candidate`
- live R0 validation creates **zero human review events**
- `published` is deliberately unavailable through the R0 review API/CLI

Commands:

```bash
proofline package-leads
proofline lead <lead-id>
proofline review-lead <lead-id> \
  --status triaged|investigating|explained|corroborated|rejected|archived \
  --reviewer "..." \
  --rationale "..."
```

`review-lead` is an explicit human action. The machine-safe pipeline does not call it.

## Current CLI surface

```bash
proofline ingest <path>
proofline status
proofline trace <observation-id>

proofline discover <plan.json>
proofline sync <plan.json>
proofline analyze-watch-changes
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

proofline segment <segment-plan.json>
proofline segment-anchor <anchor>
proofline repeated-segments
proofline near-segments
proofline recurrence-clusters
proofline recurrence-packets
proofline analyze-candidates

proofline package-leads
proofline lead <lead-id>
proofline review-lead <lead-id> --status ... --reviewer ... --rationale ...
```

## What is measured

### Synthetic/integration corpus

The generated difficult corpus exercises born-digital PDFs, image-only scans, corruption, duplicate bytes, revisions, conflicting structured records, spreadsheet formulas, source reversions, packet span contamination, and lead immutability/review history.

Current tests cover, among other things:

- extraction/quality escalation;
- source chronology and `A -> B -> A`;
- lexical/structured retrieval provenance;
- stable segment/cluster identities;
- cross-source byte dedup with distinct publisher contexts;
- evidence-local recurrence fact containment;
- selective recurrence Gold promotion;
- idempotent observation + lead generation;
- immutable lead packets;
- append-only human review events;
- explicit rejection of `published` through the R0 review interface.

### R0 Canton 2026 live corpus

Validated GitHub Actions runs rebuild the corpus from official public sources without a hand-maintained Council file list.

Measured R0 state has included approximately:

- **61 final discovered meeting resources**
- **0 unavailable final-resource downloads**
- **16 City Council Agenda PDFs** through official Canton Calendar → CivicClerk
- **75/75 nonblank City Council page evidence units**
- roughly **148,000 extracted City Council characters**
- **174 total evidence units**, **172** lexical-searchable
- **982 structured facts**
- **2 review-queue items**, both Board of Control
- **0** dead City Council CivicEngage wrappers in the final corpus

Version provenance snapshot:

- **11** publisher-backed `historical_version_of` relations
- **7** substantive version comparisons
- **7** version-change observations
- **4** same-artifact relations skipped
- **0** deterministic detector failures

Agenda-item/recurrence snapshot:

- **553** agenda-item segments
  - 138 Board
  - 415 Council
- **0** evidence-span mismatches
- Board candidate generation: **9,453 possible pairs → 2,188 exact comparisons**
- **5** near-duplicate edges
- **3** recurrence clusters
- exact segment/cluster IDs stable across identical rebuilds

## First non-preselected machine candidate

The live R0 recurrence detector examined all three Board recurrence clusters and promoted exactly **one** to Gold while leaving the other two below Gold.

### ECDI / Ordinance 60/2023 / $185,000

Common evidence-local structured facts included:

- `$185,000`
- `2026-07-31`

Varying date facts included:

- `2026-04-13`
- `2026-10-31`

The source language shows a sequence in which one agenda extends the expenditure deadline from April 13 to July 31 and a later agenda extends it from July 31 to October 31.

Proofline surfaced this pattern without a test or detector naming ECDI.

The Motorola and Versaterm recurrence groups remained below Gold because their evidence-local structured facts did not vary.

### Interpretation

The obvious ordinary explanation is sequential deadline amendments. R0 treats that as a successful outcome: the machine selected the pattern, preserved the evidence, and the evidence itself provides a benign explanation.

The software does not convert that explanation into a human disposition automatically.

## First real candidate lead

The live lead validation produced one deterministic lead for the one eligible candidate observation:

```text
lead:3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c
```

Current machine-safe state:

- immutable packet: created
- evidence/questions/ordinary explanations: retained
- editorial score fields: unset
- current disposition: **candidate**
- human review events: **0**

An immediate packaging rerun produced the same lead ID and created no duplicate.

## Important negative findings / deferred detectors

### Board ordinance numbers are not matter identity

Do **not** infer that the same `Ordinance ###/####` anchor represents the same underlying matter. The real corpus contains the same ordinance anchor across unrelated departments, vendors, transactions, and meetings.

### Project ID alone is not transaction identity

Project identifiers such as `GP####` can span construction, engineering, administration, vendors, and multiple change-order relationships. Even `project ID + change-order number` can be insufficient without counterparty/transaction-role context.

A future conflicting-value detector therefore requires an explicit **matter-key contract** rather than loose identifier equality.

### Arbitrary dollar amounts are not one comparable population

Contract total, annual fee, amendment amount, grant amount, engineering fee, and administrative amount are semantically different fields. A defensible numeric-outlier detector requires field-role normalization and an explicitly comparable population first.

These are epistemic gates discovered from real data, not missing shortcuts.

## Validation authority

GitHub Actions is the execution authority for the full repository suite plus live-network R0 gates.

Current live workflows fail on regressions including:

- Council discovery/content collapse;
- unavailable final resources;
- reintroduction of blank City Council wrappers;
- missing publisher-backed version analysis;
- deterministic detector failures;
- unstable segment/cluster identities;
- recurrence candidate generation regressing toward all-pairs comparison;
- fact-span leakage;
- nonselective Gold promotion;
- duplicate candidate observations;
- lead packaging that changes IDs on rerun;
- machine-created human review events;
- machine lead packaging crossing beyond `candidate`;
- R0 review CLI exposing `published`.

## Deliberately deferred

### Semantic/vector retrieval

Not justified yet. Deterministic lexical/structured retrieval has not shown a repeatable failure class severe enough to justify extra model/index complexity.

### LLM-generated investigative narratives

Also deferred. Evidence discovery, comparison, provenance, candidate selection, and human-review discipline come first.

### Public lead publication

Explicitly outside the current machine-safe path.

## R0 result

R0 asked:

> Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected?

**Yes.**

More importantly, it did so while demonstrating that a surfaced pattern can have an ordinary explanation and while preserving the evidence needed to reach that explanation.

See [experiments/canton-2026/README.md](experiments/canton-2026/README.md) and GitHub Issue #5.

## Human-input threshold — current state

Autonomous implementation may continue for reversible architecture, parser, retrieval, detector, and internal workflow work.

For the **first real candidate lead**, however, the next state-changing action is now a human review decision.

The software will not decide whether the real lead should be marked:

- `triaged`
- `investigating`
- `explained`
- `corroborated`
- `rejected`
- `archived`

A review event requires a named reviewer and rationale.

Publication remains a separate, higher threshold and is not available through the R0 review interface.
