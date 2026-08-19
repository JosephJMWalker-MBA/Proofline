# R0 — Canton 2026 public-record experiment

## Question

Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was **not manually preselected**?

A successful result does not require misconduct. A discrepancy with an ordinary explanation is still a successful lead if Proofline can explain why it surfaced and provide the exact public evidence a human should inspect next.

## Current source scope

Year:

- 2026

Meeting families:

- Board of Control
- City Council

The experiment intentionally stays narrow enough to inspect manually while containing longitudinal variation, contracts, amendments, public meeting context, dollar amounts, identifiers, and publisher revision history.

The two meeting families now use different official discovery paths because the publisher exposes substantively usable evidence differently.

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
2. exact `City Council Regular Meeting Agenda (PDF)` events on the official Canton host;
3. the event page's explicit link to a CivicClerk event;
4. preserved CivicClerk event metadata;
5. the metadata's published `Agenda` file record;
6. stable CivicClerk `Meetings/GetMeetingFile(fileId=...)` source URI;
7. publisher-issued short-lived blob transport used only to retrieve the PDF bytes.

Canonical meeting evidence:

- published CivicClerk Agenda PDFs

No CivicClerk event ID or file ID is hand-maintained in the production discovery plan.

## Evidence policy

### Canonical meeting evidence

PDF meeting records are the primary evidentiary representation because they preserve page-level locators.

Proofline does **not** ingest HTML, PDF, and Packet renderings of the same meeting as independent evidence merely because all three are publicly linked. Doing so before explicit duplicate/corroboration semantics could make one underlying public record look like independent support.

### Discovery/supporting evidence

Discovery pages and public metadata are preserved separately as Bronze provenance before their links/fields are interpreted.

Examples:

- Agenda Center index
- `Previous Versions` listing pages
- official Calendar month listings
- official Calendar event pages
- CivicClerk event metadata

These supporting artifacts can establish **why Proofline collected a record** without masquerading as another copy of the meeting evidence.

### Revision evidence

A publisher `Previous Versions` page can establish:

```text
archived source --historical_version_of--> current source
```

That relation authorizes deterministic comparison. It does **not** establish that a difference is suspicious, material, intentional, or improper.

Blank/empty evidence is not treated as a substantive deletion. A version pair is skipped when either side lacks usable Silver text.

## Procedure

```bash
proofline sync experiments/canton-2026/source-plan.json
```

`sync` performs one deterministic cycle:

1. preserve the configured official discovery pages;
2. derive in-scope public records through bounded source-specific adapters;
3. preserve intermediate publisher pages/metadata used to derive final file sources;
4. write the generated final watch manifest under the Proofline state directory;
5. watch and ingest the final meeting resources;
6. derive publisher-backed historical source relations;
7. run deterministic version comparisons only across those relations;
8. rebuild lexical and structured retrieval indexes.

A later run repeats the same procedure. New resources, changed bytes, reverted bytes, and publisher-added historical versions become longitudinal evidence rather than silently replacing prior state.

## Measured checkpoint — August 19, 2026

GitHub Actions rebuilt R0 from official public sources after the Calendar→CivicClerk path and sync-time version analysis were productionized.

### Final meeting corpus

- **61 final discovered meeting resources**
- **0 unavailable final-resource downloads**
- **16 City Council Agenda PDFs**
- **75 City Council page evidence units, 75/75 nonblank**
- roughly **148,000 City Council extracted characters**
- **174 evidence units overall**
- **172 evidence units in the lexical index**
- **982 structured facts overall**
- **331 City Council structured facts** (282 money, 49 date)
- **2 low-quality review items**, both Board of Control pages
- **0 City Council CivicEngage pointer-wrapper records** in the final corpus

The discovery chain preserved additional supporting artifacts, including twelve 2026 Calendar month listings, seventeen official Calendar event pages, and seventeen CivicClerk event metadata records.

One of the seventeen Calendar events did not currently expose a published Agenda file in its CivicClerk metadata, so the final Council corpus contained sixteen agendas. Proofline did not fabricate a URL to fill that gap; a later sync can acquire the agenda if the publisher adds one.

These are measured snapshot counts, not contractual corpus sizes.

### Version analysis

The same live `sync` produced:

- **11 publisher-backed `historical_version_of` relations**
- **7 substantive comparisons**
- **7 version-change observations**
- **4 `same_artifact` skips**
- **0 detector failures**

