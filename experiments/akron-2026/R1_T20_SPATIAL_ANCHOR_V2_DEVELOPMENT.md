# R1.T20 Source-Span-v2 Development Freeze

## Boundary

This freezes the T20 `proofline-spatial-text-anchor/source-span-v2` representation and its exact-byte T19b development result **before** ranks 97–128 are resolved or inspected.

Ranks 65–96 are already-opened development evidence. They cannot validate this repair.

## Why v2 exists

Source-span-v1 recovered all 285 page-parser money spans that crossed extractor line identity, but it failed on six previously line-local facts because PyMuPDF retained adjacent prose punctuation in the same spatial word token. Those six failures were three trailing commas and three trailing periods.

V2 permits a source span to borrow the containing spatial word's geometry only across adjacent Unicode punctuation. The exact leading/trailing punctuation is recorded. Expansion across letters, digits, currency symbols, mathematical symbols, or other substantive content remains fail-closed.

The anchor is still parser-agnostic and fact-type agnostic. It assigns no table, row, column, field, financial role, transaction, event, anomaly, conflict, wrongdoing, detector, or lead semantics.

## Exact-byte development replay

Workflow run `32504366821` executed on commit `46a02176f06cb7b8ba66771ebdc89affcb35ae82` and first reproduced the original T19b source→artifact-byte map signature:

`8e4bedc043544c701d2c2e6fee5dcb1fcda92d2322fbd98a5bba7b01f0a5c14d`

Artifact:

- ID: `9455028858`
- digest: `sha256:d537514fd76eca9e9f8ece24dd4d9787159fe502a769f0b8cf97d3f86ec94000`
- full suite: **224 passed**

Measured result:

- 171 pages
- 29 money-bearing pages
- 375 existing `proofline-structured/v3` money facts
- **375/375 anchored**
- **0 anchor failures**
- 285 cross-line anchors
- 90 same-line anchors
- six punctuation-boundary expansions: 3 commas, 3 periods
- 375 spatial money regions
- 29/29 money-bearing pages grouped
- frozen grouping v1: 176 components
- component sizes: 6×1, 150×2, 13×3, 5×4, 2×5
- 369 nearest-neighbor directed edges; 340 mutual-nearest directed edges

This is positive development closure, not an out-of-sample performance estimate.

## Frozen representation inputs

The machine-readable summary records the exact Git blobs for source-span-v2, spatial text extraction, structured parser v3, local grouping v1, OCR/progressive extraction, evaluator, validator, workflow, tests, and the identity-only ranks 97–128 holdout.

The future holdout remains:

- ranks 97–128
- 32 identities
- selected signature `2977671e9680305dfde595d13c77ca31197613eae0c1813f6d7a0b2218938bf3`
- status: **unopened at this freeze**

## Next stage

The next stage may resolve ranks 97–128 and apply the frozen representation without tuning. Outcome-neutral validation must accept zero-money, zero-anchor, partial-anchor, unsupported, singleton, large-component, or other null/negative outcomes.

A successful validation would support transfer of the anchoring representation only. It would not authorize financial semantics, a detector, events, anomalies, wrongdoing claims, or leads.
