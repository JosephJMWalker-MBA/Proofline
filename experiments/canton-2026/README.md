# R0 — Canton 2026 public-record experiment

## Question

Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was **not manually preselected**?

**Result: yes.**

R0 also demonstrated a more important property: a machine-selected pattern can be inspected and **explained by ordinary public-record context** without the system upgrading it into a claim of wrongdoing.

## Scope

Year:

- 2026

Meeting families:

- Board of Control
- City Council

The corpus is deliberately narrow enough for human audit while still containing longitudinal records, contracts, amendments, public meeting context, monetary values, dates, identifiers, and publisher revision history.

## Official source paths

### Board of Control

Discovery/provenance:

- official Canton CivicEngage Agenda Center
- configured `Board of Control` category
- publisher `Previous Versions` pages
- explicitly linked `ArchivedAgenda` files

Canonical meeting evidence:

- PDF agenda records

### City Council

Discovery/provenance:

1. official Canton Calendar month listings;
2. exact City Council agenda events on the official Canton host;
3. publisher-linked CivicClerk event metadata;
4. published `Agenda` file record;
5. stable CivicClerk meeting-file source URI;
6. short-lived publisher-signed blob used only as transport.

Canonical meeting evidence:

- published CivicClerk Agenda PDFs

No CivicClerk event ID or file ID is hand-maintained in the production discovery plan.

## Evidence policy

### Canonical meeting evidence

PDF meeting records are the primary evidentiary representation because they preserve page-level locators.

HTML, PDF, Packet, or other renderings of the same underlying meeting are **not** counted as independent corroboration merely because they have different URLs.

### Discovery/supporting evidence

Discovery pages and publisher metadata are preserved separately as Bronze provenance before their links/fields are interpreted.

Examples:

- Agenda Center index
- `Previous Versions` listing pages
- Canton Calendar month listings
- Canton Calendar event pages
- CivicClerk event metadata

These artifacts establish why Proofline collected a record without masquerading as another copy of the meeting evidence.

### Revision and chronology evidence

Publisher `Previous Versions` pages can establish explicit `historical_version_of` relations.

Watcher chronology provides a separate source-change authorization path. A stable source URI can therefore preserve `A → B → A` as two chronological change events instead of collapsing the final A because those bytes were seen before.

Neither path establishes suspiciousness, motive, materiality, or impropriety.

Blank/whitespace-only Silver is never interpreted as a substantive deletion/change.

## Procedure

Core acquisition/index cycle:

```bash
proofline sync experiments/canton-2026/source-plan.json
proofline segment experiments/canton-2026/segment-plan.json
```

R0 candidate generation:

```bash
proofline analyze-candidates \
  --rule board-ordinance-items \
  --threshold 0.60 \
  --shingle-size 3 \
  --min-shared-shingles 3 \
  --max-shingle-frequency 64 \
  --min-quality 0.70

proofline package-leads
```

Human review remains a distinct explicit action. The approved first R0 review is persisted as a version-controlled review receipt rather than embedded in acquisition logic.

## Measured live snapshot — August 19, 2026

Validated GitHub Actions runs have produced approximately:

### Final meeting corpus

- **61 final discovered meeting resources**
- **0 unavailable final-resource downloads**
- **16 City Council Agenda PDFs**
- **75 City Council page evidence units, 75/75 nonblank**
- roughly **148,000 extracted City Council characters**
- **174 evidence units overall**
- **172 evidence units in the lexical index**
- **982 structured facts overall**
- **2 low-quality review items**, both Board of Control pages
- **0 dead City Council CivicEngage pointer-wrapper records** in the final corpus

These are measured snapshots, not contractual corpus sizes.

### Version analysis

- **11 publisher-backed `historical_version_of` relations**
- **7 substantive comparisons**
- **7 version-change observations**
- **4 `same_artifact` skips**
- **0 detector failures**

### Agenda-item recurrence

- **553 agenda-item segments**
  - 138 Board of Control
  - 415 City Council
- **0 segment/evidence span mismatches**
- Board recurrence candidate population: **9,453 possible pairs**
- inverted-shingle filtering reduced this to **2,188 exact comparisons**
- **5 near-duplicate edges**
- **3 deterministic recurrence clusters**
- segment and recurrence identities remained stable across identical rebuilds

## First machine-selected candidate

The live detector evaluated all three Board recurrence clusters and promoted exactly **one** to Gold while leaving the other two below Gold.

The selected pattern was not named in CI.

### ECDI / Ordinance 60/2023 / $185,000 CDBG funds

Common evidence-local structured facts included:

- `$185,000`
- `2026-07-31`

Varying dates included:

- `2026-04-13`
- `2026-10-31`

The source language describes sequential expenditure-deadline amendments:

1. one occurrence extends **April 13 → July 31, 2026**;
2. a later occurrence extends **July 31 → October 31, 2026**.

