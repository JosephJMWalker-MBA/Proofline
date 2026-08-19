# Durable human review records

Proofline separates **machine-derived evidence state** from **human judgment**.

A `Lead` packet is immutable once created. Human disposition does not rewrite the packet. Instead, Proofline appends a review event and derives the current human status from the review-event history.

For reproducible real-corpus work, a human decision can also be stored as a version-controlled review receipt using:

```text
proofline-lead-review/v1
```

## Why review receipts exist

CI and research rebuilds use fresh state directories. A review event stored only inside one generated SQLite database would disappear when that state directory is discarded.

A durable review receipt preserves the human decision independently of a particular database instance, so Proofline can:

1. rebuild the evidence and deterministic lead from source;
2. verify that the exact same lead identity still exists;
3. append the recorded human review event;
4. derive the reviewed state;
5. reject silent transfer of an old judgment to a different future lead.

## Schema

Example:

```json
{
  "schema": "proofline-lead-review/v1",
  "lead_id": "lead:...",
  "status": "explained",
  "reviewer": "Joseph Walker",
  "occurred_at": "2026-08-19T17:14:00+00:00",
  "rationale": "The underlying records describe sequential deadline amendments.",
  "notes": [
    "No misconduct inference."
  ]
}
```

Required fields:

- `schema` — exactly `proofline-lead-review/v1`
- `lead_id` — exact deterministic lead identity
- `status` — one R0 review disposition
- `reviewer` — named human reviewer
- `occurred_at` — timezone-aware ISO-8601 timestamp
- `rationale` — explicit reason for the disposition

Optional:

- `notes` — list of additional textual notes

## R0 review statuses

Allowed review dispositions are:

- `triaged`
- `investigating`
- `explained`
- `corroborated`
- `rejected`
- `archived`

`published` is deliberately excluded from the R0 review-record path.

Publication is a separate product/editorial action, not an ordinary review-state transition.

## Identity binding

A review receipt is bound to the exact `lead_id` it names.

This is intentional. If evidence, detector policy, or lead packaging changes enough to produce a different lead identity, an old review must **not** be inherited automatically.

The R0 live workflow therefore fails if the stored review receipt no longer matches the deterministic lead regenerated from the public corpus.

That failure means a human should inspect the new evidence packet and make a new judgment.

## Immutability semantics

The lead packet keeps its stored status:

```text
candidate
```

Human review creates an append-only event. The displayed/current disposition is derived from the latest review event.

For example:

```text
immutable lead packet: candidate
review event: explained
current derived status: explained
```

This preserves the distinction between what the machine produced and what a person concluded.

## Idempotence

The review event ID is deterministic over:

- lead ID
- timestamp
- status
- reviewer
- rationale
- notes

Applying the same receipt again returns the existing event rather than creating a duplicate.

Changing the rationale, reviewer, timestamp, status, or notes defines a different human review event and therefore a different event ID.

## First R0 review

The first durable human review record is:

```text
experiments/canton-2026/reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json
```

It records:

- reviewer: **Joseph Walker**
- disposition: **explained**
- rationale: the Board of Control records describe sequential expenditure-deadline amendments, providing an ordinary explanation for the machine-selected date variation
- no inference of misconduct

The live R0 workflow rebuilds the public corpus, regenerates the exact lead, verifies machine-only state first, then applies this receipt and proves the derived disposition is `explained`.

## General policy

Durable review records are appropriate when a human judgment should survive ephemeral compute state and remain auditable alongside the code/evidence pipeline.

They do **not** authorize:

- public accusation
- external outreach
- publication
- privacy-policy changes affecting real people
- irreversible disclosure

Those remain separate explicit human/product-owner decisions.
