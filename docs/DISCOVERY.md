# Source Discovery

Proofline separates **finding public resources** from **watching public resources**.

That distinction matters because a static URL manifest is reproducible but not continuous: if a public agency adds a new meeting document, Proofline cannot watch a URL it never learned about.

The discovery layer solves only that problem. It is deliberately source-specific and bounded rather than a general crawler.

## Data flow

```text
official publisher index / calendar
        |
        v
preserve discovery artifact
        |
        v
source-specific deterministic parser
        |
        +----> preserve supporting publisher pages / metadata
        |
        v
generated source manifest
        |
        v
existing Proofline watcher
```

Discovery does not bypass Bronze provenance. Public pages or metadata used to derive record URLs are fetched and preserved through the same watcher/ingest path before their contents are interpreted.

## Discovery plans

The current schema is:

```text
proofline-discovery-plan/v1
```

A plan may combine multiple source-specific discoverers. The R0 Canton plan uses one discoverer for Board of Control and another for City Council because the publisher exposes usable records through different systems.

Example:

```json
{
  "schema": "proofline-discovery-plan/v1",
  "name": "example-public-records",
  "discoverers": [
    {
      "type": "civicengage_agenda_center",
      "source_uri": "https://example.gov/AgendaCenter",
      "categories": ["Board of Control"],
      "years": [2026],
      "formats": ["pdf"],
      "include_previous_versions": true
    },
    {
      "type": "civicclerk_calendar",
      "source_uri": "https://example.gov/calendar.aspx?CID=31",
      "years": [2026],
      "event_text": "City Council Regular Meeting Agenda (PDF)",
      "file_types": ["Agenda"]
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

Discover, watch the discovered resources, run publisher-backed version analysis, and rebuild retrieval indexes in one deterministic cycle:

```bash
proofline sync plan.json
```

Scheduling remains external. A scheduler may invoke `proofline sync` repeatedly; evidence semantics do not depend on scheduling policy.

## CivicEngage Agenda Center adapter

The CivicEngage adapter reads the official Agenda Center HTML and tracks the current `h2` category and `h3` meeting label. It only accepts document links explicitly published under configured categories and years.

Supported resource formats:

- HTML
- PDF
- Packet
- published `Previous Versions` listing pages

The adapter does not recursively crawl arbitrary same-domain links.

### Previous Versions

When enabled, a `Previous Versions` page is preserved as a supporting publisher artifact. Proofline then enumerates only explicitly linked `/ArchivedAgenda/` resources that match the requested formats.

Current `/Agenda/` links on the version-listing page are not emitted as historical records. That prevents one current record from masquerading as independent corroboration.

A preserved version-listing artifact can establish an append-only relation:

```text
archived source --historical_version_of--> current source
```

That relation means the publisher linked the two records through its version-history interface. It does **not** mean the change was improper, suspicious, or material.

## Official Calendar → CivicClerk adapter

Some CivicEngage meeting records are only pointer wrappers and contain no substantive meeting evidence. Proofline does not respond by crawling arbitrary links or disabling transport security. A separate bounded adapter is used when the publisher's official calendar explicitly points to CivicClerk.

The discovery chain is:

```text
official calendar month listing
    |
    | exact configured event text, same official host
    v
official calendar event page
    |
    | explicit publisher link only
    v
<tenant>.portal.civicclerk.com/event/<id>/files
    |
    | structurally derive the same tenant + event ID
    v
<tenant>.api.civicclerk.com/v1/Events/<id>
    |
    | preserve public event metadata
    | select configured published file type
    | require fileId to agree with publisher URL
    v
stable Meetings/GetMeetingFile(fileId=...,plainText=false) source URI
```

### Bounded calendar discovery

For each configured year, Proofline generates exactly twelve month-list URLs while preserving the configured calendar filters such as `CID`.

An event is accepted only when:

- its anchor text exactly matches the configured `event_text` after whitespace normalization;
- the event page remains on the same official calendar host;
- it exposes a numeric event ID.

### CivicClerk trust boundaries

The event page may establish a CivicClerk event only through a structurally valid HTTPS link of the form:

```text
https://<tenant>.portal.civicclerk.com/event/<id>/files
```

From that publisher-linked page Proofline derives:

```text
https://<tenant>.api.civicclerk.com/v1/Events/<id>
```

The event metadata is itself preserved as Bronze supporting evidence before file records are interpreted.

A published file is emitted only when:

- the event date is in the configured year scope;
- the file `type` matches a configured `file_types` value such as `Agenda`;
- `fileId` is an integer;
- the stable file URL uses the same CivicClerk tenant;
- the URL structurally matches `Meetings/GetMeetingFile(fileId=<same id>,plainText=false)`;
- the stable URL has no unexpected query string or fragment.

No CivicClerk event IDs or file IDs are hardcoded into production discovery.

## Stable source versus short-lived transport

CivicClerk's stable file API returns a JSON envelope containing a short-lived signed Azure blob transport. Proofline treats these as different concepts:

```text
canonical source identity
    = stable CivicClerk Meetings/GetMeetingFile(fileId=...) URI

acquisition transport
    = ephemeral validated blobUri used in-memory only
```

The signed blob URI is never promoted to source identity and its SAS query token is never persisted. See [SOURCE_MANIFEST.md](SOURCE_MANIFEST.md) for the watcher-side `civicclerk_blob` fetch strategy.

This matters for longitudinal semantics: a rotated transport token with identical PDF bytes is `unchanged`; changed PDF bytes behind the same stable publisher file URI are `changed`.

## Generated manifests are derivatives

A generated watch manifest is not public-source evidence. It is a deterministic derivative of preserved publisher artifacts plus versioned discovery parsers.

The manifest is therefore disposable and regenerable. The preserved discovery/supporting bytes and downloaded public records are not.

## Scope safety

Discovery should remain explicit and bounded. Adding a source-specific adapter is preferable to turning Proofline into a general crawler with unclear collection boundaries.

A discovery adapter should state:

- which publisher index/system it understands;
- which links it considers public records;
- which intermediate publisher artifacts it preserves;
- how it derives native identifiers;
- which filters are applied;
- which host/path transitions are allowed;
- what it deliberately ignores.
