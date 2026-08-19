# Akron 2026 transfer experiment

This experiment tests whether Proofline's evidence architecture transfers to a second municipal public-record corpus with a different publisher stack **without importing Canton-specific semantic assumptions**.

Source: Akron City Council's official **Hyland OnBase Agenda Online** portal.

Current state: **T1 through T5 complete.**

## Transfer question

Canton established an end-to-end investigative path, but a system that works only for one publisher stack is not yet infrastructure.

Akron intentionally changes the source conditions:

- different publisher software;
- canonical evidence delivered as HTML logical records rather than meeting PDFs;
- publisher-supplied agenda-item boundaries;
- almost no explicit financial values in canonical item summaries.

The transfer experiment therefore tests each layer independently rather than assuming the Canton source profile applies.

## T1 — source-contract probe — complete

The probe was read-only and bounded. It did not sweep or guess numeric meeting IDs. It inspected official publisher pages/routes and followed only publisher-declared paths.

Workflow: `32294171356`

Artifact: `r1-akron-onbase-probe` (`9380590855`)

### Raw shell result

- 7/7 bounded page requests succeeded;
- 5/5 sample meeting pages succeeded;
- raw meeting-page HTML contained **0 substantive agenda bodies**;
- raw meeting-page HTML exposed **0 direct agenda PDF anchors**;
- the visible `Agenda` anchor in the shell was only `#main-content`.

### First-party data contract

Captured OnBase forms/scripts exposed publisher routes for:

1. bounded meeting search;
2. agenda-tree loading;
3. agenda-item loading;
4. nominal agenda `DownloadFile` construction.

Live probe result:

- **32** 2026 City Council meetings discovered in the then-current bounded date search;
- **32** reported an available agenda;
- **3/3** sampled `Documents/ViewAgenda` trees were substantive;
- **6/6** sampled `Meetings/ViewMeetingAgendaItem` responses were substantive;
- **0/3** nominal agenda `DownloadFile` samples returned `%PDF` bytes.

The nominal agenda downloads returned HTML, so Proofline did not weaken transport checks or chase that route.

### Promoted publisher chain

```text
OnBase meeting search
→ embedded SearchResults JSON
→ stable meetingId + AgendaUniqueName
→ Documents/ViewAgenda?meetingId=…
→ publisher-linked loadAgendaItem(itemId, false)
→ Meetings/ViewMeetingAgendaItem canonical evidence
```

Source roles:

- search response = discovery/index provenance;
- agenda tree = supporting provenance;
- agenda item HTML = canonical evidence;
- supporting-document links = deferred to a later bounded attachment contract;
- nominal agenda PDF route = rejected until separately proven.

## T2 — generic production acquisition — complete

PR #56 promoted the T1 contract into the generic `OnBaseAgendaDiscoverer` and installed `proofline-onbase` CLI.

Akron supplies only:

`experiments/akron-2026/onbase-plan.json`

The adapter contains no Akron hostname, Canton semantic policy, or guessed meeting/item range.

Workflow: `32295079984`

Artifact: `r1-akron-onbase-production` (`9381183963`)

### Live production result

A clean 2026 run produced:

- **33** meetings with available agendas;
- **1** preserved bounded meeting-search artifact;
- **33** preserved agenda-tree support artifacts;
- **1,475 canonical agenda-item sources**;
- **0 unavailable canonical items**;
- **1,475/1,475** canonical items with nonblank Silver text;
- **1,475/1,475** meeting the preferred extraction quality floor.

The transferred state contained **1,509 evidence units** including discovery/support provenance.

Ordinary Proofline indexers ran unchanged:

- lexical evidence indexed: **1,509**;
- structured facts: **1,025**.

Immediate rediscovery regenerated the same manifest SHA-256:

`375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`

and canonical watcher counts:

- new: **0**;
- changed: **0**;
- unavailable: **0**;
- unchanged: **1,475**.

## T3 — canonical evidence atomicity — complete

PR #57 tested whether one canonical OnBase agenda-item page already equals one logical evidence record.

Final live validation:

- **1,475 canonical sources**;
- **1,475 canonical evidence units**;
- **0 structural atomicity errors**;
- **1,475/1,475** locator `record:1`;
- **1,475/1,475** exactly one `Item Details` boundary;
- **1,475/1,475** exactly one `Back to Meeting Outline` boundary;
- median item-body length: **218 characters**;
- maximum item-body length: **1,021 characters**;
- **1,011** item bodies containing `ORDINANCE` or `RESOLUTION`;
- **3** short publisher utility items: `Meeting Notice` ×2 and `Files` ×1;
- **0 unknown short-item classes**.

The first structural check incorrectly treated minimum prose length as a proxy for atomicity. A bounded exception probe showed the three short records are legitimate publisher agenda-tree items. The validation rule was corrected rather than lowering a threshold blindly.

### T3 decision

**No additional segmentation is justified for canonical Akron agenda-item sources.**

The publisher already supplies the logical record boundary. Adding derived sub-records without evidence of multiple matters would weaken rather than improve provenance.

