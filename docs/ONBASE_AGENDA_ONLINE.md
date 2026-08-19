# OnBase Agenda Online discovery

Proofline's OnBase adapter is a generic source-discovery layer for Hyland OnBase Agenda Online instances whose publisher contract exposes the structures validated by the Akron T1 experiment.

It does **not** scrape arbitrary rendered pages, sweep numeric IDs, or infer document URLs from filenames.

## Plan

Schema:

`proofline-onbase-agenda-plan/v1`

Example:

```json
{
  "schema": "proofline-onbase-agenda-plan/v1",
  "name": "example-council-2026",
  "source_uri": "https://records.example.gov/OnBaseAgendaOnline/Meetings",
  "meeting_type_ids": [101],
  "years": [2026]
}
```

`source_uri` must identify the instance's `/Meetings` endpoint and may not carry query or fragment state.

## Discovery chain

For each declared year, Proofline constructs the publisher's custom-date meeting search using:

- `dropid=11`;
- configured `mtids`;
- `dropsv=01/01/YYYY`;
- `dropev=12/31/YYYY`.

The adapter then follows this deterministic chain:

```text
meeting search
→ embedded SearchResults JSON
→ meetings with IsAgendaAvailable=true
→ Documents/ViewAgenda for each meetingId
→ loadAgendaItem(itemId, false) publisher links
→ Meetings/ViewMeetingAgendaItem canonical source URI
```

Only JSON embedded inside the first-party `SearchResults` constructor is parsed. It is decoded with `json.loads`; page JavaScript is never executed.

Only `loadAgendaItem(<integer>, false)` links become canonical agenda items. Section calls (`true`) and unrelated JavaScript links are ignored.

## Source roles

### Discovery/index evidence

Meeting-search responses are preserved through the normal `CorpusWatcher` and reported as `index_artifact_ids`.

### Supporting provenance

Agenda-tree responses are also preserved through the watcher and reported as `supporting_artifact_ids`.

### Canonical evidence

Each agenda item becomes a normal `proofline-source-manifest/v1` resource:

- stable publisher URI;
- deterministic native identifier based on instance + meeting ID + item ID;
- expected media type `text/html`.

The ordinary Proofline watcher then downloads, hashes, ingests, versions, and extracts those item pages. OnBase therefore does not introduce a second Bronze/Silver pipeline.

## Identity and transport rules

Canonical source identity is the stable publisher agenda-item URI and native meeting/item identifiers.

Proofline does not use:

- cookies or session values as identity;
- rendered browser state;
- inferred/guessed IDs;
- transient URLs;
- nominal agenda PDF URLs unless that transport is separately proven to return valid PDF bytes.

The Akron T1 probe specifically found that nominal agenda `DownloadFile` samples returned HTML instead of PDF magic bytes. The production adapter therefore does not use that path.

## CLI

```bash
proofline-onbase \
  --state-dir .akron \
  --manifest-out .akron/agenda-items.json \
  experiments/akron-2026/onbase-plan.json
```

By default the command preserves discovery/support artifacts, emits the canonical manifest, and syncs the canonical agenda-item resources through the ordinary watcher.

Use `--discover-only` to stop after manifest derivation.

## Transfer boundary

This adapter solves **source acquisition only**. It does not imply that Canton segmentation, matter-key, financial-role, or detector policies apply to an OnBase corpus.

Those semantic layers require separate source-profile evidence and transfer validation.