A `same_artifact` relation means the publisher linked a historical/current record pair whose final bytes are identical. Proofline records the relation but does not manufacture a content change.

## Real-corpus failures that improved the architecture

R0 has already produced several useful engineering failures:

### Blank City Council CivicEngage PDF wrappers

The original City Council PDFs were one-page, zero-text pointer wrappers rather than meeting evidence. OCR would have been the wrong response.

### Stale UUID pointer target

The wrapper contained a machine-readable same-domain UUID URI, but all tested direct UUID targets returned 404. Proofline did not loosen crawling rules to chase arbitrary alternatives.

### Title-only HTML

The CivicEngage HTML representation transported successfully but was largely only a meeting title. A high “searchable resource” count briefly looked like an improvement until content quality was measured. This became the reason R0 CI now asserts substantive Council page/text/fact floors rather than HTTP success alone.

### Empty Packet representation

The publisher's Packet representation was also non-substantive for the sampled Council records.

### Legacy archive TLS failure

A separate official archive failed strict certificate validation from GitHub Actions. Proofline did not disable TLS verification; it found the verified official Calendar→CivicClerk chain instead.

### Temporary download URL versus canonical source identity

CivicClerk's stable file API returns a JSON envelope with a rotating signed Azure blob URL. Treating the signed URL as source identity would create false change events whenever the token rotated.

Proofline now keeps the stable file API as canonical source and uses the signed blob only as in-memory transport. Identical PDF bytes behind a fresh token remain `unchanged`.

### Library capability existed without CLI orchestration

The version-analysis runner was implemented and tested, but an earlier integration claim did not actually modify `cli.py`; live CI also treated a missing `version_analysis` field as an empty result. CLI-boundary tests and the live R0 workflow now require `sync` to emit and execute version analysis explicitly.

## R0 phases

### R0.1 — Corpus integrity

Substantially achieved for the current scope. Continue measuring:

- discovered resources
- successful vs unavailable retrievals
- unique artifacts
- page/evidence count
- extraction quality distribution
- low-confidence/review backlog
- exact duplicate prevalence
- revision-list coverage
- discovery-supporting artifact coverage

### R0.2 — Retrieval sanity

Continue building real-corpus questions without selecting a desired conclusion, for example:

- find a named ordinance or contract identifier;
- find records containing amounts above a threshold;
- find meetings in a date range;
- retrieve the exact page behind a selected result.

### R0.3 — Detector baseline

Now active.

Current deterministic detector capability includes publisher-backed version comparison. Next useful detector classes include:

- conflicting normalized values tied to the same explicit identifier;
- repeated item/identifier appearance across meetings;
- unusually large numeric changes relative to comparable records;
- document/version appearance or disappearance where publisher semantics justify the comparison.

Each detector must emit evidence references and limitations. It must not assign motive or wrongdoing.

### R0.4 — Human lead packet

Only after a machine observation survives provenance checks should Proofline package it as a candidate lead with:

- why it surfaced;
- exact evidence;
- uncertainty;
- possible benign explanations;
- questions worth asking.

Publication is out of scope.

## First non-preselected pattern behavior

R0 has already shown the desired workflow on a repeated public-safety drone contract item that appeared across consecutive Board of Control agendas. Repetition alone was not treated as suspicious. The surrounding public record supplied an ordinary procedural explanation, so the pattern remains an **explained candidate**, not a finding of wrongdoing.

The same principle applies to version observations: a changed amount can be surfaced deterministically while an arithmetic relationship or surrounding source text is presented as possible benign context rather than upgraded into causation.

## Success criteria

R0 succeeds if all of the following are true:

1. the corpus can be regenerated from official publisher interfaces without a hand-maintained final URL list;
2. every search result or observation resolves to stable evidence and original source lineage;
3. at least one non-preselected pattern is surfaced reproducibly;
4. a human can inspect that pattern without trusting an LLM-generated narrative;
5. the system makes clear when the apparent pattern has a plausible ordinary explanation.

The current checkpoint satisfies much of this definition; R0 remains active because detector/lead-packet behavior still needs broader real-corpus evaluation.

## Failure is useful

R0 is successful as an engineering experiment when the real corpus exposes a broken assumption. Those failures become fixtures, trust boundaries, and CI assertions before Proofline expands to a larger corpus.
