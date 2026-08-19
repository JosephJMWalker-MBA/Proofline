# R1 Canonical Retrieval Benchmark v2 — Score

This record documents the first score of the 42-case canonical-evidence benchmark frozen before
retrieval evaluation.

## Provenance

- Frozen suite: `r1-canonical-v2-unscored.json`
- Frozen suite SHA-256: `aee4d01b3b7fa505d008296e226bbaff43af6022c025ad9764f14b412e9cfbbc`
- Freeze receipt: `R1_CANONICAL_V2_FREEZE.md`
- Scoring workflow run: `32288529528`
- Scoring artifact ID: `9378612471`
- Scoring artifact digest: `sha256:fe60fe385d3d766a9896657ea07f1daa122d5656d16e2d3e5be53b162b291586`
- Evaluation depth: `k=10`

Exact score files are preserved under `r1-canonical-v2-score/`:

- `evaluation.json` SHA-256: `09a2a40fd86a7b66be8f87487fa45ff015b24826cde73ac40b964852c79ebe17`
- `scorable-report.json` SHA-256: `5a0b8a7e773fdc75fbb74eb8fb0a4b34a8d632070419f9bb5aa199a69fd8e97d`
- `summary.json` SHA-256: `26dfaba3ae44a527829666da4c69fe86e70efda90fd0711965ec8ea03d2f55eb`
- `sync.json` SHA-256: `02d66d49c5c28e4b60889dd263b3138547452515f8b0761c384e3abdb12a9b72`

The scoring workflow verified the frozen benchmark SHA before and after evaluation.

## Result

### Raw evaluator

- cases: **42**
- expectation accuracy: **1.0**
- positive hit rate at 10: **1.0**
- target recall at 10: **1.0**
- negative accuracy: **1.0**
- provenance validity: **1.0**
- unresolved target count: **0**
- failure classes: **none**

### Scorable report

- scorable cases: **42/42**
- unscorable cases: **0**
- scorable expectation accuracy: **1.0**
- scorable positive cases: **37**
- scorable positive hit rate: **37/37 = 1.0**
- scorable target recall: **1.0**
- negative controls: **5/5 = 1.0**
- mean scorable case provenance validity: **1.0**
- scorable retrieval failures: **0**

Per-mode scorable expectation accuracy is 1.0 for:

- lexical
- money
- date
- publisher-native identifier
- identifier negative control

## What this establishes

The first R1 benchmark produced six `unresolved_target` cases because frozen targets included
volatile discovery/support pages. The canonical-evidence policy removed that failure class:

- first frozen suite: **6 unscorable cases / 10 unresolved target records**
- canonical frozen suite: **0 unscorable cases / 0 unresolved targets**

This supports the hypothesis that the first failures were benchmark-target volatility rather than a
lexical or structured retrieval failure.

## Decision on semantic/vector retrieval

**Still not justified.**

Across the broader 42-case canonical benchmark, Proofline produced no deterministic retrieval miss,
no partial target recall, no unexpected result in the negative controls, and no provenance failure.
Semantic retrieval should remain deferred until a future frozen benchmark exposes a repeatable
failure class that deterministic query/index improvements cannot address.

This result does not claim retrieval is universally complete. It records that the current R1
canonical test population did not justify additional probabilistic retrieval complexity.

## Integrity rule

The frozen suite and exact score files are historical measurement records. Future benchmark or
evaluator improvements must create new versioned artifacts rather than rewriting this result.
