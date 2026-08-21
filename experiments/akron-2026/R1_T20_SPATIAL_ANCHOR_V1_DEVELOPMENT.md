# R1.T20 spatial-anchor v1 development result

## Status

This receipt preserves the first exact-byte T19b development replay of `proofline-spatial-text-anchor/source-span-v1` **before** refinement. It is not out-of-sample validation.

Run `32501978519` reproduced the original T19b source→artifact byte mapping exactly and replayed the new anchor over the same 375 page-level `proofline-structured/v3` money facts.

- artifact: `9454036743`
- artifact digest: `sha256:5eb741beb393fb660cd26de4e90c3f54b9bb4ab67bfbbfbdb83be9fab544c3f5`
- evaluation SHA-256: `01b115c39b1abd8b5cec28738da9361f8e51ae7f78e6091e31e5aa316cd72a98`
- exact T19b source→artifact map signature: `8e4bedc043544c701d2c2e6fee5dcb1fcda92d2322fbd98a5bba7b01f0a5c14d`

## Result

V1 anchored **369 / 375** page-parser money facts.

Most importantly, it recovered **285 / 285** facts in the exact cross-line failure class that motivated T20. Every previously lost `$\n<number>` span mapped into spatial word geometry.

However, v1 did not preserve all prior same-line coverage:

- T19b line-local spatial observations: **90**
- v1 same-line anchors: **84**
- regression: **6**

All 29 money-bearing pages still produced at least one anchored region; grouping emitted 369 regions and 175 components.

## Six v1 failures

All six failures have the same v1 exception:

`spatial anchor span ends inside a spatial word`

Post-hoc comparison with the already-preserved T19b line observations shows that the parser span ends immediately before prose punctuation retained inside the same PyMuPDF word token:

- `$57,988.38,`
- `$54,725.60,`
- `$73,185.45,`
- `$132,113.53.`
- `$318,012.96.`
- OCR `$1,000.`

The outside-span content is therefore **three commas and three periods**, not additional letters or digits.

## Decision

Do **not** freeze source-span-v1 for the untouched holdout.

The next method version should preserve v1's exact source-span lineage while allowing deterministic word-boundary expansion **only across adjacent Unicode punctuation**. Expansion across letters, digits, or other non-punctuation content remains a hard failure. The emitted anchor should record whether and how much boundary expansion occurred.

This refinement is generic geometry alignment, not a money- or dollar-specific rule.

Ranks 97–128 remain unopened and cannot be used while refining this behavior.

Detector authorization remains false. Lead count remains null.
