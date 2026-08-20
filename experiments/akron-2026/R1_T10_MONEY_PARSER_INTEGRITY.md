# R1.T10 — Structured money parser integrity

## Decision

Proofline's generic structured money parser is promoted from `proofline-structured/v1` to `proofline-structured/v2` for current builds.

The change is intentionally narrow. R1.T9 proved two cases where preferred Silver text was high quality but the structured parser emitted a numerically incomplete money fact. R1.T10 repairs those cases while preserving v1 as an explicit historical parser contract for frozen experiment reproduction.

No Akron financial-role classifier or detector is introduced here.

## Triggering evidence

R1.T9 reproduced the exact frozen 31-money-fact population against the same seven money-bearing Bronze artifacts and exposed local preferred-Silver context for every token.

Two facts were demonstrably parser-invalid despite preferred extraction quality between `0.9996` and `1.0`:

1. Silver text:

   `Total expenditure (if applicable): $ 51 ,780.00`

   v1 fact:

   - raw token: `$ 51`
   - normalized value: `51.00`

   The parser stopped before whitespace-separated thousands punctuation.

2. Silver text:

   `Sold over $138MM since 2013, 466+ transactions`

   v1 fact:

   - raw token: `$138`
   - normalized value: `138.00`

   The parser stopped before the contiguous `MM` magnitude suffix.

The second value remains private biographical sales-volume context. Correcting its numeric parse does **not** make it a municipal expenditure, contract, award, appropriation, receipt, or investigative lead.

## Parser contract

### Current parser — `proofline-structured/v2`

For explicit free-form currency syntax, v2:

- preserves and parses whitespace around thousands separators;
- consumes the complete recognized magnitude-suffixed token;
- normalizes a finite supported magnitude set:
  - `K` → 1,000
  - `M` / `MM` → 1,000,000
  - `B` / `BN` → 1,000,000,000;
- rejects unknown attached alphabetic suffixes rather than silently emitting a shorter dollar fragment;
- preserves character anchors for the complete consumed money token.

### Historical parser — `proofline-structured/v1`

v1 remains explicitly selectable through the structured extraction/build API. This is not a compatibility alias to v2: it preserves the exact deterministic behavior that generated the T8/T9 frozen receipts.

The T9 workflow now runs current extraction/OCR, then explicitly rebuilds structured facts with v1 before checking the frozen 31-fact signature and token anchors.

This keeps two different claims separate:

- **current parser correctness can improve**;
- **historical experiment outputs remain reproducible under the parser version that produced them**.

## Live validation

Validated branch head:

`cecd318c0caebe9e7886c6f6bbfb5ad273ea43a5`

T10 workflow:

`32385653383`

Artifact:

`r1-akron-money-parser-integrity` (`9412981279`)

Artifact digest:

`sha256:7e7b6d2e9d9508b6f41b24ece8de50f4955d770d3a8bb7fdef28914beba6f4fc`

The workflow reacquired the same deterministic eight-source Akron attachment sample, rebuilt preferred Silver with the existing progressive OCR path, ran structured parser v2, and compared the resulting money population to the frozen v1 T8/T9 population using source/Bronze identity, locator, and character-start anchors.

### Measured v1 → v2 delta

- v2 money facts: **31**
- unchanged facts: **29**
- changed facts: **2**
- unexpected changes: **0**
- missing expected repairs: **0**
- exact frozen source/Bronze continuity: **yes**
- OCR failures: **0**
- rejected publisher links: **0**

Corrected fact 1:

- frozen source: `s4`
- locator: `page:4`
- character start: `378`
- v1: `$138` → `138.00`, char end `382`
- v2: `$138MM` → `138000000.00`, char end `384`

Corrected fact 2:

- frozen source: `s5`
- locator: `page:2`
- character start: `1207`
- v1: `$ 51` → `51.00`, char end `1211`
- v2: `$ 51 ,780.00` → `51780.00`, char end `1219`

The live gate required the other 29 frozen facts to remain unchanged. It also fails closed if an unrelated fact changes or an expected repair disappears.

## Regression coverage

The full repository suite passed **142 tests** on the validated T10 head.

Focused parser tests require:

- `$ 51 ,780.00` to remain one raw token and normalize to `51780.00`;
- `$138MM` to remain one raw token and normalize to `138000000.00`;
- no residual `$ 51` or `$138` fragment for those examples under v2;
- an unknown attached suffix such as `$138XYZ` to produce no money fact rather than a truncated `$138` fact;
- explicit v1 parsing to continue reproducing the historical malformed outputs;
- structured index builds to record the parser version used.

The T10 delta test also mutates an unrelated third frozen fact and requires the measurement gate to reject the result.

## Compatibility validation

On the validated T10 head, these independent workflows also passed:

- `test`
- `r0-canton-validation`
- `r0-near-segment-validation`
- `r1-retrieval-evaluation`
- `r1-canonical-retrieval-evaluation`
- `r1-financial-role-validation`
- `r1-akron-onbase-probe`
- `r1-akron-benchmark-pool`
- `r1-akron-retrieval-evaluation`
- `r1-akron-money-context-profile`

The T9 context workflow successfully restored `proofline-structured/v1` and reproduced the frozen historical contract after current extraction had run with v2.

## Non-claims

R1.T10 does **not** establish that:

- every explicit dollar token is a financial event;
- magnitude-suffixed private sales history is relevant to municipal finance;
- the repaired `$51,780` occurrence should independently count twice when the same expenditure appears in multiple form fields;
- Akron should use Canton's financial-role policy;
- an Akron financial conflict, anomaly, recurrence, or suspicious transaction exists;
- a financial detector is ready for production.

Parser integrity is a prerequisite for those questions, not evidence for their answers.

## Next stage

The next stage should freeze a conservative Akron attachment money-role contract derived from the T9 local contexts, then evaluate that contract on a **disjoint, content-blind attachment sample** selected by source identity and excluding the original T8 eight sources.

Unknown/unclassified values and a null financial-event result must remain valid outcomes. Only after out-of-sample role evaluation should Proofline decide whether to authorize an Akron-specific financial detector, matter linking, or recurrence analysis.
