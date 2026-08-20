# R1.T11 — Akron Money-Role Out-of-Sample Evaluation

## Status

Completed as a preregistered out-of-sample evaluation of the frozen `akron-money-role-v1` contract.

This stage evaluates semantic-role transfer only. It does **not** authorize a detector, lead, anomaly, conflict, suspiciousness, recurrence, or transaction-counting layer.

## Final blind live run

- Workflow: `r1-akron-money-role-oos`
- Run: `32392428980`
- Validated head: `e1cb2f4a0c66086ec847f727a4e9fde2ca555704`
- Artifact: `r1-akron-money-role-oos` (`9415678800`)
- Artifact digest: `sha256:0c1767de7346c5721071eb14685241c1070cff052b2a6b5ceb383865b03b00d2`
- Full repository tests: **149 passed**
- Canton validation: passed
- Akron OnBase source-contract probe: passed
- Live attachment graph: **2,327** source identities
- Global rejected attachment links: **0**

## Preregistered sampling boundary

The T11 source population was frozen before semantic evaluation from the preserved R1.T8 full attachment manifest.

Ranking rule:

1. `sha256(source_uri)` ascending;
2. exact `source_uri` as deterministic tie-breaker.

The original T8 derivation sample was exactly ranks **1–8**. T11 froze ranks **9–32**, giving **24 source identities**.

The live T11 run required exact reproduction of:

- all 8 excluded T8 source-identity hashes;
- all 24 selected T11 source-identity hashes;
- no overlap between the two sets.

All 24 selected sources synced successfully and none were unavailable. Selection did not use filename content, extracted text, money values, document type, role likelihood, or any semantic feature.

## Frozen role contract

The role contract was derived from R1.T9 and frozen before T11 documents were evaluated.

Recognized roles:

- `fee_schedule_threshold`
- `filing_fee_amount`
- `estimated_project_cost`
- `city_expenditure_amount`
- `contract_amount`
- `assessment_rate`
- `private_background_amount`
- `unclassified_money`

`unclassified_money` is the mandatory default.

The contract explicitly records:

`detector_authorized: false`

No rule was changed in response to the T11 results below.

## Extraction and provenance result

The 24 source identities resolved to **23 unique Bronze artifacts** because two distinct publisher source URIs served byte-identical copies of the same conditional-use petition.

- selected attachment source identities: **24**
- unique Bronze artifacts: **23**
- duplicate Bronze artifact groups: **1**
- unique logical pages: **110**
- OCR pages attempted: **26**
- OCR extractions added: **26**
- OCR failures: **0**
- post-OCR pages below 0.70: **1**
- money facts below 0.70 quality: **0**

The one remaining low-quality page was `page:7` of one selected PDF. OCR returned a blank page with quality `0.0`; it contributed no structured money facts. T11 therefore did not manufacture evidence from that blank page or lower the money-fact quality gate to make it usable.

Every evaluated money fact retained:

- selected publisher source identity and SHA-256 identity hash;
- exact Bronze artifact identity;
- preferred Silver evidence ID and page locator;
- exact `char_start:char_end` token anchor;
- page-text SHA-256;
- local context SHA-256;
- extraction method, quality, software, and model metadata.

Structured indexing used `proofline-structured/v2`.

## Blind semantic result

The 23 unique artifacts produced **88** provenance-backed money facts.

| Role | Facts |
| --- | ---: |
| `fee_schedule_threshold` | 10 |
| `filing_fee_amount` | 6 |
| `city_expenditure_amount` | 1 |
| `unclassified_money` | 71 |
| **Total** | **88** |

So:

- classified facts: **17/88**
- unclassified facts: **71/88**
- detector authorized: **false**
- lead count: **null**

No minimum classification rate or positive financial result was required by the preregistration.

## What generalized

### Conditional-use fee schedule

Two out-of-sample conditional-use petition artifacts contained the same newer fee-schedule wording seen in T9. The frozen contract correctly recognized:

- five project-cost threshold values per artifact;
- three filing-fee values per artifact.

One of those artifacts was published under two separate attachment source URIs at different agenda items. Because Proofline indexes the Bronze artifact rather than duplicating byte-identical evidence, those duplicate source identities did not manufacture a second set of money facts. Their source provenance is retained on the shared facts.

### City total expenditure

One Uniform Report context explicitly printed:

`Total expenditure (if applicable): $650,000`

The frozen `city_total_expenditure_field` rule classified this single fact as `city_expenditure_amount`.

