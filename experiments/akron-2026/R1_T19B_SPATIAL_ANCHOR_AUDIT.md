# R1.T19b post-hoc spatial-anchor audit

## Status

This is a **post-hoc failure-localization audit** of the already-frozen T19b blind machine artifact. It does not rewrite the blind result and does not convert ranks 65–96 into a new validation population.

Blind evidence:

- workflow run: `32497051480`
- evaluated head: `c23fdb8446f64354d0f654670ffba97ef4d8fb78`
- artifact: `9452336639`
- artifact digest: `sha256:4033ea05fbd122504e0dadf005f200ae32e30f646d086cfdfb2399b0bbb36320`
- evaluation SHA-256: `542b35d019573ce518d22cd3001663f2a4a89d4fcc025c40e97118bf21116e1b`
- topology signature: `12ca65788281d621299e35f7f526dad5a43356ef3e4adb36df857a09ccc61645`

## Blind machine result

The frozen ranks 65–96 evaluation measured 32 publisher source identities / 30 unique PDF artifacts, 171 pages, 49 OCR pages attempted / 49 added / 0 failed, 29 money-bearing pages, 375 page-level `proofline-structured/v3` money facts, 90 spatial money regions, 18 grouped pages, and 38 nearest-component groups.

No contextual semantic audit was performed before that artifact was finalized.

## Exact coverage failure

The apparent 375 → 90 loss is one deterministic representation-boundary failure class.

Comparing the preserved `page_parser_money_facts` multiset with the preserved spatial-line observations page by page leaves exactly **285 unmatched facts**. Every one has the raw span `"$\n<number>"`: the currency symbol and numeric core cross extractor line identity.

Distribution:

- **273 / 285** unmatched facts occur across all 11 money-bearing pages of one native-text artifact (`artifact:ad3b0b1f…c503c`); those pages contain zero spatial money regions.
- The remaining **12 / 285** occur on page 2 of one OCR artifact (`artifact:93073e47…1c23`); that page has 13 page-parser money facts and one spatial-line money observation.
- No preferred extraction method was unsupported.
- No money-bearing page remained below the quality floor after OCR.

This localizes the failure away from OCR quality and away from nearest-component grouping.

## Mechanism

T19b's page-level path calls `extract_structured_facts()` on the **full preferred page text**. Its `_spatial_money_regions()` path instead iterates `page.lines()`, constructs one line string at a time, and calls the same parser independently on each line.

`proofline-structured/v3` accepts whitespace between the currency symbol and numeric core. Therefore `"$\n1,699,297"` is a valid page-level money fact. But no isolated spatial line contains the complete fact when `$` and `1,699,297` have different extractor line identities.

The spatial mapper loses the fact before `nearest_neighbor_components()` is called.

## Decision

**Do not tune `proofline-local-grouping/nearest-components-v1` in response to this gap.**

The next representation boundary is deterministic **page-fact → spatial-word anchoring**: consume the already-emitted page-parser fact span; bind that exact span to spatial words from the same `evidence_id` / `spatial_id`; permit whitespace/newline separation already accepted by the page parser; fail closed when a span cannot be mapped uniquely and deterministically; and emit geometry only, without table, field, financial-role, event, anomaly, or lead semantics.

Ranks 65–96 are now development/audit evidence. A repair derived here cannot be validated on T19b.

## Next untouched holdout

Before repair development, ranks **97–128** were mechanically frozen from the same preserved 2,327-source manifest using identity hashes only.

- ranks 1–96 exclusion signature: `e6288eeda9d527ffcc9189b01cf0c101e5f42d122070fc563ebe798ce1189b61`
- ranks 97–128 selected signature: `2977671e9680305dfde595d13c77ca31197613eae0c1813f6d7a0b2218938bf3`
- ranks 1–128 combined signature: `8620cf0dab2126035dfccebb82fa6e83f4d44d68c44ae90993455ec36faabaf1`

The freeze contains no selected URI values, source names, document text/bytes, money facts, layout features, or semantic labels.

Detector authorization remains false. Lead count remains null.
