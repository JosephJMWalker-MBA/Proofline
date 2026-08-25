# Proofline

**Follow the record. Preserve the boundary.**

Proofline is provenance-first public-record intelligence infrastructure for turning messy government archives into reproducible evidence, bounded observations, and reviewable investigative questions.

It is built for a problem that ordinary search does not solve well: a public fact may be spread across meeting systems, revisions, attachments, minutes, legislation databases, notices, and later records. Proofline reconstructs those relationships while keeping source authority, uncertainty, and non-findings explicit.

Proofline does **not** decide that a person or organization did something wrong. It does not turn recurrence into suspicion, missing records into adverse outcomes, or procedural labels into conclusions. Human investigators, journalists, researchers, and reviewers retain responsibility for interpretation and publication.

## What Proofline does

```text
official publisher interfaces
        |
        v
preserved source provenance
        |
        v
immutable Bronze artifacts
        |
        v
stable Silver evidence units
        |
        +----> lexical + structured retrieval
        |
        +----> publisher-backed relationships
        |
        +----> chronology / comparison / bounded observations
        |
        v
reviewable Gold outputs
        |
        v
append-only human review
```

The governing rule is simple:

> **Gold may be wrong. Silver must be reproducible. Bronze must remain immutable.**

### Bronze — source

Original publisher artifacts and retrieval history:

- original bytes
- stable source URI
- retrieval timestamp
- SHA-256
- publisher/native identifier
- source and version relationships

### Silver — evidence

Stable, human-inspectable evidence units:

- page, row, agenda item, or logical record
- exact source locator
- extracted text
- extraction method/version
- quality/confidence metadata

Extraction can improve without rewriting history. Earlier attempts remain preserved.

### Gold — derived

Regenerable analysis:

- entities and aliases
- relationships
- events
- chronology
- comparisons
- observations
- candidate leads
- model outputs

Gold outputs are not source facts. They must trace backward to the evidence that authorized them.

## Why the provenance boundary matters

The most important Proofline operation runs backward:

```text
Lead / Observation
    -> EvidenceUnit
        -> Artifact
            -> observed public source
```

Where comparison or relationship claims depend on publisher structure, there is an additional authorization path:

```text
Observation
    -> publisher-backed relationship
        -> preserved publisher record establishing that relationship
```

An LLM is never required to traverse either chain.

This distinction lets Proofline say things such as:

- two records explicitly refer to the same municipal matter;
- a publisher replaced one document with another;
- two records contain different stated values;
- one meeting record schedules a later hearing;
- a bounded source search returned zero candidates;

without silently upgrading those facts into:

- motive;
- wrongdoing;
- causal effect;
- passage or denial;
- abandonment;
- significance or newsworthiness.

## Validated public-source stacks

Proofline has been exercised against two materially different municipal publisher systems.

### Canton, Ohio

Validated source paths include:

- CivicEngage Agenda Center
- CivicEngage `Previous Versions` / `ArchivedAgenda`
- the official Canton Calendar
- CivicClerk event metadata and meeting-file transport

Canton required source-profile-specific segmentation because publisher PDFs contain multiple agenda matters within larger documents.

### Akron, Ohio

Validated source paths include:

- Hyland OnBase Agenda Online bounded meeting search
- embedded publisher `SearchResults` data
- `Documents/ViewAgenda` agenda trees
- publisher-linked agenda-item discovery
- canonical `Meetings/ViewMeetingAgendaItem` HTML
- OnBase Public Access custom-query metadata
- Council and Committee Meeting Minutes
- marked agenda PDFs
- Passed Legislation search
- Clerk/Council notice publications

Akron often supplies the logical agenda-item boundary directly, so Proofline does not add segmentation merely for consistency with Canton.

## Real-corpus validation

### R0 — Canton 2026

The first real-corpus experiment asked whether Proofline could acquire public records, normalize them into reproducible evidence, surface a non-preselected question, and preserve a benign human explanation without rewarding suspicious-sounding output.

It did. The first candidate involved a recurring municipal matter with changing expenditure-deadline facts. Human review found an ordinary administrative explanation and dispositioned the lead `explained`. That benign result was treated as a successful system test, not a failed hunt for wrongdoing.

### R1 — retrieval and semantic gates

Two frozen canonical retrieval benchmarks currently exist:

| Corpus | Cases | Positive cases | Negative controls | Target recall @10 | Provenance validity | Unresolved targets |
|---|---:|---:|---:|---:|---:|---:|
| Canton canonical v2 | 42 | 37 | 5 | 1.0 | 1.0 | 0 |
| Akron transfer v1 | 37 | 32 | 5 | 1.0 | 1.0 | 0 |

These are bounded measurements from frozen corpora, not claims of universal completeness. Semantic/vector retrieval remains deferred because the frozen real-corpus benchmarks have not yet exposed a deterministic retrieval failure class that justifies the added complexity.

## Akron T21 — reconstruct a record family and trace outcome

The current advanced validation asks a harder question than retrieval:

> Can Proofline reconstruct the public-record family around a citizen-facing municipal matter, resolve references across independent publisher surfaces, build a chronology, and trace a later outcome without inventing one when authority is incomplete?

The governed chain is:

```text
citizen-facing matter
    -> referenced planning case / petition / ordinance
    -> agenda placement
    -> Council and Committee records
    -> staff / commission recommendation
    -> hearing and procedural activity
    -> later publisher surfaces
    -> authoritative disposition evidence, if it exists
```

