# Proofline

**Follow the record.**

Proofline is public-record intelligence infrastructure for provenance-backed investigative leads.

It continuously turns large, messy public archives into stable evidence that can be discovered, watched, searched, compared, and used to surface reproducible leads for human investigators and journalists.

Proofline does **not** decide that a person or organization did something wrong. It distinguishes source evidence from machine-derived observations and leaves accusation, fairness, newsworthiness, and publication decisions with humans.

> **Looking for what exists today?** Start with [STATUS.md](STATUS.md). The roadmap explains where the system is going; `STATUS.md` distinguishes implemented capabilities, measured behavior, validation status, and the active research edge.

## The problem

Important facts can be technically public but practically hidden inside volume:

- massive document releases
- scanned or poorly OCR'd PDFs
- spreadsheets and native files
- revisions and quiet replacements
- duplicated records
- inconsistent names and identifiers
- records distributed across multiple agencies or systems

Search alone does not answer the harder questions:

- What exists?
- What changed?
- What disappeared?
- What cannot be reliably extracted?
- Which values or dates conflict across records?
- Which patterns deserve a human's time?

## Epistemic model

### Bronze — Source

Immutable original artifacts and retrieval metadata.

- original bytes
- source URI
- retrieval timestamp
- SHA-256
- native/public identifier
- version relationship

### Silver — Evidence

Stable human-inspectable evidence units with append-only extraction attempts.

- page, row, or logical record
- source locator
- extracted text
- extraction method/version
- quality/confidence

Better OCR can improve the preferred extraction without changing the evidence identity or deleting earlier attempts.

### Gold — Derived

Regenerable interpretation and analysis.

- entities and aliases
- relationships
- events
- anomalies
- observations
- investigative leads
- embeddings / model outputs

**Gold may be wrong. Silver must be reproducible. Bronze must remain immutable.**

## Current pipeline

```text
official publisher interfaces
    |
    v
discovery/support provenance ---> deterministic source manifests
    |
    v
watch/acquisition ---> immutable artifact history
    |
    v
progressive extraction ---> stable evidence units ---> quality review
    |
    +----> publisher-backed source relations ---> deterministic observations
    |
    v
lexical + structured indexes
    |
    v
source-profile / policy-scoped analysis
    |
    v
candidate leads ---> append-only human review
```

The evidence core, watcher, progressive extraction, deterministic retrieval, benchmark/evaluation framework, bounded detectors, immutable candidate leads, and human-review receipts are implemented and tested. Real-corpus validation has progressed through **R0 Canton 2026** and **R1 transfer validation in Akron 2026**. See [ROADMAP.md](ROADMAP.md), [STATUS.md](STATUS.md), [experiments/canton-2026/README.md](experiments/canton-2026/README.md), and [experiments/akron-2026/README.md](experiments/akron-2026/README.md).

## Quick start

```bash
python -m pip install -e ".[dev]"

proofline ingest ./records/report.pdf \
  --source-uri "https://example.gov/reports/report.pdf" \
  --native-id "REPORT-2026-08"

proofline status
```

### Discover and continuously sync public sources

A static manifest is useful when resource URLs are already known. A discovery plan is used when official publisher interfaces expose new record URLs over time.

```bash
proofline discover experiments/canton-2026/source-plan.json
proofline sync experiments/canton-2026/source-plan.json
```

`discover` first preserves the configured publisher discovery pages, then derives a bounded watch manifest through source-specific adapters. `sync` performs discovery, watches/ingests the resulting resources, runs deterministic comparisons only across publisher-backed historical-version relations, and rebuilds retrieval indexes.

For Canton, Board of Control comes from CivicEngage Agenda Center PDFs/history, while City Council follows the official Canton Calendar into publisher-linked CivicClerk agenda files. That split exists because the original CivicEngage Council PDFs were non-substantive pointer wrappers, not because Proofline broadly crawls alternate sources.

Akron uses a separate generic Hyland OnBase Agenda Online adapter because the publisher's canonical evidence boundary is different: individual agenda-item HTML records rather than the PDF/page boundary used in Canton. The adapter follows publisher-exposed meeting search, agenda-tree, and agenda-item relationships without numeric-ID sweeping.

See [docs/DISCOVERY.md](docs/DISCOVERY.md) and [docs/ONBASE_AGENDA_ONLINE.md](docs/ONBASE_AGENDA_ONLINE.md).

### Analyze publisher-backed versions

```bash
proofline analyze-versions
proofline trace <observation-id>
```

Version comparison is provenance-gated. Proofline does not decide that two similarly named documents are versions of one another. A preserved publisher artifact must first establish a `historical_version_of` source relation.

A comparison can report exact text/value changes and descriptive arithmetic context, but it does not assign motive, suspiciousness, or materiality. Blank/empty Silver evidence is skipped rather than interpreted as deletion.

`trace` returns the evidence used for an observation and the publisher-backed source relation that authorized the comparison.

### Watch an existing manifest

```bash
proofline watch examples/source-manifest.json
proofline changes
```

Each visit is recorded independently as `new`, `unchanged`, `changed`, or `unavailable`. `changed` means the final acquired bytes differ from the immediately prior successful observation. It does not explain motive or significance.

Some publishers expose a stable file API that returns a short-lived signed transport URL. Proofline keeps the stable publisher URI as source identity and uses the temporary transport only in-memory, so token rotation does not create false source changes.

See [docs/SOURCE_MANIFEST.md](docs/SOURCE_MANIFEST.md).

