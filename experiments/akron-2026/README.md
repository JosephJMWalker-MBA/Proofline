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

- **32** 2026 City Council meetings discovered in the bounded custom-date search;
- **32** reported an available agenda;
- **3/3** sampled `Documents/ViewAgenda` agenda-tree responses were substantive;
- **6/6** sampled `Meetings/ViewMeetingAgendaItem` responses were substantive;
- **0/3** nominal agenda `DownloadFile` samples returned PDF magic bytes.

The nominal agenda downloads returned small HTML responses rather than `%PDF` bytes. That failure is retained as part of the source-contract evidence; the adapter will not weaken transport checks or chase the nominal PDF path.

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

## Promotion rule — satisfied

The publisher exposes a reproducible official chain from a bounded search surface to stable meeting and agenda-item identities. A production OnBase discovery adapter is therefore justified.

Canonical source identity must remain the stable OnBase publisher URL/meeting/item identifiers. Session state, cookies, rendered UI state, or transient transport URLs must never become evidence identity.

## Next transfer stage

T2 will add a generic **OnBase Agenda Online** discoverer to Proofline's existing discovery/watcher pipeline. It will initially emit only canonical agenda-item HTML resources and preserve search/agenda-tree responses as supporting provenance.

The subsequent transfer measurements remain separate:

1. Bronze/source acquisition reuse;
2. Silver extraction quality;
3. segmentation portability;
4. retrieval benchmark portability;
5. matter-key policy portability;
6. financial-role policy portability;
7. detector behavior, including valid zero-result outcomes.

Canton-specific segmentation, matter-key, and financial-role rules are not presumed to apply to Akron.