The same form also contained two `$325,000.00` component values. Those did **not** satisfy the frozen local-field rule and remained unclassified. T11 did not broaden the rule after seeing them.

## What did not generalize

Four T9-derived roles had zero out-of-sample matches:

- `estimated_project_cost`
- `contract_amount`
- `assessment_rate`
- `private_background_amount`

Zero matches are a valid result; they do not demonstrate that those roles are wrong, only that this disjoint 24-source sample did not reproduce their frozen rule conditions.

More importantly, **71/88 facts remained unclassified**. A post-result human context audit shows that many are not random parser noise; they expose important semantic families absent from the v1 derivation set.

This audit is descriptive only. It does not modify the frozen T11 result or retrospectively label the machine output.

### Older Planning Commission filing-fee schedule — 19 unclassified facts

One older petition contains a `Planning Commission Filing Fees Chart` with a different historical schedule:

- project-cost boundaries from `$0` through `$200,001 - more`;
- fee values from `$100` through `$1,000`;
- a `$250` City-owned-land sale/lease fee.

The same packet also contains a stated `$171` purchase price and `$0.05` per-square-foot amount.

The v1 contract intentionally used the exact numeric schedule supported by T9 and therefore did not recognize this historical fee table. This is strong evidence that numeric-specific fee rules underfit time-varying municipal forms.

### External comparative fire-budget document — 17 unclassified facts

A document discussing metro fire departments nationally contains values such as `$36M`, `$89M`, `$17.6M`, `$400M`, apparatus replacement ranges, and other external-city budget examples.

These are neither Akron expenditures nor automatically private-biographical amounts. Their presence supports keeping external/comparative context separate from municipal financial-event semantics.

### Executive-summary budget questions and answers — 12 unclassified facts

A City budget Q&A packet contains program, budget, expenditure, debt-service, and other amounts. The T9 derivation set did not establish a sufficiently narrow role contract for these contexts, so v1 left them unclassified.

### Municipal fact-sheet financial tables — multiple unclassified populations

The out-of-sample set includes several official fact sheets with explicit financial-data tables, including:

- eight repeated `$378,000` occurrences in a sanitation lease packet;
- a 2026 Capital Investment Program funding table totaling `$341,909,940`;
- a `$15,025` grant cash match and `$60,100.00` project amount;
- two `$250,000.00` CDBG values in a neighborhood-revitalization authorization packet;
- transportation/capital funding values including `$2,177,086` and `$12,096,742`;
- two `$325,000.00` expenditure/cost components beside the classified `$650,000` total expenditure.

These contexts are exactly why T11 was required before any detector. A role vocabulary derived from eight documents does not yet cover the diversity of Akron's own financial forms.

## Interpretation

T11 supports a **partial-generalization / underfit** conclusion.

The v1 contract appears conservative on the facts it does classify, but its out-of-sample coverage is narrow. The test does not justify converting role matches into financial leads.

The most important result is the negative one:

> A small, high-confidence role taxonomy derived from T9 is not broad enough to represent Akron attachment money contexts reliably.

That is preferable to silently forcing 71 heterogeneous facts into the nearest known role.

## Decision

**Do not authorize an Akron financial detector from v1.**

The next defensible stage is a new representation-development cycle, not detector logic:

1. treat T11 as development evidence for a possible v2 role taxonomy;
2. separate document-local municipal financial roles from external/comparative/background money;
3. replace numeric-specific schedule recognition with wording/structure evidence where the T11 contexts support doing so;
4. retain `unclassified_money` as a first-class output;
5. preserve form-level duplication rather than treating repeated occurrences as independent events;
6. freeze any v2 contract before evaluating it;
7. evaluate v2 on a **new disjoint source-identity holdout** that excludes both T8 ranks 1–8 and T11 ranks 9–32.

A reasonable next holdout begins at rank 33, but its exact size and identities must be frozen before any content from that holdout is inspected.

Only a successful new out-of-sample role evaluation could justify preregistering a later detector experiment.

## Non-claims

T11 does not claim:

- that 88 money facts are 88 financial events;
- that the 17 classified facts are independent transactions;
- that the 71 unclassified facts are irrelevant;
- that a role match implies anomaly, conflict, fraud, waste, abuse, suspiciousness, or wrongdoing;
- that duplicate publisher source identities imply duplicate underlying events;
- that the 24-source sample represents all 2,327 attachments;
- that zero matches for four roles disproves those roles;
- that post-result human characterization is a new machine ground truth;
- that a financial detector is authorized.
