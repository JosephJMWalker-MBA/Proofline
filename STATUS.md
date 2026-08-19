# Proofline — Live Status

This file is the current implementation and validation record for Proofline.

## Current state

Proofline has now validated two related claims:

1. **R0 Canton 2026:** a real public-record corpus can be acquired, normalized into reproducible evidence, analyzed deterministically, promoted selectively into a candidate lead, and dispositioned by a human without rewarding suspicious-sounding output.
2. **R1 transfer validation:** the evidence and retrieval architecture transfers to a second municipal publisher stack with a materially different canonical evidence boundary.

The current end-to-end architecture is:

```text
official publisher interfaces
→ preserved discovery/support provenance
→ immutable Bronze artifacts
→ stable Silver evidence units
→ deterministic lexical + structured retrieval
→ source-profile-specific segmentation only when required
→ policy-scoped matter identity / field semantics
→ deterministic observations and candidate leads
→ append-only human review
→ durable version-controlled receipts
```

**Gold may be wrong. Silver must be reproducible. Bronze must remain immutable.**

Semantic/vector retrieval remains deferred because neither frozen real-corpus benchmark has exposed a deterministic retrieval failure class that justifies it.

## Implemented platform capabilities

### Evidence core

- immutable SHA-256 artifact identity
- stable evidence units with human-inspectable locators
- append-only extraction and processing history
- deterministic observation/evidence traceability
- evidence-backed immutable lead packets
- content-addressed local artifact storage

### Watcher and source provenance

- versioned source manifests
- `new`, `unchanged`, `changed`, and `unavailable` watcher states
- append-only visit chronology
- correct `A → B → A` reversion semantics
- prior-byte preservation
- exact watcher `check_id` provenance for watcher-authorized observations
- publisher-backed `historical_version_of` relations
- stable source identity separated from temporary/signed transport URLs

### Extraction and retrieval

- native PDF/text/HTML/JSON/XML extraction
- page/row/logical-record evidence identities
- progressive OCR escalation
- extraction quality measurement and review queue
- Unicode-aware substantive-Silver gate before Gold promotion
- SQLite FTS5 lexical retrieval
- publisher-native identifier lookup
- deterministic structured indexing for explicit money, dates, and identifiers
- amount/date range queries
- retrieval evaluation with exact source URI + locator + optional artifact SHA targets
- scorable reporting that separates target drift from retrieval failure

### Public-source adapters now validated

Canton:

- CivicEngage Agenda Center
- CivicEngage `Previous Versions` / `ArchivedAgenda`
- official Canton Calendar
- CivicClerk event metadata and meeting-file transport

Akron:

- generic Hyland OnBase Agenda Online bounded meeting search
- embedded first-party `SearchResults` JSON
- `Documents/ViewAgenda` agenda trees
- publisher-linked `loadAgendaItem(id, false)` discovery
- canonical `Meetings/ViewMeetingAgendaItem` HTML evidence
- installed `proofline-onbase` CLI

The OnBase adapter contains no Akron hostname, Canton semantic policy, or numeric-ID sweep.

## R0 Canton 2026 — complete

R0 asked:

> Can Proofline ingest a real public-record corpus and surface at least one reproducible anomaly, contradiction, unexplained change, or cross-record pattern that was not manually preselected?

**Yes.**

The first non-preselected machine candidate was the recurring ECDI / Ordinance 60/2023 / `$185,000` CDBG matter with changing expenditure-deadline facts. Human review found an ordinary administrative explanation and dispositioned the lead `explained`; Proofline did not reinterpret that benign explanation as failure.

A later segmentation correction changed the deterministic derivation identity. The prior human review did **not** silently transfer. A new review receipt explicitly re-affirmed the corrected lead, while the prior reviewed lead remained preserved.

See [experiments/canton-2026/README.md](experiments/canton-2026/README.md) and [docs/REVIEW_RECORDS.md](docs/REVIEW_RECORDS.md).