Proofline surfaced the recurrence because stable structured anchors remained while date facts varied. It did not infer chronology, causation, materiality, suspiciousness, or wrongdoing from the fact variation itself.

The Motorola and Versaterm recurrence groups remained below Gold because their evidence-local structured facts were unchanged.

## First real lead

Deterministic lead ID:

```text
lead:3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c
```

Machine-created state before human review:

- immutable packet status: `candidate`
- evidence/questions/ordinary explanations retained
- editorial score fields unset
- review events: `0`

### Human review

Reviewer:

- **Joseph Walker**

Disposition:

- **explained**

Review time:

- `2026-08-19T17:14:00+00:00`

Rationale:

> The underlying Board of Control records describe sequential expenditure-deadline amendments. The recurring $185,000 amount and July 31 handoff are consistent with continuity of the same administrative matter; the evidence currently provides an ordinary explanation for why Proofline surfaced the changing dates. No evidence of misconduct is inferred.

Durable review receipt:

`reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json`

The lead packet itself remains immutable with stored status `candidate`. Its **derived current status is `explained`** because of the append-only human review event.

The live R0 lead workflow rebuilds the corpus from official sources, regenerates the exact deterministic lead ID, proves machine-only processing still stops at `candidate`, applies the version-controlled human review receipt, and proves the derived state is `explained`. Applying the same receipt twice creates only one event.

## Review-record invariant

A human review receipt is bound to the exact deterministic lead ID.

If future detector/evidence changes cause the lead identity to change, validation fails rather than silently transferring the old human judgment to a new evidence packet.

See `docs/REVIEW_RECORDS.md`.

## Real-corpus failures that improved the architecture

### Blank City Council CivicEngage PDF wrappers

The initial CivicEngage City Council PDFs were one-page, zero-text pointer wrappers rather than scans. Blind OCR would have been the wrong response.

### Stale UUID pointer target

The wrapper exposed a machine-readable UUID target, but the direct target was stale/404. Proofline did not loosen crawling rules to invent alternatives.

### Title-only HTML / empty packet rendering

Alternative CivicEngage renderings transported successfully but were non-substantive. R0 CI therefore measures evidence content, not just HTTP success.

### Legacy archive TLS failure

A separate official archive failed strict certificate validation. Proofline did not disable TLS verification; it found a verified official Calendar→CivicClerk source path instead.

### Rotating signed download URL

CivicClerk returns rotating signed blob URLs. Treating those tokens as source identity would create false change events. Proofline keeps the stable publisher file API as canonical source identity and uses signed URLs only as transport.

### Library capability without orchestration

An earlier version-analysis implementation existed as a library but was not actually wired into `sync`. This became a regression lesson: live CI now validates installed CLI boundaries, not just internal modules.

### Whitespace-only Silver gate bug

SQLite's default `TRIM()` does not remove every Unicode/line whitespace case. A chronology fixture exposed the possibility that tab/newline-only extraction could pass a Gold gate. Proofline now uses a shared Unicode-aware substantive-Silver predicate before Gold comparison.

## Negative findings that block naïve future detectors

### Ordinance number is not matter identity

The same Board `Ordinance ###/####` anchor appears across unrelated departments, vendors, contracts, and meetings. A conflicting-value detector cannot safely join records on ordinance number alone.

### Project ID is not transaction identity

A project can include construction, engineering, administration, multiple counterparties, and multiple change-order relationships. Even project ID + change-order number can be insufficient without transaction-role/counterparty semantics.

A future conflicting-value detector needs an explicit **matter-key contract**.

### Agenda dollar amounts are not one comparable population

Contract totals, annual fees, amendment amounts, grant amounts, engineering fees, and administrative amounts are semantically different fields.

A future numeric-outlier detector needs field-role normalization and a documented comparison population before it can make a defensible comparison.

## Success criteria

R0 required that:

1. the corpus can be regenerated from official publisher interfaces without a hand-maintained final URL list;
2. derived observations resolve to stable evidence and source lineage;
3. at least one non-preselected pattern is surfaced reproducibly;
4. a human can inspect the pattern without trusting an LLM-generated narrative;
5. the system preserves plausible ordinary explanations;
6. machine processing stops before human disposition;
7. human disposition is explicit, attributable, append-only, and reproducible.

**R0 meets these criteria.**

## Disposition

R0 is complete.

The first real lead is **explained**, not corroborated wrongdoing, and the explanation is publicly documented with its provenance boundary intact.

Future work should move to separate issues for:

- explicit matter-key semantics;
- financial field-role normalization/comparable populations;
- broader real-corpus retrieval benchmarks;
- semantic retrieval only if deterministic retrieval exposes a measured failure class.

Publication, public accusation, external outreach, privacy-policy changes affecting real people, and irreversible publication remain explicit human/product-owner decisions.