The frozen Akron target is planning case `PC-2025-80-CU`, Petition `D-14`, concerning a conditional use for a training facility at `1928 Eastwood Avenue`.

T21 has now validated a substantial part of the relationship/provenance architecture:

- exact target identity frozen before terminal-record searches;
- exact agenda-status chronology measured without treating recurring `TIME` as disposition;
- numbered-vote candidates bounded and measured without interpreting vote arithmetic as passage/failure;
- Public Access source contracts independently probed before target searches;
- Council Meeting Minutes searched by frozen exact dates, acquired as source bytes, and audited target-locally;
- Committee Meeting Minutes independently searched, acquired, and audited;
- Council/Committee evidence linked through typed non-terminal provenance relationships;
- publisher placements, target evidence, future metadata, and search checkpoints kept in separate chronology lanes;
- Passed Legislation recall expanded only under pre-frozen query terms;
- Clerk-authored Charter §38 notices tested as a positive-only passage surface;
- a public-record request scope frozen before submission;
- the exact governed request submitted to the City of Akron and its sent-message receipt preserved.

The evidence currently supports procedural facts such as referral, hearing activity, recommendations, public comment, and committee polling. It does **not** yet establish a governed terminal disposition for the Eastwood matter.

**Current T21 outcome: `Unknown`.**

That is an intentional result. Proofline treats the following as non-terminal unless a separately governed authoritative source says otherwise:

- repeated agenda presence;
- `TIME` status;
- recommendation for approval;
- committee poll arithmetic;
- disappearance from later agendas/minutes;
- zero search results;
- missing minutes;
- search-engine non-findings;
- absence of a §38 notice;
- an assigned legislative number by itself;
- delay or no response to a records request.

T21 is currently parked pending an actual Akron custodian response or responsive record. No additional inference is authorized while waiting.

See `experiments/akron-2026/` and issue `#83` for the frozen plans, source receipts, measurement summaries, and merge-by-merge continuity record.

## Quick start

```bash
python -m pip install -e ".[dev]"

proofline ingest ./records/report.pdf \
  --source-uri "https://example.gov/reports/report.pdf" \
  --native-id "REPORT-2026-08"

proofline status
```

### Discover and sync official sources

```bash
proofline discover experiments/canton-2026/source-plan.json
proofline sync experiments/canton-2026/source-plan.json
```

Discovery follows source-specific publisher contracts. It does not broadly crawl alternate sites or sweep guessed numeric identifiers.

For Akron OnBase:

```bash
proofline-onbase <plan.json>
```

See [docs/DISCOVERY.md](docs/DISCOVERY.md), [docs/SOURCE_MANIFEST.md](docs/SOURCE_MANIFEST.md), and [docs/ONBASE_AGENDA_ONLINE.md](docs/ONBASE_AGENDA_ONLINE.md).

### Search and inspect evidence

```bash
proofline index
proofline search "Northstar Civic Systems"
proofline lookup CSV-B
proofline amounts --min 250000 --max 500000
proofline dates --from 2026-01-01 --to 2026-12-31
proofline identifier C-001
proofline trace <observation-id>
```

Structured meaning is conservative. Arbitrary digits are not assumed to be money, and arbitrary tokens are not assumed to be identifiers. Source syntax or field semantics must authorize the interpretation.

### Review extraction quality

```bash
proofline review
proofline review --threshold 0.80
proofline extract artifact:<sha256> --ocr tesseract
```

OCR is optional. Proofline can preserve and queue an artifact even when OCR is unavailable. HTML is converted to visible text without script/style/template content. CSV/XLSX records are streamed into citeable row evidence; spreadsheet formulas are preserved but not evaluated.

### Analyze governed comparisons

```bash
proofline analyze-versions
proofline changes
proofline analyze-watch-changes
proofline trace <observation-id>
```

Version comparison is provenance-gated. Similar names are not enough: the publisher must first establish the relevant version relationship.

## Local state

```text
.proofline/
├── proofline.db
├── manifests/
└── artifacts/
    └── sha256/
        └── <prefix>/<full-sha256>
```

Original bytes are content-addressed. Watcher chronology is separate from unique artifact identity, so a public-source sequence such as `A -> B -> A` remains temporally visible instead of collapsing into one remembered object.

## Design principles

1. **Evidence before narrative.**
2. **Provenance is mandatory.**
3. **Authority and completeness are separate properties.**
4. **Missing evidence remains unknown.**
5. **Relationships authorize comparison; they do not imply causality.**
6. **Cheap deterministic extraction comes first.**
7. **Confidence measures extraction usability, not truth.**
8. **Indexes and Gold outputs are disposable; source evidence is not.**
9. **Longitudinal memory matters.**
10. **Seek benign explanations.**
11. **Humans retain editorial agency.**
12. **Negative results are valid results.**

## Repository guide

- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
- [GOVERNANCE.md](GOVERNANCE.md) — editorial and epistemic boundaries
- [STATUS.md](STATUS.md) — detailed implementation/validation history
- [ROADMAP.md](ROADMAP.md) — planned development
- [docs/](docs/) — source, extraction, retrieval, evidence-reference, and review contracts
- [experiments/canton-2026/](experiments/canton-2026/) — R0/R1 Canton validation
- [experiments/akron-2026/](experiments/akron-2026/) — R1 Akron transfer and T21 record-family/outcome tracing

## Scope boundary

Public accusation, outreach, publication, privacy-policy changes affecting real people, paid external deployment, and irreversible publication remain explicit human/product-owner decisions.

Proofline is designed to make the public record easier to follow **without pretending the record says more than it does**.