### Review extraction quality

```bash
proofline review
proofline review --threshold 0.80
proofline extract artifact:<sha256> --ocr tesseract
```

Tesseract is optional. Proofline can preserve and queue a scan even when OCR is unavailable. HTML is converted to visible text without script/style/template content. CSV/XLSX records are streamed into citeable row evidence; spreadsheet formulas are preserved but not evaluated.

See [docs/EXTRACTION.md](docs/EXTRACTION.md).

### Build and query retrieval indexes

```bash
proofline index
proofline search "Northstar Civic Systems"
proofline lookup CSV-B

proofline amounts --min 250000 --max 500000
proofline dates --from 2026-01-01 --to 2026-12-31
proofline identifier C-001

proofline evaluate tests/retrieval_eval.json --k 5
```

`proofline index` builds disposable derivatives over preferred Silver evidence, including:

1. SQLite FTS5 lexical evidence search with transparent BM25 ranking;
2. publisher-native identifier lookup;
3. deterministic structured facts for explicit monetary values, dates, and identifiers when source semantics justify them.

Arbitrary digits are **not** assumed to be money. Arbitrary tokens are **not** assumed to be identifiers. Structured meaning must come from explicit syntax or source field semantics.

See [docs/RETRIEVAL.md](docs/RETRIEVAL.md) and [docs/RETRIEVAL_EVALUATION.md](docs/RETRIEVAL_EVALUATION.md).

## Provenance invariant

The most important path runs backward:

```text
Lead
  -> Observation
      -> EvidenceUnit
          -> Artifact
              -> observed public source
```

For version observations there is an additional authorization path:

```text
Observation
  -> publisher-backed source relation
      -> preserved version-listing artifact
```

An LLM is never required to traverse either chain.

The stable reference contract is documented in [docs/EVIDENCE_REFERENCE.md](docs/EVIDENCE_REFERENCE.md).

## Local state

```text
.proofline/
├── proofline.db
├── manifests/
└── artifacts/
    └── sha256/
        └── <prefix>/<full-sha256>
```

Original bytes are content-addressed. Watcher chronology is stored separately from unique artifact identity, so a public source sequence such as `A -> B -> A` remains temporally visible rather than collapsing back to one remembered object.

## Validated research state

### R0 Canton 2026 — complete

R0 asked whether Proofline could ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected.

It did. The first non-preselected candidate was a recurring municipal matter with changing expenditure-deadline facts. Human review found an ordinary administrative explanation and dispositioned the lead `explained`. That benign result was preserved as a successful test of the system's ability to surface a reproducible question without turning anomaly detection into accusation.

A later segmentation correction changed the deterministic derivation identity. The prior review did not silently transfer; a new review receipt explicitly re-affirmed the corrected lead while preserving the prior reviewed lead.

### R1 Canton semantic gates — bounded validations complete

Proofline then tightened the comparison boundary before expanding interpretation:

- a frozen canonical retrieval benchmark scored **42/42 expectations met** with **1.0 target recall at 10** and **1.0 provenance validity**;
- corrected Board segmentation prevented unrelated matters from being silently grouped;
- matter keys were treated as permission to compare, not universal entity identity;
- financial values became comparable only after both matter identity and field role were resolved;
- the first authorized financial-conflict detector emitted **0 conflicts**, and that negative result was accepted without retuning the policy to manufacture a finding.

These are bounded results from frozen corpora and policies, not claims of universal retrieval or semantic completeness.

### R1 Akron 2026 transfer — T1 through T5 complete

Akron tests whether the same evidence/retrieval architecture transfers to a materially different publisher stack.

The generic OnBase path produced **1,475 canonical agenda-item resources with 0 unavailable items and 1,475/1,475 nonblank Silver records**. The publisher already supplied the logical record boundary, so no extra Akron agenda segmentation was added.

A retrieval-blind benchmark was frozen before lexical scoring. Its first score produced:

- **37/37 expectations met**;
- **32/32 positive cases hit**;
- **54/54 explicit positive targets recovered**;
- **5/5 negative controls passed**;
- **1.0 target recall at 10**;
- **1.0 provenance validity**;
- **0 unresolved targets**;
- **no measured retrieval failure class**.

Semantic/vector retrieval therefore remains deferred. This is a complexity gate, not a claim that lexical/structured retrieval will always be sufficient.

See [STATUS.md](STATUS.md) for the detailed validation record and frozen receipts.

## Current research edge: Akron supporting documents

The current bounded question is whether publisher-declared supporting-document relationships can be acquired without guessing identifiers or broad crawling while preserving exact relationship provenance.

The active work is intentionally narrower than "ingest every attachment": inspect already-acquired canonical item HTML, classify publisher-declared link/transport patterns, follow only a deterministic bounded sample, validate actual response bytes/media types, and decide whether a generic OnBase attachment adapter is justified.

Until that work is promoted through the same evidence and validation discipline as T1–T5, supporting-document acquisition should be treated as an active experiment rather than an established production capability.

## Design principles

1. **Evidence before narrative.**
2. **Provenance is mandatory.**
3. **Cheap extraction first.**
4. **Confidence measures extraction usability, not truth.**
5. **Indexes are disposable.**
6. **Longitudinal memory matters.**
7. **Humans retain editorial agency.**
8. **Seek benign explanations.**

See [ARCHITECTURE.md](ARCHITECTURE.md) and [GOVERNANCE.md](GOVERNANCE.md) for the deeper system and editorial contracts.
