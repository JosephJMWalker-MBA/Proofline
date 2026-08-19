# R1 Akron Transfer Retrieval Benchmark v1 — Freeze Receipt

This receipt establishes the historical boundary between **retrieval-blind benchmark selection** and **retrieval scoring** for the first Akron transfer benchmark.

The suite was generated from live Akron OnBase evidence after T3 established that each canonical agenda-item source is already one atomic `record:1` evidence unit. Selection and curation were performed without building or consulting the lexical retrieval index. Human inspection considered only question quality, target quality, source role, and exact evidence identity. No retrieval result, rank, score, hit, or miss was consulted before this freeze.

## Frozen identities

- Source-policy file: `experiments/akron-2026/source-policy.json`
- Source-policy schema: `proofline-benchmark-source-policy/v1`
- Target source role: **canonical**
- Unscored pool workflow run: `32300387686`
- Inspected artifact ID: `9383051730`
- Inspected artifact digest: `sha256:d8848900139e7f6e145225ab41e2797f2655171310371e8d99d5b96d4b010f0f`
- Inspected PR head: `50ef1851ea77a410cf3116a99e856ef9fb9c9a6d`
- Frozen benchmark: `r1-transfer-v1-unscored.json.gz`
- Decompressed benchmark JSON SHA-256: `fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681`
- Deterministic gzip SHA-256 (`mtime=0`): `2beb620c3421389575175349e28f16dd4ef75364fcf675efe7933d298c49da78`
- Broad raw pool JSON SHA-256: `2ecd580b7289512627f07af73cf11c72bdb4df9e35fe091a15dfdb137c7a1635`
- Curation record JSON SHA-256: `c767a227c6e433d00aae84a83a09554c334c72ac1bf468451cdb0bf91ce75119`
- Pool summary JSON SHA-256: `b663c52c369df1268a8d3716c3ce45729776ffc6fae427938a8bedae91c8179c`
- Structured profile JSON SHA-256: `53bedcd213a8ff2bc80092dd9804510839fdcf6e9d4e376459f68131b10fc224`
- Source rebuild `sync.json` SHA-256: `d72960eadc117b28d33249a5ad5cb3aca5d918df6206684fc23d568ef401f37b`
- Evaluation schema: `proofline-retrieval-eval/v2`
- Retrieval results consulted before freeze: **false**

The inspected JSON is stored compressed only to keep the historical fixture small. Recover the exact frozen bytes with:

```bash
gzip -dc experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz > /tmp/r1-transfer-v1-unscored.json
sha256sum /tmp/r1-transfer-v1-unscored.json
```

The SHA-256 must equal the decompressed benchmark identity above before scoring.

## Frozen suite composition

The curated suite contains **37 cases**:

- 8 cross-record lexical/entity cases
- 8 unique lexical/entity cases
- 8 exact date cases
- 8 publisher-native identifier cases
- 5 deterministic negative controls

The suite contains **54 explicit positive evidence targets**. Every positive target is bound to:

- a source URI classified `canonical` by the Akron source policy;
- the atomic locator `record:1`;
- an exact artifact SHA-256.

Search-result and agenda-tree pages remain support/provenance only and cannot become positive benchmark targets.

## Money absence is evidence, not missing coverage

The canonical Akron agenda-item corpus produced no structured money facts and no explicit `$`, `USD`, or `dollar(s)` markers at selection time. Three canonical records contain a comma-formatted `1,200`, but those occurrences describe a physical quantity such as `1,200 feet` and are deliberately not promoted to money.

Accordingly, the frozen suite contains no positive money case. The deterministic negative money control remains present.

## Inspection note

Two accepted unique lexical questions — `Fund Balance Projections` and `Narrative Explanations` — intentionally resolve to the same canonical **Mid Year Budget Review** agenda item. They were retained because they represent distinct, intelligible information needs against one legitimate atomic record rather than duplicate publisher UI noise.

## Integrity rule

This benchmark version is write-once. Retrieval misses, target-resolution failures, future publisher changes, or inconvenient scores are measurements, not reasons to edit the frozen suite.

Any later benchmark revision must receive a new filename/version and its own pre-score freeze receipt. The first retrieval score must occur in a separate development step after this exact frozen identity exists in Git history.