## R1 Canton semantic gates — complete for the first bounded policies

### Canonical retrieval benchmark

The second Canton retrieval suite restricted positive targets to canonical evidence before scoring.

Frozen suite:

- **42 cases**
- **37 positive / 5 negative controls**
- **42/42 expectation met**
- positive hit rate at 10: **1.0**
- target recall at 10: **1.0**
- negative accuracy: **1.0**
- provenance validity: **1.0**
- unresolved targets: **0**

See `experiments/canton-2026/retrieval/R1_CANONICAL_V2_SCORE.md`.

### Corrected Board segmentation

The live Board source profile now produces:

- **144** agenda-item segments
- **6** recovered compound-ordinance anchors
- **0** nested ordinance-heading errors

This correction was required before matter identity because the prior rule could place unrelated matters inside one segment.

### Matter-key contract

The first conservative Board policy treats a matter key as **permission to compare**, not a universal entity identity.

Live result:

- **144** matter candidates
- **22 resolved**
- **2 ambiguous**
- **120 insufficient identity**
- **2 repeated resolved matter keys**

The policy correctly separates a live same-project/same-change-order counterparty collision rather than manufacturing a false join.

### Financial field-role policy

Money values become comparable only after both matter identity and field role are resolved.

Live result:

- **46** money facts inside resolved matters
- **41 assigned**
- **5 unknown**
- **0 ambiguous**
- **3** repeated same-matter/same-role comparison populations

Unknown values remain unknown rather than being forced into a taxonomy.

### Conflicting-value detector

The first financial conflict detector compares only:

```text
same resolved matter key + same assigned financial role
```

Live Canton result:

- **3** authorized repeated populations inspected
- **0** conflicts emitted

That negative result is accepted. The detector was not tuned to manufacture a finding.

## R1 Akron 2026 transfer experiment — T1 through T5 complete

Akron is intentionally different from Canton. Its official source is Hyland **OnBase Agenda Online**, and the publisher supplies individual agenda-item HTML resources rather than the PDF/page boundary used in Canton.

See [experiments/akron-2026/README.md](experiments/akron-2026/README.md).

### T1 — source-contract probe

The bounded probe established that:

- raw meeting shells are not substantive canonical evidence;
- the visible Agenda anchor is not a direct agenda PDF;
- nominal agenda `DownloadFile` samples did not return PDF bytes;
- the promotable publisher chain is meeting search → agenda tree → publisher-linked agenda item.

No numeric meeting/item IDs are guessed or swept.

### T2 — generic production adapter

A clean live run produced:

- **33** meetings with available agendas
- **1** preserved bounded search artifact
- **33** preserved agenda-tree support artifacts
- **1,475** canonical agenda-item resources
- **0 unavailable** canonical items
- **1,475/1,475** canonical items with nonblank Silver text

The ordinary Proofline watcher, HTML extractor, lexical indexer, and structured indexer were reused unchanged.

Immediate rediscovery reproduced the same manifest identity:

`375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`

### T3 — atomic evidence validation

Across all **1,475** canonical items:

- **1,475/1,475** locator `record:1`
- **0** structural atomicity errors
- exactly one `Item Details` boundary per item
- exactly one return-to-outline boundary per item
- **3** legitimate short utility items (`Meeting Notice` ×2, `Files` ×1)
- **0** unknown short-item classes

**Decision:** no additional Akron agenda segmentation is justified. The publisher already supplies the logical record boundary.

### T4 — retrieval-blind benchmark freeze

The benchmark was generated and curated before any lexical retrieval index was available.

Frozen suite:

- **233** raw candidates
- **37** curated unscored cases
- **54** explicit positive evidence targets
- 8 cross-record lexical cases
- 8 unique lexical cases
- 8 exact-date cases
- 8 publisher-native identifier cases
- 5 deterministic negative controls

Every positive target is canonical `record:1` evidence bound to an exact artifact SHA-256.

