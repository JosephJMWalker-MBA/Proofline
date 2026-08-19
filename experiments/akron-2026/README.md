# Akron 2026 transfer experiment

This experiment tests whether Proofline's evidence architecture transfers to a second municipal public-record corpus with a different publisher stack.

Source: Akron City Council's official **OnBase Agenda Online** portal.

## T1 — source-contract probe — complete

The probe was read-only and bounded. It did not sweep or guess numeric meeting IDs. It inspected official publisher pages/routes and followed only publisher-declared paths.

Workflow: `32294171356`

Artifact: `r1-akron-onbase-probe` (`9380590855`)

### Stage 1: raw meeting-page shells

The initial probe established a useful negative result:

- 7/7 bounded page requests succeeded;
- 5/5 sample meeting pages succeeded;
- raw meeting-page HTML contained **0 substantive agenda bodies**;
- raw meeting-page HTML exposed **0 direct agenda PDF anchors**;
- the visible `Agenda` anchor in the shell was only `#main-content`.

Therefore the production adapter must not treat the meeting shell as canonical evidence and must not infer a PDF URL from the visible shell alone.

### Stage 2: publisher-declared data paths

The captured first-party OnBase forms/scripts exposed explicit routes for:

1. bounded meeting search;
2. agenda-tree loading;
3. agenda-item loading;
4. agenda `DownloadFile` construction.

The second probe used those publisher-declared routes directly.

Live result:

- **32** 2026 City Council meetings discovered in the bounded Jan 1–Aug 19 custom-date search;
- **32** reported an available agenda;
- **3/3** sampled `Documents/ViewAgenda` agenda-tree responses were substantive;
- **6/6** sampled `Meetings/ViewMeetingAgendaItem` responses were substantive;
- **0/3** nominal agenda `DownloadFile` samples returned PDF magic bytes.

The nominal agenda downloads returned small HTML responses rather than `%PDF` bytes. That failure is retained as part of the source-contract evidence; the adapter does not weaken transport checks or chase the nominal PDF path.

## Publisher contract selected for production

The promotable official chain is:

```text
OnBase meeting search
→ embedded SearchResults JSON
→ stable meetingId + AgendaUniqueName
→ Documents/ViewAgenda?meetingId=…
→ publisher-linked agenda item IDs
→ Meetings/ViewMeetingAgendaItem?meetingId=…&itemId=…&isSection=false&type=agenda
```

For Akron, the best canonical evidence unit is therefore the **agenda-item HTML endpoint**, not a meeting PDF.

### Source roles

- meeting search response: discovery/support provenance;
- agenda-tree response: discovery/support provenance;
- agenda-item endpoint: canonical substantive evidence;
- supporting-document links from an agenda item: publisher-linked resources for a later bounded attachment stage;
- nominal agenda PDF transport: rejected for now because the probe did not receive PDF bytes.

This is an intentional transfer contrast with Canton. Proofline's evidence model permits a stable logical source unit to be canonical evidence; canonical evidence does not have to be a PDF.

## T2 — production acquisition transfer — complete

PR #56 promotes the proven source contract into a generic `OnBaseAgendaDiscoverer` and installed `proofline-onbase` CLI. Akron supplies only a source plan:

`experiments/akron-2026/onbase-plan.json`

The core adapter contains no Akron hostname, City Council text, Canton policy, or guessed meeting/item range.

Workflow: `32295079984`

Artifact: `r1-akron-onbase-production` (`9381183963`)

### Live production result

A clean 2026 full-year discovery/sync produced:

- **33** meetings with available agendas;
- **33** preserved agenda-tree supporting artifacts;
- **1** preserved bounded meeting-search artifact;
- **1,475 canonical agenda-item sources**;
- **0 unavailable canonical items**;
- **1,475 / 1,475** canonical items with nonblank Silver text;
- **1,475 / 1,475** with at least 120 visible-text characters;
- **1,475 / 1,475** meeting the preferred extraction quality floor.

Together the state contains **1,509 evidence units**: 1 search response + 33 agenda trees + 1,475 canonical item pages.

The ordinary Proofline indexers ran unchanged over the transferred state:

- lexical evidence indexed: **1,509**;
- structured facts extracted: **1,025**.

No special OnBase evidence database or extraction pipeline was introduced.

### Immediate rerun

The second production run regenerated the same manifest SHA-256:

`375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`

The serialized manifest was byte-identical and the canonical watcher result was:

- new: **0**;
- changed: **0**;
- unavailable: **0**;
- unchanged: **1,475**.

This validates deterministic discovery and stable canonical source identity on the live publisher.

## Transfer conclusions after T2

### Transferred unchanged

- immutable artifact storage;
- SHA-based artifact identity;
- source/snapshot chronology;
- watcher download/change semantics;
- HTML Silver extraction;
- preferred extraction quality handling;
- lexical indexing;
- structured indexing;
- canonical logical evidence units.

### New source-specific infrastructure

- bounded OnBase meeting-search contract;
- embedded `SearchResults` JSON parser;
- agenda-tree parser for publisher `loadAgendaItem(id, false)` links;
- stable agenda-item canonical source construction.

### Not transferred yet

Canton-specific:

- agenda-item segmentation rules;
- matter-key policy;
- financial-role policy;
- recurrence/detector configuration.

Those remain unproven on Akron and must not be reused by assumption.

## Next transfer stage

T3 should characterize the canonical Akron item text and define the **smallest necessary segmentation policy**. Because each canonical source is already one agenda item, the correct answer may be *no additional segmentation at all*. That should be measured rather than assumed.

After the evidence-unit boundary is settled, the next retrieval benchmark must again be generated/frozen without consulting retrieval results before scoring.
