# Proofline R0/R1 Publication Artifact Manifest

> **Status:** Publication-preparation manifest. This file identifies the minimum research-owned artifacts that should support the first Proofline R0/R1 report. Historical SHA-256 values below are copied from the frozen experiment receipts and must be re-verified against the exact deposit bytes before publication.

## Governing rule

The publication package should be sufficient to reconstruct the reported benchmark identities and scores without silently republishing every third-party municipal source byte.

The minimum package therefore favors:

- frozen benchmark definitions;
- freeze receipts;
- exact score receipts/results;
- evaluator configuration/code identity;
- research-authored manifests and summaries; and
- source URLs, source roles, locators, and hashes needed to verify provenance.

Municipal source bytes should be deposited only after a separate redistribution/rights review.

---

## A. Canton canonical benchmark v2

### Freeze receipt

Path:

`experiments/canton-2026/retrieval/R1_CANONICAL_V2_FREEZE.md`

Purpose: establishes that canonical benchmark selection occurred before retrieval scoring.

### Frozen benchmark

Path:

`experiments/canton-2026/retrieval/r1-canonical-v2-unscored.json`

Historical SHA-256:

`aee4d01b3b7fa505d008296e226bbaff43af6022c025ad9764f14b412e9cfbbc`

Composition:

- 42 cases
- 37 positive cases
- 5 deterministic negative controls
- 5 cross-record lexical/entity cases
- 8 unique lexical/entity cases
- 8 exact-money cases
- 8 exact-date cases
- 8 publisher-native identifier cases

Every positive expected target is bound to:

- a source URI classified `canonical` by the frozen source policy;
- a page-level locator; and
- an exact artifact SHA-256.

### Preserved broad raw pool

Path:

`experiments/canton-2026/retrieval/r1-canonical-v2-raw-pool.json`

Historical SHA-256:

`60807ca48ce44f5fd400b5509fedaec5a34e99b34b8619bfe3f8b3674207c0b3`

Purpose: preserves the broader pre-curation candidate population used before the final canonical suite.

### Score receipt

Path:

`experiments/canton-2026/retrieval/R1_CANONICAL_V2_SCORE.md`

Evaluation depth:

`k=10`

Scoring workflow run:

`32288529528`

Scoring artifact ID:

`9378612471`

Scoring artifact digest:

`sha256:fe60fe385d3d766a9896657ea07f1daa122d5656d16e2d3e5be53b162b291586`

Exact score-file identities recorded by the receipt:

| File | Historical SHA-256 |
| --- | --- |
| `evaluation.json` | `09a2a40fd86a7b66be8f87487fa45ff015b24826cde73ac40b964852c79ebe17` |
| `scorable-report.json` | `5a0b8a7e773fdc75fbb74eb8fb0a4b34a8d632070419f9bb5aa199a69fd8e97d` |
| `summary.json` | `26dfaba3ae44a527829666da4c69fe86e70efda90fd0711965ec8ea03d2f55eb` |
| `sync.json` | `02d66d49c5c28e4b60889dd263b3138547452515f8b0761c384e3abdb12a9b72` |

Reported bounded result:

- 42/42 scorable
- expectation accuracy 1.0
- positive hit rate @10 1.0
- target recall @10 1.0
- negative accuracy 1.0
- provenance validity 1.0
- unresolved targets 0
- failure classes none

---

## B. Akron transfer benchmark v1

### Freeze receipt

Path:

`experiments/akron-2026/retrieval/R1_TRANSFER_V1_FREEZE.md`

Purpose: establishes retrieval-blind selection and curation before the lexical retrieval index was consulted.

### Frozen benchmark

Path:

`experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz`

Historical deterministic gzip SHA-256:

`2beb620c3421389575175349e28f16dd4ef75364fcf675efe7933d298c49da78`

Historical decompressed JSON SHA-256:

`fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681`

Composition:

- 37 cases
- 32 positive cases
- 5 deterministic negative controls
- 54 explicit positive evidence targets
- 8 cross-record lexical/entity cases
- 8 unique lexical/entity cases
- 8 exact-date cases
- 8 publisher-native identifier cases
- no positive money case because the frozen canonical Akron corpus contained no explicit currency evidence

Every positive target is bound to:

- a source classified `canonical` by the Akron source policy;
- atomic locator `record:1`; and
- an exact artifact SHA-256.

### Broad raw pool

Historical JSON SHA-256:

`2ecd580b7289512627f07af73cf11c72bdb4df9e35fe091a15dfdb137c7a1635`

