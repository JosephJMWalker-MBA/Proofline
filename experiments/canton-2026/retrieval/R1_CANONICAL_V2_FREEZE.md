# R1 Canonical Retrieval Benchmark v2 — Freeze Receipt

This receipt establishes the historical boundary between **canonical benchmark selection** and
**retrieval scoring** for the second R1 Canton benchmark.

The suite was generated from live Canton evidence with an explicit source-role policy, curated for
question quality, inspected while still unscored, and then copied byte-for-byte from the inspected
GitHub Actions artifact into Git history.

## Frozen identities

- Source-policy file: `source-policy.json`
- Source-policy schema: `proofline-benchmark-source-policy/v1`
- Target source role: **canonical**
- Unscored pool workflow run: `32287927032`
- Inspected artifact ID: `9378375454`
- Inspected artifact digest: `sha256:bace0c05e8d8c07c84f1326fe2d1facbb4b90d5c2c47d7d117ccec705c4e30b4`
- Frozen benchmark: `r1-canonical-v2-unscored.json`
- Frozen benchmark SHA-256: `aee4d01b3b7fa505d008296e226bbaff43af6022c025ad9764f14b412e9cfbbc`
- Preserved broad raw pool: `r1-canonical-v2-raw-pool.json`
- Raw pool SHA-256: `60807ca48ce44f5fd400b5509fedaec5a34e99b34b8619bfe3f8b3674207c0b3`
- Source rebuild `sync.json` SHA-256 at selection time: `1b85ad9b0e10761096acf47147d2bac39e430e64211b66ffd365561c0d0988f5`
- Evaluation schema: `proofline-retrieval-eval/v2`
- Retrieval results consulted before freeze: **false**

## Frozen suite composition

The curated suite contains **42 cases**:

- 5 cross-record lexical/entity cases
- 8 unique lexical/entity cases
- 8 exact money cases
- 8 exact date cases
- 8 publisher-native identifier cases
- 5 deterministic negative controls

Every positive expected target is bound to:

- a source URI classified `canonical` by the frozen source policy;
- a page-level locator (`page:*`);
- an exact artifact SHA-256.

Canonical source families are Board current Agenda PDFs, Board ArchivedAgenda PDFs, and published
City Council CivicClerk meeting-file PDFs. Discovery/support pages remain preserved provenance but
are not positive targets in this benchmark.

## Integrity rule

This benchmark version is write-once. Retrieval misses, target-resolution failures, or future
publisher changes are measurements, not reasons to edit the frozen suite.

Any later benchmark revision must receive a new filename/version and its own pre-score freeze
receipt.