The canonical item text contained **0 explicit money facts**. Three comma-formatted `1,200` values describe physical quantities such as `1,200 feet`; Proofline correctly did not reinterpret them as currency.

Freeze receipt:

`experiments/akron-2026/retrieval/R1_TRANSFER_V1_FREEZE.md`

### T5 — first frozen retrieval score

First score workflow: `32302508603`.

The clean scoring rebuild independently reproduced:

- **33** meetings
- **1,475** canonical items
- exact manifest identity `375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`
- **1,509** indexed evidence units including support provenance
- **1,025** structured facts

Result:

- **37/37** expectations met
- **32/32** positive cases hit
- **54/54** explicit positive targets recovered
- **5/5** negative controls passed
- target recall at 10: **1.0**
- provenance validity: **1.0**
- unresolved targets: **0**
- retrieval failure classes: **none**

The final PR head immediately reproduced the same semantic summary in a second clean scoring run.

Score receipt:

`experiments/akron-2026/retrieval/R1_TRANSFER_V1_SCORE.md`

## Current retrieval conclusion

Two write-once real-corpus canonical benchmarks now exist:

| Corpus | Cases | Positive cases | Negative controls | Target recall @10 | Unresolved targets | Retrieval failures |
|---|---:|---:|---:|---:|---:|---:|
| Canton canonical v2 | 42 | 37 | 5 | 1.0 | 0 | 0 |
| Akron transfer v1 | 37 | 32 | 5 | 1.0 | 0 | 0 |

**Semantic/vector retrieval is still not justified by measured evidence.** This is not a claim of universal completeness; it is a complexity gate.

## Current CLI surface

Core:

```bash
proofline ingest <path>
proofline status
proofline trace <observation-id>
proofline review
proofline extract <artifact-id> --ocr tesseract
```

Discovery/watch:

```bash
proofline discover <plan.json>
proofline sync <plan.json>
proofline watch <manifest>
proofline changes
proofline analyze-watch-changes
proofline analyze-versions
proofline-onbase <plan.json>
```

Retrieval/evaluation:

```bash
proofline index
proofline search "terms"
proofline lookup <publisher-native-id>
proofline amounts --min 250000 --max 500000
proofline dates --from 2026-01-01 --to 2026-12-31
proofline identifier <identifier>
proofline evaluate <suite.json> --k 10
```

Analysis/review:

```bash
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

## Validation authority

GitHub Actions is the execution authority for the full repository suite and live-network experiment gates.

Current live gates cover, among other things:

- official-source acquisition and media validation
- source/version provenance
- extraction quality
- stable segment and recurrence identity
- bounded candidate generation
- fact-span containment
- candidate/lead idempotence
- immutable lead packets
- explicit human-review reconstruction
- conservative matter identity
- financial-role assignment boundaries
- authorized financial conflict populations
- generic OnBase source transfer
- Akron atomic evidence
- retrieval-blind benchmark creation
- exact frozen benchmark scoring

## Next development edge

The Akron transfer has now proven acquisition, Silver evidence, atomic evidence identity, deterministic indexing, and frozen retrieval evaluation.

The next bounded question is **supporting-document acquisition**.

Canonical Akron agenda-item summaries contain almost no explicit financial values, but the publisher exposes supporting-document links from some items. The next experiment should therefore:

1. inspect already-acquired canonical item HTML for publisher-declared supporting links;
2. classify link/transport patterns without guessing document IDs;
3. follow only a small deterministic bounded sample;
4. validate actual response bytes/media types rather than trusting link labels or extensions;
5. decide whether a generic OnBase attachment adapter is justified;
6. keep attachment source identity and agenda-item relationship provenance explicit.

Only after richer evidence is acquired should Akron matter-key, financial-role, recurrence, or detector policies be considered. Canton semantic rules must not be transferred by assumption.

Public accusation, outreach, publication, privacy-policy changes affecting real people, paid external deployment, or irreversible publication remain explicit human/product-owner decisions.
