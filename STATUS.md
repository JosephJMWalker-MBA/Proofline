# Proofline — Live Status

This file is the current implementation and validation record for Proofline.

## Current milestone state

Proofline now has a validated end-to-end public-record path:

```text
official publisher sources
→ immutable Bronze artifacts
→ page-level Silver evidence
→ lexical + structured retrieval
→ deterministic source/version analysis
→ stable agenda-item segments
→ bounded recurrence candidates
→ evidence-local recurrence packets
→ selective Gold candidate observations
→ immutable candidate leads
→ explicit append-only human review
→ durable version-controlled review receipts
```

The first real-corpus experiment, **R0 Canton 2026**, has met its success criterion.

## Implemented

### Evidence core

- immutable SHA-256 source artifacts
- stable evidence units with human-inspectable locators
- append-only extraction and processing history
- deterministic observation/evidence traceability
- evidence-backed immutable lead packets

### Watcher and source provenance

- versioned source manifests
- `new`, `unchanged`, `changed`, and `unavailable` watcher states
- append-only visit chronology
- correct `A → B → A` reversion semantics
- prior-byte preservation
- exact watcher `check_id` provenance for watcher-authorized observations
- publisher-backed `historical_version_of` relations
- rotating signed transport URLs separated from canonical source identity

### Extraction and retrieval

- native PDF/text/HTML/JSON/XML extraction
- page/row evidence identities
- progressive OCR escalation
- extraction quality measurement and review queue
- Unicode-aware substantive-Silver gate before Gold promotion
- SQLite FTS5 lexical retrieval
- deterministic structured indexing for money, dates, and explicit identifiers
- amount/date range queries
- retrieval evaluation harness with provenance checks

Semantic/vector retrieval remains deferred until measured lexical/structured misses justify it.

### Canton discovery

Board of Control:

- official CivicEngage Agenda Center
- `Previous Versions` pages
- publisher-linked `ArchivedAgenda` files

City Council:

- official Canton Calendar
- CivicClerk event metadata
- stable CivicClerk meeting-file source URI
- publisher-signed blob used only as temporary transport

Canonical meeting evidence remains page-level PDF evidence. Discovery HTML/JSON is preserved separately as provenance rather than counted as independent corroboration.

### Version and watcher analysis

- deterministic version comparator
- publisher-version and watcher-chronology authorization paths kept distinct
- same-artifact pairs do not manufacture changes
- blank/whitespace-only Silver cannot masquerade as a substantive deletion/change
- observation identities bind to the exact evidence/extraction inputs used
- `proofline analyze-versions`
- `proofline analyze-watch-changes`
- `proofline trace` exposes evidence plus source relations, watcher visits, and detector context

### Agenda-item recurrence

- deterministic source-profile segmentation with exact character spans
- stable segment IDs across rebuilds
- version-family suppression before recurrence scoring
- inverted token-shingle candidate generation rather than O(n²) all-pairs comparison
- exact Jaccard scoring for bounded candidates
- deterministic recurrence clusters with stable IDs
- recurrence evidence packets containing only structured facts inside the exact segment span
- explicit common-vs-varying fact sets

Recurrence packets remain descriptive below Gold unless a detector policy explicitly promotes them.

### R0.3 Gold candidate policy

Detector: `recurrence_fact_variation/v1`.

Promotion requires:

- multiple publisher-backed source families;
- multiple evidence units;
- structured facts in every occurrence;
- known preferred-extraction quality at/above threshold;
- at least one structured value common to all occurrences;
- at least one structured value whose presence varies across occurrences.

Safeguards:

- recurrence alone is insufficient;
- missing/low-quality extraction cannot masquerade as a change;
- no chronology, causation, materiality, suspiciousness, or field-equivalence inference;
- possible ordinary explanations are mandatory;
- questions worth asking are mandatory;
- immediate reruns are idempotent.

### R0.4 lead lifecycle

- eligible candidate observations package deterministically into immutable `Lead` packets
- packet retains exact observation/evidence references, questions, and possible ordinary explanations
- editorial/scalar scores remain unset in R0
- lead rows and lead→observation/evidence links are DB-enforced immutable
- human disposition is append-only `lead_review_events`
- current status is derived from review history; the original lead packet is not rewritten
- `published` is excluded from the R0 review interface
- version-controlled review receipts use schema `proofline-lead-review/v1`
- applying the same review receipt is idempotent
- a review receipt is bound to the exact deterministic lead ID and must not silently transfer to a different future lead

See [docs/REVIEW_RECORDS.md](docs/REVIEW_RECORDS.md).

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
proofline identifier <identifier>
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
proofline review-lead <lead-id> \
  --status triaged|investigating|explained|corroborated|rejected|archived \
  --reviewer "..." \
  --rationale "..."
