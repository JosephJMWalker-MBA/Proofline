# R0 — Canton 2026 public-record experiment

## Question

Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was **not manually preselected**?

A successful result does not require misconduct. A discrepancy with an ordinary explanation is still a successful lead if Proofline can explain why it surfaced and provide the exact public evidence a human should inspect next.

## Source scope

Canonical discovery index:

- `https://cantonohio.gov/AgendaCenter`

Initial categories:

- Board of Control
- City Council

Initial year:

- 2026

The experiment intentionally starts narrow enough to inspect manually while containing real longitudinal variation, contracts, amendments, public meeting context, dollar amounts, ordinance identifiers, and published revision history.

## Evidence policy

### Canonical meeting evidence

PDF meeting records are the primary evidence representation for this experiment because they preserve page-level locators.

Proofline will **not** ingest both HTML and PDF versions of every meeting as independent evidence during R0. Doing so before duplicate/corroboration semantics exist could make one underlying public record look like independent support.

### Discovery and revision evidence

The official Agenda Center HTML index is itself preserved as a Bronze artifact and extracted as visible-text Silver evidence.

When the index exposes `Previous Versions`, that listing is also watched as a source. Its existence is evidence that the publisher exposes revision history; it is not evidence that a revision is suspicious or improper.

## Procedure

```bash
proofline sync experiments/canton-2026/source-plan.json
```

`sync` performs one deterministic cycle:

1. preserve the official Agenda Center index;
2. discover in-scope meeting resources from links published by that index;
3. write the generated manifest under the Proofline state directory;
4. watch and ingest the discovered resources;
5. rebuild lexical and structured retrieval indexes.

A later run repeats the same procedure. New resources and changed bytes become longitudinal evidence rather than silently replacing prior state.

## R0 phases

### R0.1 — Corpus integrity

Before looking for leads, measure:

- discovered resources
- successful vs unavailable retrievals
- unique artifacts
- page/evidence count
- extraction quality distribution
- low-confidence/review backlog
- exact duplicate prevalence
- revision-list coverage

### R0.2 — Retrieval sanity

Build real-corpus questions only after ingestion. Questions should exercise known public-record tasks without selecting a desired conclusion, for example:

- find a named ordinance or contract identifier;
- find records containing amounts above a threshold;
- find meetings in a date range;
- retrieve the exact page behind a selected result.

### R0.3 — Detector baseline

Run only deterministic observations first:

- source changed across visits;
- explicit identifier sequence gaps where a real sequence is defined;
- conflicting normalized values tied to the same explicit identifier;
- unusually large numeric changes relative to comparable records;
- document/version appearance or disappearance.

Each detector must emit evidence references and limitations. It must not assign motive or wrongdoing.

### R0.4 — Human lead packet

Only after a machine observation survives provenance checks should Proofline package it as a candidate lead with:

- why it surfaced;
- exact evidence;
- uncertainty;
- possible benign explanations;
- questions worth asking.

Publication is out of scope.

## Success criteria

R0 succeeds if all of the following are true:

1. the corpus can be regenerated from the official index without a hand-maintained URL list;
2. every search result or observation resolves to stable evidence and original source lineage;
3. at least one non-preselected pattern is surfaced reproducibly;
4. a human can inspect that pattern without trusting an LLM-generated narrative;
5. the system makes clear when the apparent pattern has a plausible ordinary explanation.

## Failure is useful

R0 is also successful as an engineering experiment if the real corpus exposes a broken assumption—for example bad OCR, unstable source links, duplicate inflation, missing page provenance, or poor retrieval. Those failures should become fixtures and tests before Proofline expands to a larger corpus.
