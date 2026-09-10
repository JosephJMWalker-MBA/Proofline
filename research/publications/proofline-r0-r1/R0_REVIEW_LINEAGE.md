# R0 Human-Review Lineage

> **Purpose:** Preserve the exact human-review identity transition relevant to the first Proofline publication. This is supporting publication evidence, not a new experiment result.

## Initial reviewed lead

Review receipt:

`experiments/canton-2026/reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json`

Receipt Git blob SHA:

`3df44180f7c0004bbb84a374f62e6b84e70b300b`

Lead identity:

`lead:3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c`

Disposition:

`explained`

Reviewer:

`Joseph Walker`

Review time:

`2026-08-19T17:14:00+00:00`

Rationale recorded in the receipt:

> The underlying Board of Control records describe sequential expenditure-deadline amendments. The recurring $185,000 amount and July 31 handoff are consistent with continuity of the same administrative matter; the evidence currently provides an ordinary explanation for why Proofline surfaced the changing dates. No evidence of misconduct is inferred.

## Segmentation correction

A later Board compound-ordinance segmentation correction changed the deterministic derivation identity of the lead.

Proofline did **not** transfer the earlier human disposition automatically to the new deterministic lead identity.

That is the behavior the review-record contract requires: a stored human judgment is bound to the exact `lead_id` named by the receipt. If evidence, detector policy, segmentation, or lead packaging changes enough to produce a different lead identity, the old review cannot silently authorize the new one.

## Corrected reviewed lead

Review receipt:

`experiments/canton-2026/reviews/lead-ab70a8e49322a7662e31fa1331926d34358a549527b293427c96ade005206a51.json`

Receipt Git blob SHA:

`2d8228198d093743ecc01225afcf514aeba2c344`

Corrected lead identity:

`lead:ab70a8e49322a7662e31fa1331926d34358a549527b293427c96ade005206a51`

Disposition:

`explained`

Reviewer:

`Joseph Walker`

Review time:

`2026-08-19T18:56:00+00:00`

The second receipt explicitly states that the disposition was **re-affirmed after the segmentation correction changed the deterministic lead identity**. It also records that the prior reviewed lead remains preserved as historical review evidence.

The substantive rationale remained unchanged: the corrected lead retained the same ECDI evidence, $185,000 amount, July 31 handoff, varying deadline dates, ordinary explanations, and questions worth asking; only the derivation identity changed.

## Publication claim supported by this lineage

The first paper may state:

> Proofline binds human review to exact deterministic lead identity. When a segmentation correction changed the lead identity, the prior review was preserved but not silently inherited; a second human review receipt explicitly re-affirmed the `explained` disposition for the corrected lead.

This is stronger and more precise than merely saying that review events are append-only.

## Claims this lineage does not support

It does not establish:

- inter-rater reliability;
- unbiased human judgment;
- correctness of the human explanation as a universal ground truth;
- corruption detection accuracy;
- false-positive rate;
- calibrated investigative significance; or
- any claim about other leads or municipalities.

## Governing implementation documentation

`docs/REVIEW_RECORDS.md`

That document states that:

- a lead packet remains machine-created `candidate` state;
- human disposition is appended separately;
- current human status is derived from review-event history;
- durable review receipts survive ephemeral compute state;
- a review receipt is bound to exact `lead_id`; and
- mismatched regenerated lead identity requires renewed human inspection rather than silent transfer.

## Manuscript edit gate

Before the manuscript is declared review-ready, section 4.1 or section 7 should be revised to mention the identity change and explicit re-affirmation. The current draft is not false, but it omits this stronger lineage evidence.
