# R1.T14 — Akron financial-representation v2 precision audit

Status: post-hoc contextual audit of the completed R1.T13b blind result. This stage does **not** alter the frozen v2 semantic contract and does **not** authorize a detector.

## Source evidence

R1.T13b completed successfully on PR-head commit `abf3bbfa7eb3b1e9329f0baa9dae72b3416c7b4f`.

- workflow run: `32440471169`
- workflow artifact: `9432387690`
- artifact digest: `sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338`
- selected ranks 33–64 signature: `b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966`
- excluded ranks 1–32 signature: `e0e72779fb4e88f1720ff5f00dcb7ac90a11c83ed56094c32a1da2f478383afb`
- live attachment graph: 2,327 sources, 0 rejected publisher links
- sample: 32 publisher source identities, 28 unique Bronze artifacts, 4 duplicate-Bronze groups
- pages: 270 unique-artifact pages
- OCR: 94 pages attempted, 94 extractions added, 0 failures
- post-OCR low-quality pages: 1; that page contributed no money fact below the 0.70 quality floor
- structured parser: `proofline-structured/v2`
- money facts: 194

The compact result is preserved in `r1_t13b_blind_result_summary.json`. The full workflow artifact remains the canonical execution evidence.

## Blind representation result

Frozen v2 emitted:

- 124 / 194 fully unknown facts
- 70 / 194 facts with a non-unknown amount type
- 70 facts in `akron_municipal_record_context`
- 124 facts with unknown scope/context/amount type

Observed non-unknown amount-type distribution:

- `filing_fee_amount`: 50
- `municipal_form_amount`: 13
- `total_project_amount`: 2
- `estimated_project_cost`: 1
- `grant_context_amount`: 1
- `purchase_price`: 1
- `unit_rate`: 1
- `assessment_rate`: 1

This is a coverage result, not an accuracy result.

## Post-hoc contextual audit

All 70 non-unknown amount-type assignments were inspected against their preserved local T13b context. The audit is assistant-conducted and is **not human-labeled ground truth** or a preregistered accuracy estimate.

Disposition:

- **25 supported** — local text directly supports the assigned type.
- **13 generic by design** — `municipal_form_amount` correctly recognizes a municipal financial form but intentionally leaves the precise field unresolved.
- **32 contradicted** — local text directly supports a different amount meaning than the frozen v2 assignment.

Machine-readable audit: `r1_t14_known_amount_type_audit.json`.

### Dominant error: flattened fee tables

Six holdout documents contain an `Estimated TOTAL Project Cost / Applicable Fee` table. Frozen v2 correctly recognizes `fee_schedule` context but then assigns **all 50 money tokens** `filing_fee_amount` because flat text order cannot preserve the two-column relationship.

Contextual audit:

- 19 actual fee-position tokens support `filing_fee_amount`.
- 31 project-cost threshold/range tokens are contradicted as `filing_fee_amount`.

Examples of contradicted tokens include `$0`, `$20,000`, `$20,001`, `$100,000`, and `$101,001` in the modern schedule, and `$0`, `$6,000`, `$5,001`, `$20,000`, `$100,001`, `$200,000`, and `$200,001` in the older schedule.

This is not primarily a taxonomy problem. It is a **lost row/column structure** problem.

### Assessment amount mislabeled as a rate

Frozen v2 assigns `$220,682.90` the type `assessment_rate` because the surrounding document contains both `resurfacing` and `cash assessed`.

The same preserved context explicitly says:

- residential use rate per linear foot: `6.65`
- charitable use rate per linear foot: `6.65`
- other use rate per linear foot: `8.40`
- `CASH ASSESSED: $220,682.90`

The currency fact is an assessed amount/total, not a rate. This is a direct semantic contradiction.

## New numeric-integrity defect

T13b also exposed a generic structured-parser defect independent of v2 semantic representation.

In one 2026 fee schedule, preserved Silver context contains:

`$20,001___- $100,000`

Explicit `proofline-structured/v2` emits the first fact as:

- raw text: `$20`
- normalized: `20.00`

The full `$20,001` candidate is prevented from satisfying the terminal boundary by trailing OCR underscore characters, but the regex engine backtracks and accepts the shorter `$20` prefix before the comma.

This is another partial-token integrity failure. It is now reproduced by a dedicated regression fixture in `tests/test_akron_v2_precision_audit.py` using **explicit v2**, so historical T13b behavior can remain reproducible after a future parser repair.

## Decision

**Akron financial-detector authorization remains denied.**

The evidence does not justify another round of amount-role regex expansion. Two prerequisites come first:

1. repair the generic partial-token numeric-integrity defect so malformed/OCR-tailed money strings fail closed or parse the complete defensible token;
2. add structure-aware table/field evidence so row/column identity is available before semantic amount typing.

Only after those boundaries are validated should a new semantic representation be frozen and evaluated on a new untouched holdout.

## Non-claims

- T14 does not retroactively tune or revise financial-representation v2.
- The 25/13/32 audit is not a population accuracy estimate.
- The audit is not human ground truth.
- A supported amount type is not transaction identity or proof that repeated occurrences are independent events.
- No anomaly, conflict, suspiciousness, wrongdoing, recurrence, investigative lead, or detector conclusion is produced.
