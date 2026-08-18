# Source Discovery

Proofline separates **finding public resources** from **watching public resources**.

That distinction matters because a static URL manifest is reproducible but not continuous: if a public agency adds a new meeting document, Proofline cannot watch a URL it never learned about.

The discovery layer solves only that problem.

## Data flow

```text
official index page
      |
      v
preserve index artifact
      |
      v
source-specific deterministic parser
      |
      v
generated source manifest
      |
      v
existing Proofline watcher
```

Discovery does not bypass Bronze provenance. The public index page that advertised a resource is fetched and preserved through the same watcher/ingest path before its links are interpreted.

## Discovery plans

The first plan schema is:

```text
proofline-discovery-plan/v1
```

Example:

```json
{
  "schema": "proofline-discovery-plan/v1",
  "name": "example-public-records",
  "discoverers": [
    {
      "type": "civicengage_agenda_center",
      "source_uri": "https://example.gov/AgendaCenter",
      "categories": ["Board of Control", "City Council"],
      "years": [2026],
      "formats": ["pdf"],
      "include_previous_versions": true
    }
  ]
}
```

## Commands

Discover resources and write a deterministic manifest:

```bash
proofline discover plan.json
```

By default the manifest is written under:

```text
.proofline/manifests/<plan-name>.json
```

Discover, watch the discovered resources, and rebuild retrieval indexes in one deterministic cycle:

```bash
proofline sync plan.json
```

Scheduling remains external. A scheduler may invoke `proofline sync` repeatedly; the evidence semantics do not depend on the scheduler.

## CivicEngage Agenda Center adapter

The initial adapter is intentionally narrow.

It reads the official Agenda Center HTML and tracks the current `h2` category and `h3` meeting label. It only accepts document links explicitly published under configured categories and years.

Supported resource formats:

- HTML
- PDF
- Packet
- published `Previous Versions` listing pages

The adapter does not recursively crawl arbitrary same-domain links.

## Previous Versions

A `Previous Versions` link is preserved as a watchable source when enabled.

This means:

> The publisher exposes a revision-history page for this meeting record.

It does **not** mean:

> The record was improperly changed.

A later extraction adapter may enumerate the historical versions linked from that page. Until then the listing itself is preserved longitudinally so changes to the listing are not lost.

## Generated manifests are derivatives

A generated watch manifest is not public-source evidence. It is a deterministic derivative of a preserved public index artifact plus a versioned discovery parser.

The manifest is therefore disposable and regenerable. The index bytes and downloaded public records are not.

## Scope safety

Discovery should remain explicit and bounded. Adding a new source-specific adapter is preferable to turning Proofline into a general crawler with unclear collection boundaries.

A discovery adapter should state:

- which index type it understands;
- which links it considers public records;
- how it derives native identifiers;
- which filters are applied;
- what it deliberately ignores.