## T4 — retrieval-blind benchmark freeze — complete

PR #58 generated the first Akron retrieval benchmark **without consulting retrieval results**.

Workflow: `32300387686`

Artifact: `r1-akron-benchmark-pool-unscored` (`9383051730`)

Artifact digest:

`sha256:d8848900139e7f6e145225ab41e2797f2655171310371e8d99d5b96d4b010f0f`

The workflow deliberately did not build a lexical search index before selection. It generated the broad pool twice and required byte-identical output, then curated only by deterministic question/target-quality rules.

### Frozen suite

- **233** raw candidates;
- **37** curated cases;
- **54** explicit positive evidence targets;
- 8 cross-record lexical/entity cases;
- 8 unique lexical/entity cases;
- 8 exact-date cases;
- 8 publisher-native identifier cases;
- 5 deterministic negative controls.

Every positive target is:

- a source classified `canonical` by `source-policy.json`;
- locator `record:1`;
- bound to an exact artifact SHA-256.

Question-quality curation rejected publisher UI fragments, incomplete phrases, all-caps fragments, and a repeated-edge-token fragment before any retrieval score existed.

### Money absence

The canonical item text contained:

- **0** structured money facts;
- **0** `$` markers;
- **0** `USD` markers;
- **0** `dollar(s)` markers.

Three comma-formatted `1,200` occurrences describe a physical quantity such as `1,200 feet` and were correctly not promoted to money.

Therefore the frozen suite contains no positive money case. The negative money control remains.

Freeze receipt:

`retrieval/R1_TRANSFER_V1_FREEZE.md`

Frozen benchmark:

`retrieval/r1-transfer-v1-unscored.json.gz`

Decompressed benchmark SHA-256:

`fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681`

## T5 — first frozen retrieval score — complete

PR #59 performed the first retrieval consultation only **after** T4 existed in Git history.

First scoring workflow: `32302508603`

Artifact: `r1-akron-retrieval-evaluation` (`9383700181`)

Artifact digest:

`sha256:7406e8c84cb8bedc0363bfd0c586cafb2cba113bf433d4fd351d45bbad945e9a`

### Independent live rebuild

The scoring run reproduced:

- **33** meetings;
- **1,475** canonical items;
- **0 unavailable** canonical items;
- exact manifest identity `375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`;
- **1,509** indexed evidence units including support provenance;
- **1,025** structured facts.

### First score

Raw evaluator:

- **37/37** expectations met;
- positive hit rate at 10: **1.0**;
- target recall at 10: **1.0**;
- negative accuracy: **1.0**;
- provenance validity: **1.0**;
- unresolved target count: **0**;
- failure classes: **none**.

Scorable report:

- **37/37** scorable;
- **0** unscorable;
- **32/32** positive cases hit;
- **54/54** explicit positive targets recovered;
- **5/5** negative controls passed;
- mean scorable provenance validity: **1.0**;
- retrieval failures: **0**.

A second clean run on the final PR head reproduced the same semantic summary and manifest identity.

Score receipt:

`retrieval/R1_TRANSFER_V1_SCORE.md`

Exact compact first-score bundle:

`retrieval/r1-transfer-v1-score-core.tar.gz`

## Transfer conclusion through T5

### Transferred unchanged

- immutable artifact storage and SHA identity;
- source/snapshot chronology;
- watcher download/change semantics;
- Silver extraction and quality handling;
- lexical indexing;
- structured indexing;
- native-identifier lookup;
- evidence-target resolution;
- retrieval evaluation and scorable reporting.

### Source-specific infrastructure required

- bounded OnBase meeting-search contract;
- embedded first-party `SearchResults` parser;
- agenda-tree parser for publisher `loadAgendaItem(id, false)` links;
- stable agenda-item canonical source construction.

### Explicitly **not** transferred by assumption

- Canton agenda segmentation;
- Canton matter-key policy;
- Canton financial-role policy;
- Canton recurrence/detector configuration.

Akron already disproved one assumption: unlike Canton, it needs **no additional agenda segmentation**.

## Retrieval complexity decision

The first Akron frozen benchmark exposed no deterministic retrieval failure. Combined with the 42-case frozen Canton canonical benchmark, there is still no measured evidence requiring semantic/vector retrieval.

This is a complexity gate, not a claim of universal retrieval completeness.

## Next transfer stage — bounded supporting-document contract

The canonical Akron item summaries are structurally clean but information-light for financial analysis. Some publisher pages expose `Supporting Documents` links.

The next experiment should therefore probe that attachment boundary before any production ingestion:

1. rebuild/preserve the canonical item corpus through the existing adapter;
2. inspect those already-acquired item HTML artifacts locally for publisher-declared supporting links;
3. classify link shapes and same-instance relationships without guessing IDs;
4. select a small deterministic bounded sample of discovered links;
5. fetch only that sample and validate actual bytes, media type, redirect behavior, and stable source identity;
6. decide whether a generic OnBase attachment adapter is justified.

No supporting-document link label, filename extension, or nominal route will be trusted as a media-type assertion until the returned bytes validate it.