```

Durable review receipts are loaded/applied through `proofline.review_records`; the R0 live workflow uses that module to reconstruct the approved human review on every clean validation build.

## R0 Canton 2026 — measured snapshot

Validated live runs have produced approximately:

- **61 final discovered meeting resources**
- **0 unavailable final-resource downloads**
- **16 City Council Agenda PDFs**
- **75/75 nonblank City Council page evidence units**
- roughly **148,000 City Council extracted characters**
- **174 evidence units**, **172** lexical-searchable
- **982 structured facts**
- **2 review-queue items**, both Board of Control
- **0** dead City Council CivicEngage wrapper records in the final corpus

Version-analysis snapshot:

- **11** publisher-backed `historical_version_of` relations
- **7** substantive comparisons
- **7** version-change observations
- **4** same-artifact relations skipped
- **0** deterministic detector failures

Agenda-item/recurrence snapshot:

- **553** agenda-item segments
  - 138 Board of Control
  - 415 City Council
- **0** evidence-span mismatches
- Board recurrence search: **9,453 possible pairs → 2,188 exact comparisons**
- **5** near-duplicate edges
- **3** recurrence clusters
- stable segment and recurrence identities across identical rebuilds

These counts are measured snapshots, not contractual corpus sizes.

## First non-preselected machine candidate

The live recurrence detector examined all three Board recurrence clusters and promoted exactly **one** while leaving the other two below Gold.

### ECDI / Ordinance 60/2023 / $185,000 CDBG funds

Common evidence-local structured facts included:

- `$185,000`
- `2026-07-31`

Varying date facts included:

- `2026-04-13`
- `2026-10-31`

One public record extends the expenditure deadline from **April 13 → July 31, 2026**; a later record extends it from **July 31 → October 31, 2026**.

Proofline surfaced the pattern without a detector or CI assertion naming ECDI.

The Motorola and Versaterm recurrence groups remained below Gold because their evidence-local structured facts were unchanged.

## First real lead — human disposition recorded

Deterministic lead:

```text
lead:3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c
```

Human review:

- reviewer: **Joseph Walker**
- disposition: **explained**
- review time: **2026-08-19T17:14:00+00:00**
- immutable packet status: `candidate`
- derived current status: `explained`

Rationale:

> The underlying Board of Control records describe sequential expenditure-deadline amendments. The recurring $185,000 amount and July 31 handoff are consistent with continuity of the same administrative matter; the evidence currently provides an ordinary explanation for why Proofline surfaced the changing dates. No evidence of misconduct is inferred.

Durable review receipt:

`experiments/canton-2026/reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json`

The live validation workflow rebuilds the corpus from official sources, regenerates this exact lead ID, first proves machine-only state remains `candidate`, applies the version-controlled human receipt, and then proves the derived disposition is `explained`. Reapplying the receipt creates no duplicate event.

## Important negative findings

### Board ordinance numbers are not matter identity

The same `Ordinance ###/####` anchor can occur across unrelated departments, vendors, transactions, and meetings. It is not safe as a matter key.

### Project ID alone is not transaction identity

A project can contain construction, engineering, administration, multiple counterparties, and multiple change-order relationships. A future conflicting-value detector needs an explicit **matter-key contract** rather than loose identifier equality.

### Arbitrary dollar amounts are not one comparable population

Contract total, annual fee, amendment amount, grant amount, engineering fee, and administrative amount are semantically distinct. Numeric outlier detection requires field-role normalization and an explicitly comparable population first.

These are epistemic gates discovered from real records, not implementation shortcuts.

## Validation authority

GitHub Actions is the execution authority for the full repository suite and live-network R0 gates.

Current regression gates cover:

- official-source acquisition and substantive Council evidence;
- source/version provenance;
- stable segment/recurrence identity;
- bounded candidate generation;
- fact-span containment;
- selective Gold promotion;
- candidate/lead idempotence;
- immutable lead packets;
- machine processing stopping before human disposition;
- durable human review reconstruction;
- exact lead-ID binding for a review receipt;
- no duplicate event on review-receipt reapplication;
- `published` remaining unavailable through R0 review.

## R0 result

R0 asked:

> Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected?

**Yes.**

It also demonstrated the more important epistemic behavior: a machine-selected pattern can be investigated and **explained by ordinary public-record context** rather than rewarded for sounding suspicious.

See [experiments/canton-2026/README.md](experiments/canton-2026/README.md) and GitHub Issue #5.

## Next work

R0 is complete. Future detector work should proceed only after the required identity/comparison semantics are defined:

- explicit matter-key contract for conflicting-value analysis;
- financial field-role normalization before numeric outlier analysis;
- broader real-corpus retrieval benchmark coverage;
- semantic retrieval only if deterministic retrieval demonstrates a measured failure class.

Public accusation, outreach, publication, privacy-policy changes affecting real people, paid external deployment, or irreversible publication remain explicit human/product-owner decisions.
