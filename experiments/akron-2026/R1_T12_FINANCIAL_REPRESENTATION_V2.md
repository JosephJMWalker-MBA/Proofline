# R1.T12 — Akron Financial Representation v2

## Status

Completed as a **representation-development stage only**.

R1.T12 does not evaluate a new holdout, authorize a detector, assign transaction/event identity, assess occurrence independence, or generate investigative leads. It uses only previously observed R1.T9/R1.T11 development evidence to replace the underfit single-role model with a richer descriptive representation.

## Development baseline

R1.T12 begins from merged R1.T11 main:

`cb14e7726aca7d23ba18c590187ba722fc15ad41`

R1.T11 was a partial-generalization / underfit result:

- 24 disjoint attachment source identities;
- 88 money facts;
- 17 classified by the frozen v1 role contract;
- 71 retained as `unclassified_money`;
- detector authorization remained false;
- lead count remained null.

The 71 unknowns exposed coherent context families absent from the original T9 derivation set. T12 treats those unknowns as development evidence rather than retroactively changing the completed T11 result.

## Future holdout was frozen first

Before the v2 representation rules were written, T12 froze the next source-identity holdout at commit:

`cc0a4496c5abaf17e5839e193fb9b921efe8e51c`

Frozen file:

`experiments/akron-2026/r1_t13_disjoint_attachment_sources.json`

The selection uses the same preserved 2,327-source Akron attachment manifest:

- manifest SHA-256: `7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a`;
- source identity ranking: `sha256(UTF-8 source_uri)`, then source URI;
- ranks **1–32**: excluded as development evidence;
- ranks **33–64**: frozen as **32 future holdout identities**.

The holdout file stores identity hashes and provenance metadata only. It contains no `source_uri`, `source_name`, or `document_text` fields and records:

`content_inspection_status: not_inspected_at_freeze`

**No rank-33–64 document content was downloaded, inspected, or used to derive T12 rules.** R1.T13 is the first stage allowed to resolve and inspect those frozen identities.

## Representation v2

Contract:

`experiments/akron-2026/akron-financial-representation-v2.json`

Evaluator:

`experiments/akron-2026/financial_representation_v2.py`

Schema:

`proofline-akron-financial-representation/v2`

Parser dependency:

`proofline-structured/v2`

Instead of forcing every money fact into one semantic role, v2 emits independent descriptive facets.

### Scope

- `akron_municipal_record_context`
- `external_reference`
- `private_background`
- `unknown`

Scope describes the evidence context. It does **not** claim ownership of the money.

### Context type

- `fee_schedule`
- `municipal_financial_form`
- `municipal_budget_narrative`
- `project_estimate`
- `grant_project`
- `contract`
- `assessment`
- `property_transaction`
- `external_comparison`
- `private_background`
- `unknown`

### Amount type

- `fee_schedule_threshold`
- `filing_fee_amount`
- `city_expenditure_amount`
- `municipal_form_amount`
- `total_project_amount`
- `budget_narrative_amount`
- `estimated_project_cost`
- `grant_cash_match_amount`
- `grant_context_amount`
- `contract_amount`
- `assessment_rate`
- `purchase_price`
- `unit_rate`
- `external_comparative_amount`
- `private_background_amount`
- `unknown`

The important new state is `municipal_form_amount`. When flattened text or OCR proves that a value belongs to a municipal financial form but does not preserve enough table structure to distinguish fields such as appropriation, budgeted cost, or current request, Proofline keeps the more conservative representation instead of manufacturing a precise field assignment.

## Structural fee-schedule generalization

R1.T11 exposed an older Planning Commission fee schedule whose amounts differed from the T9 schedule.

T12 therefore removes amount-specific whitelisting. The v2 contract contains no `numeric_in` rule. Fee-schedule amounts are interpreted structurally relative to the `Applicable Fee` marker:

- currency tokens before the marker can be schedule thresholds;
- currency tokens after the marker can be filing-fee amounts.

Derivation tests use unseen fixture amounts to ensure the behavior depends on structure rather than memorized dollar values.

The development evidence also contained an OCR heading split:

`Estimated TOT AL Project Cost`

T12 explicitly tolerates that observed split. This adjustment was made from ranks 1–32 development evidence only; it is not a T13 holdout-driven change and does not lower the extraction-quality threshold.

## Hard semantic boundary

The v2 contract requires all of the following to remain false:

- `detector_authorized`
- `event_identity_assigned`
- `independence_assessed`

The evaluator preserves exact preferred-Silver token anchors and emits context/page/source-name hashes, but it does not produce anomaly, conflict, suspiciousness, transaction, event, or lead judgments.

Repeated amount occurrences remain evidence occurrences until a separate future stage establishes event identity and independence.

## Validation

Validated code head:

`b6446b330482de629686771f140997daab6f5631`

T12 workflow:

- run: `32400112065`
- conclusion: **success**

General repository test workflow:

- run: `32400112060`
- result: **170 passed in 9.07s**

Compatibility checks:

- Akron OnBase source-contract probe `32400112083`: **success**
- Canton validation `32400112081`: **success**

The T12 workflow is intentionally no-network. It validates the representation contract and frozen holdout boundary without resolving or downloading any T13 source.

## First validation failure

An earlier T12 run failed one new test because the test searched serialized JSON for the substring `source_uri"`. That string appeared in the harmless ranking description `then source_uri`, even though the holdout contained no `source_uri` field or URI values.

The correction changed only the validation method: it now recursively inspects exact JSON keys and rejects `source_uri`, `source_name`, or `document_text` fields. The frozen T13 holdout file itself was not changed or resampled.

## What T12 establishes

T12 establishes that:

1. R1.T11's underfit result can be represented without rewriting its historical output.
2. Financial interpretation is better modeled as separable descriptive facets than one forced money role.
3. Known table-layout ambiguity can be preserved explicitly as `municipal_form_amount`.
4. Historical fee schedules can be represented structurally without amount whitelists.
5. A future 32-source holdout was frozen before v2 rule development and remains uninspected.
6. The representation contract is prevented from silently crossing into detector, event-identity, or occurrence-independence semantics.

## What T12 does not establish

R1.T12 does **not** establish:

- that v2 generalizes beyond ranks 1–32;
- that v2 has better precision or recall out of sample;
- that every municipal money fact can be assigned a non-unknown facet;
- that a represented amount is a transaction or independent financial event;
- that an amount is anomalous, conflicting, suspicious, improper, or evidence of wrongdoing;
- that an Akron financial detector is justified.

## Decision

Freeze v2 as written and evaluate it unchanged in R1.T13 on the already-frozen ranks **33–64** holdout.

Unknown, partially represented, and null outcomes must remain valid. R1.T13 may characterize the blind result, but it must not tune v2 rules after seeing holdout content and then report that tuned result as out-of-sample validation.
