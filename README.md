# Proofline

**Follow the record.**

Proofline is public-record intelligence infrastructure for provenance-backed investigative leads.

It continuously turns large, messy public archives into stable evidence that can be discovered, watched, searched, compared, and eventually used to surface reproducible leads for human investigators and journalists.

Proofline does **not** decide that a person or organization did something wrong. It distinguishes source evidence from machine-derived observations and leaves accusation, fairness, newsworthiness, and publication decisions with humans.

> **Looking for what exists today?** Start with [STATUS.md](STATUS.md). The roadmap explains where the system is going; `STATUS.md` distinguishes implemented capabilities, measured behavior, validation status, and the active experiment.

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

- page or logical record
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
official public indexes / calendars
    |
    v
discovery ---> preserved supporting provenance ---> deterministic watch manifest
    |
    v
watch/acquisition ---> immutable artifact history
    |
    v
progressive extraction ---> page/row evidence ---> quality review
    |
    +----> publisher-backed source relations ---> deterministic version observations
    |
    v
lexical + structured indexes
    |
    v
additional pattern detectors ---> observations ---> corroboration
    |
    v
lead desk ---> human investigation
```

M0 through M3 are complete and tested. R0 is the first real-public-record experiment and now exercises live discovery, acquisition, extraction, retrieval, publisher-backed version comparison, and CI content-quality assertions. See [ROADMAP.md](ROADMAP.md), [STATUS.md](STATUS.md), and [experiments/canton-2026/README.md](experiments/canton-2026/README.md).

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

For R0, Board of Control comes from CivicEngage Agenda Center PDFs/history, while City Council follows the official Canton Calendar into publisher-linked CivicClerk agenda files. That split exists because the original CivicEngage Council PDFs were non-substantive pointer wrappers, not because Proofline broadly crawls alternate sources.

See [docs/DISCOVERY.md](docs/DISCOVERY.md).

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

`proofline index` builds two disposable derivatives over preferred Silver evidence:

1. SQLite FTS5 lexical evidence search with transparent BM25 ranking;
2. deterministic structured facts for explicit monetary values/dates in prose and semantically named spreadsheet fields.

Arbitrary digits are **not** assumed to be money. Arbitrary tokens are **not** assumed to be identifiers. Structured meaning must come from explicit syntax or source field semantics.

See [docs/RETRIEVAL.md](docs/RETRIEVAL.md).

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

## Active experiment: R0 Canton 2026

The active product experiment is:

> **Ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected.**

The August 19, 2026 live validation checkpoint rebuilt **61 final meeting resources with zero unavailable final downloads**, including **16 substantive City Council agenda PDFs**. Those Council agendas produced **75/75 nonblank page evidence units**. The full corpus produced **174 evidence units**, **982 structured facts**, and only **2 review-queue items**. The same sync derived **11 publisher-backed historical-version relations**, created **7 deterministic version-change observations**, skipped **4 same-artifact relations**, and reported **0 detector failures**.

These are measured snapshot counts, not promises about future publisher state. See [experiments/canton-2026/README.md](experiments/canton-2026/README.md) for source policy, failure cases, and the current detector phase.

Success does not mean finding wrongdoing. A routine discrepancy with a benign explanation is still a successful investigative lead if Proofline identifies it reproducibly and gives a human the exact evidence needed to investigate it.

Semantic/vector retrieval remains deferred until measured real-corpus retrieval failures justify it.

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
