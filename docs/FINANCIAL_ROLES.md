# Financial field-role contract

Proofline does not treat all dollar values as one comparable population.

Matter identity answers **which records may describe the same underlying matter**. Financial-role assignment answers a separate question:

> What does this particular monetary value mean in the source text, and is it semantically comparable to another value?

Both gates must pass before numeric comparison is allowed.

## Status model

Every explicit money fact inside a `resolved` matter-key segment receives one of three states:

- `assigned` — exactly one declared role rule matches the exact money span;
- `ambiguous` — competing role rules match the same money span;
- `unknown` — no declared role rule matches the money span.

Only `assigned` values may enter a comparison population. Unknown and ambiguous values are preserved and reported, but never pooled.

## Comparison population

The first R1 comparison population is deliberately narrow:

**same resolved matter key + same assigned financial field role**

A population never crosses matter keys or field roles. Cross-matter outlier analysis is explicitly out of scope for this policy.

A repeated population means only that the same matter/role combination appeared more than once. It is descriptive; it does not imply that differing values are erroneous or suspicious.

## Evidence binding

Role assignment is accepted only when a policy regex's named `amount` group matches the exact character span of a structured money fact.

Each assignment retains:

- immutable matter key and matter-candidate identity;
- evidence ID and segment ID;
- raw and normalized monetary value;
- currency unit;
- exact evidence-relative character offsets;
- matched role rule(s);
- source mappings.

Structured-index fact IDs are intentionally not part of assignment identity because structured indexes are disposable rebuilds.

## Canton R1 policy

`experiments/canton-2026/financial-role-policy.json`

It currently recognizes only two roles inside the resolved Board change-order matter class:

### `change_amount`

Source language such as:

- `in the amount of $...`
- `for a cost reduction in the amount of $...`
- `net reduction in the amount of $...`

### `resulting_contract_total`

Source language such as:

- `resulting in a new contract amount of $...`
- `resulting in a new project amount of $...`
- `resulting in a new contract price of $...`
- `final contract price of $...`

These roles are semantic labels for comparison, not accounting/legal classifications beyond the wording preserved in the record.

## Deliberate unknowns

The policy intentionally leaves supporting figures unclassified when their role is not needed or sufficiently justified. Examples encountered during R1 profiling include:

- total cost of extra work;
- Federal Funds component;
- Sewer Funds component;
- purchase-order offset;
- a narrative restatement of a previously stated change amount.

Leaving a value `unknown` is preferable to manufacturing a comparison population.

## Stable identity

The financial-role policy is content-addressed by SHA-256. Assignment IDs derive from stable evidence coordinates, normalized value, matter key, policy hash, and resolved role state—not from disposable structured-index build/fact IDs.

Comparison-population IDs derive from policy hash + resolved matter key + field role. Identical evidence rebuilt under the same policies therefore preserves assignment/population identity while structured/segment build UUIDs may change.

## What this does not authorize

This layer does **not**:

- calculate suspiciousness;
- rank projects by amount;
- compare change amounts across unrelated matters;
- infer that a changed value is wrong;
- infer causation, intent, or wrongdoing.

A future conflicting-value detector may compare values only after both matter identity and financial role are resolved, and must retain the comparison population and its limitations in the resulting evidence packet.
