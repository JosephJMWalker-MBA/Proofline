# R1.T15 — Money Parser v3 Integrity

## Purpose

R1.T15 repairs the generic partial-token money-parser defect exposed by the completed T13b blind evaluation and preserved in R1.T14.

The observed Silver text contained:

```text
$20,001___- $100,000
```

`proofline-structured/v2` rejected the complete first thousands-form candidate because of the trailing OCR underscore continuation, then regex backtracking accepted the shorter prefix `$20`. That produced a deterministic but numerically unsupported money fact.

R1.T15 changes **numeric integrity only**. It does not change the Akron financial-representation v2 semantic contract, assign transaction/event identity, assess independence, authorize a detector, or emit leads.

## Parser contract

R1.T15 introduces:

- historical `proofline-structured/v1` — unchanged and explicitly selectable;
- historical `proofline-structured/v2` — unchanged and explicitly selectable;
- current/default `proofline-structured/v3`.

The v3 money regex makes the numeric core atomic. Once a candidate such as `$20,001` has been selected, a malformed trailing continuation cannot force the engine to retreat to `$20`.

The repair is deliberately fail-closed. v3 does **not** infer that `$20,001___` means `$20,001`; it emits no fact for that malformed token. A later independently valid token such as `$100,000` remains extractable.

## Historical reproduction

Explicit v2 remains capable of reproducing the T13b defect:

```text
$20,001___- $100,000
```

v2:

- `$20` → `20.00`
- `$100,000` → `100000.00`

This behavior remains available only so prior experiment receipts can be regenerated exactly. It is not the current parser behavior.

## T13b population delta

A compact anchor fixture was derived from the already-opened T13b evidence artifact:

- T13b workflow run: `32440471169`
- T13b workflow artifact: `9432387690`
- T13b artifact digest: `sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338`
- fixture schema: `proofline-akron-t15-t13b-money-anchor-fixture/v1`
- fixture money-fact count: **194**
- committed fixture SHA-256: `630d39ba9b8cc90476c6dd053c1af5459b85e9fd7173f43f4560952ae58eacb0`

Each fixture record preserves a small local text window and the exact v2 character anchor. Before any v3 comparison, explicit v2 is required to reproduce all 194 historical anchors exactly.

Measured v2 → v3 delta:

- total historical anchors: **194**
- unchanged: **193**
- removed: **1**
- changed/replaced: **0**

The single removed anchor is the unsupported `$20` fragment from the malformed `$20,001___` token.

This is a regression measurement on **already-opened T13b evidence**. It is not a new holdout and does not create a new generalization claim.

## Historical workflow pinning

Changing the current/default parser must not silently rewrite older experiments. Historical stages that specifically require v1 or v2 are therefore pinned to their declared parser contracts rather than inheriting v3 implicitly.

In particular:

- T9 profiles v2 before its explicit v1 historical rebuild;
- T10 remains an exact v1 → v2 parser-delta experiment;
- T11 evaluates its frozen role contract with the contract-declared v2 parser;
- T13b evaluates the frozen financial-representation v2 contract with its contract-declared v2 parser.

T8 and ordinary current extraction remain free to use the current parser because they are measurement/current-pipeline stages rather than frozen v2 semantic evaluations.

## Acceptance boundary

R1.T15 is accepted only if:

1. the full repository test suite passes;
2. the 194-anchor fixture SHA-256 is unchanged;
3. explicit v2 reproduces all 194 historical anchors exactly;
4. v3 produces exactly 193 unchanged anchors, one removal, and zero changed replacements;
5. the removal is the malformed `$20` fragment associated with `$20,001___`;
6. default extraction uses v3 and fails closed on that malformed candidate;
7. explicit v1/v2 historical paths remain available;
8. frozen T9/T10/T11/T13b workflows retain their original parser contracts;
9. no semantic/detector/event/lead authority changes.

## Non-claims

- This repair does not prove the money parser is complete for arbitrary OCR corruption.
- The malformed token is not reconstructed into a guessed value.
- The T13b anchor fixture is not independent evaluation data; it was derived after T13b was opened.
- The parser repair does not resolve the table-structure failures documented in R1.T14.
- The parser repair does not improve or validate the precision of the frozen financial-representation v2 contract.
- Detector authorization remains **false** and lead count remains **null**.

## Next stage

After R1.T15 is merged, the next engineering problem is **structure-aware table/field extraction**. R1.T14 showed that flat text destroys critical row/column relationships in fee schedules and assessment forms. More semantic regex rules should not be added until the evidence layer preserves that structure.
