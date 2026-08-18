# Source Manifest Contract — v1

Proofline watches public resources from an explicit, versioned JSON manifest. The manifest says **what should be checked**; the watcher records **what was actually observed** on each run.

## Minimal manifest

```json
{
  "schema": "proofline-source-manifest/v1",
  "name": "City procurement releases",
  "resources": [
    {
      "source_uri": "https://example.gov/contracts/2026-001.pdf"
    }
  ]
}
```

The current watcher accepts `http` and `https` resources.

## Resource fields

| Field | Required | Meaning |
|---|---:|---|
| `source_uri` | yes | Canonical public URL Proofline should revisit. |
| `source_name` | no | Human-readable source label. |
| `native_identifier` | no | Identifier assigned by the publishing system, such as a docket, contract, accession, Bates, permit, or report number. |
| `expected_media_type` | no | Expected HTTP media type. A mismatch is recorded as an unavailable/invalid check rather than silently ingested. |
| `sequence_group` | no | Explicit name for an identifier sequence whose gaps should be checked. |
| `sequence_number` | no | Integer position within `sequence_group`. Must be supplied together with `sequence_group`. |

Proofline does not infer sequence numbers from filenames. If a publisher's numbering scheme is meaningful enough to audit, it should be encoded explicitly or supplied by a source-specific adapter later.

## Watch states

Each visit produces exactly one state for each resource:

- `new` — no successful prior observation exists and bytes were retrieved successfully.
- `unchanged` — the retrieved bytes have the same SHA-256 artifact identity as the immediately prior successful observation.
- `changed` — the retrieved bytes differ from the immediately prior successful observation.
- `unavailable` — Proofline could not validate and ingest bytes during this check.

`unavailable` does **not** mean a publisher intentionally removed a record. A 404, 500, timeout, network failure, access-control response, or media-validation failure can all produce this state. The HTTP/error context is retained for human interpretation.

## Reversions are temporal changes

Suppose one URL produces these byte versions over four successful checks:

```text
A -> B -> A -> A
```

Proofline reports:

```text
new -> changed -> changed -> unchanged
```

The third observation is a real change from the immediately prior public state even though artifact `A` was already known. The fourth is unchanged because the watcher compares against the previous successful visit, not against the newest unique artifact in the corpus.

This distinction is important for longitudinal investigations: the Bronze artifact map answers **which byte versions have ever existed**, while the append-only watcher ledger answers **which version was present on each visit**.

## HTTP provenance

When available, each watcher check records:

- HTTP status
- normalized `Content-Type`
- `ETag`
- `Last-Modified`
- number of acquisition attempts
- error text for failed checks
- check time
- run ID
- previous and current artifact IDs

These fields are evidence about acquisition behavior. They are not proof of intent or authorship.

## Acquisition integrity

Successful downloads are streamed into temporary storage, validated, and then passed into Proofline's SHA-256 content-addressed artifact store. PDF responses are checked for PDF magic bytes when the response or manifest says they are PDFs.

Transient HTTP `429` and `5xx` responses are retried with exponential backoff. Prior artifacts are never deleted when a later check fails.

## Sequence gaps

Sequence-gap output is purely structural. Given explicit manifest numbers:

```text
1, 2, 4
```

Proofline can report:

```json
{
  "sequence_group": "dataset-a",
  "observed_min": 1,
  "observed_max": 4,
  "missing": [3]
}
```

This means only that the declared sequence lacks `3`. It does not establish that a document existed, was withheld, was deleted, or should have been published. Source-specific rules may later add stronger semantics when the publishing system documents them.

## CLI

```bash
proofline watch examples/source-manifest.json
proofline changes
proofline changes --include-unchanged
```

`proofline changes` reads the append-only watcher ledger. By default it hides `unchanged` rows so new, changed, and unavailable resources are easier to review.

## Scheduling

`proofline watch` is intentionally one deterministic run. Repetition should initially be scheduled by a deployment layer such as cron, systemd timers, a container scheduler, or a hosted job runner rather than hiding a daemon inside the evidence core.

That keeps scheduling policy separate from evidence semantics: the same manifest and command can be run manually, hourly, daily, or event-triggered without changing how Proofline classifies a source observation.