### Curation record

Historical SHA-256:

`c767a227c6e433d00aae84a83a09554c334c72ac1bf468451cdb0bf91ce75119`

### Pool summary

Historical SHA-256:

`b663c52c369df1268a8d3716c3ce45729776ffc6fae427938a8bedae91c8179c`

### Structured profile

Historical SHA-256:

`53bedcd213a8ff2bc80092dd9804510839fdcf6e9d4e376459f68131b10fc224`

### Score receipt

Path:

`experiments/akron-2026/retrieval/R1_TRANSFER_V1_SCORE.md`

Evaluation depth:

`k=10`

Scoring workflow run:

`32302508603`

Scoring artifact ID:

`9383700181`

Scoring artifact digest:

`sha256:7406e8c84cb8bedc0363bfd0c586cafb2cba113bf433d4fd351d45bbad945e9a`

First scoring head:

`dce8e2cd4dbfd9e2af777b8ec7cd5cde1e7f8fcd`

Durable compact score bundle:

`experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz`

Historical bundle SHA-256:

`afb475dc59c57056155776e54c97cf9eb33e62c55c8d66a35ba4f59c7f143af2`

Exact score-file identities recorded by the receipt:

| File | Historical SHA-256 |
| --- | --- |
| `evaluation.json` | `3793ef6cabfc0643a3b5f76bfcd5dc81de7d9b1662264288f3442d7ea5d691ce` |
| `scorable-report.json` | `5bf5f5fb0f2ae4f4b7fd6dfdc0f4b79e8fad24ef1270ca14e163e5741a110826` |
| `summary.json` | `f8e7957c348dc78b6a6df8fd2e6f8e0e4e5c6a69155687aff958ad3e8029a292` |
| `index.json` | `74e8d665e0b8f74ee3083a5cf42f79b1b7531c80a67985abccce462b9c49329f` |
| `status.json` | `abf3a1d681aae2363983ee53d1aa03610b3931f0af62b8fd71d947d2b0a7aaa0` |

Live-source identities recorded by the score receipt:

| File | Historical SHA-256 |
| --- | --- |
| `agenda-items.json` | `375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0` |
| `sync.json` | `084dce08bbf0d6ff95d31439edb371275f7a3fe7c9ff6b2a5a72bcec09942771` |

Reported bounded result:

- 37/37 scorable
- 32/32 positive cases hit
- 54/54 explicit positive targets recovered
- 5/5 negative controls passed
- expectation accuracy 1.0
- target recall @10 1.0
- provenance validity 1.0
- unresolved targets 0
- retrieval failures 0

---

## C. Canton R0 governance demonstration

Minimum publication evidence should identify:

- the deterministic machine-selected lead identity;
- the evidence packet that produced the candidate;
- the version-controlled human review receipt;
- the append-only disposition `explained`; and
- the documented rationale that the observed changing dates were consistent with sequential expenditure-deadline amendments.

The publication must not characterize this case as a corruption or wrongdoing detection result.

Primary experiment documentation:

`experiments/canton-2026/README.md`

Review-record contract:

`docs/REVIEW_RECORDS.md`

---

## D. Publication-owned artifacts to create before deposit

- [ ] final manuscript source
- [ ] rendered archival manuscript (PDF or repository-supported archival format)
- [ ] final bibliography
- [ ] machine-readable publication artifact manifest
- [ ] exact repository commit/tag used by the publication
- [ ] SHA-256 verification report generated from the final deposit bytes
- [ ] README for the measurement package
- [ ] license/rights statement for the manuscript
- [ ] rights/redistribution decision for each third-party source artifact class
- [ ] persistent identifier metadata (after deposit)

---

## E. Redistribution boundary

### Safe default for the first deposit

Deposit research-authored benchmark definitions, score outputs, manifests, receipts, code references, and source-provenance metadata.

### Separate review required

Do not automatically bundle:

- municipal PDFs;
- publisher HTML captures;
- attachments;
- notices;
- minutes source bytes; or
- other third-party content merely because it was publicly accessible.

For those materials, preserve the source URL, retrieval date, source role, locator, and hash in the research package. Add the actual source bytes only when redistribution is clearly appropriate for that artifact class.

---

## F. Integrity rule

Publication preparation must not rewrite historical benchmark or score artifacts.

If a digest fails, a source has changed, a benchmark definition needs correction, or a score must be recomputed, create a new versioned research object and explain the difference. Do not repair an inconvenient historical result in place.
