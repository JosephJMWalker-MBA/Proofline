# Matter-key contract

Proofline matter keys are deterministic **comparison guards**. They answer a narrow question:

> Does the active source/profile policy provide enough evidence-backed identity components to permit these records to be compared as the same matter?

A matter key is not a source identifier, entity-resolution claim, legal conclusion, or evidence of wrongdoing.

## Status model

Every in-scope segment receives one of three states:

- `resolved` — every component required by one resolver is present and unambiguous; a deterministic matter key may be emitted;
- `ambiguous` — competing identity components or multiple transaction matches exist; no matter key is emitted;
- `insufficient_identity` — the policy lacks enough explicit information to resolve the matter; no matter key is emitted.

Conflicting-value detectors **must consume only `resolved` keys**. They must never interpret `ambiguous` or `insufficient_identity` as a partial match.

## Evidence pointers

Every component that contributes to a resolved key retains:

- component role;
- raw source text;
- normalized comparison value;
- evidence ID;
- segment ID;
- absolute character start/end offsets.

Normalization does not replace the source form. It exists only to make deterministic equality possible under a declared policy.

## Source/profile policy

The core resolver is source-agnostic. A `proofline-matter-key-policy/v1` file declares:

- which segmentation rule is in scope;
- how explicit project IDs are recognized;
- which transaction resolver patterns are allowed;
- the canonical transaction role assigned by each resolver;
- the exact components required to emit a key.

The current Canton R1 policy is:

`experiments/canton-2026/matter-key-policy.json`

It is deliberately narrow. The first resolved class is **Board of Control change orders with exactly one GP project ID**. The key requires:

1. `project_id`;
2. `transaction_role = change_order`;
3. `change_order_number`;
4. `counterparty`.

This contract directly prevents several false joins discovered in the live corpus:

- the same ordinance anchor can refer to unrelated matters;
- the same GP project can have construction, engineering, and administrative contracts;
- the same project and change-order number can belong to different counterparties;
- one correctly bounded agenda item can legitimately reference multiple project IDs.

Multi-project items remain `ambiguous`. Change orders without an explicit GP identifier remain `insufficient_identity` under this first policy. That loss of recall is intentional.

## Normalization

For this contract:

- project/change-order numbers normalize to canonical decimal strings;
- transaction roles are policy-assigned canonical labels;
- counterparties use Unicode normalization, case folding, period removal, `&` → `and`, and alphanumeric whitespace collapsing.

No fuzzy company matching, alias inference, FKA/DBA equivalence, project-name similarity, or LLM resolution is performed. If wording differences prevent equality, Proofline accepts the false negative rather than guessing.

## Stable identity

The policy has a deterministic SHA-256. A resolved matter key is derived from:

- policy hash;
- resolver name;
- ordered required component roles and normalized values.

The candidate identity is separately derived from policy hash + stable segment ID. Rebuilding the same evidence under the same policy therefore preserves key identity even though rebuild metadata may change.

## Current limitation

A resolved key means only that the active policy considers the records safe enough to enter a same-matter comparison population. A downstream detector must still prove that the **field being compared has the same semantic role**. That is the purpose of R1 Issue #40; matter identity alone does not make two dollar values comparable.
