# R1 Akron Transfer Retrieval Benchmark v1 — First Score

This record preserves the first retrieval score of the 37-case Akron transfer benchmark frozen before any retrieval result was consulted.

## Provenance

- Frozen suite: `r1-transfer-v1-unscored.json.gz`
- Freeze receipt: `R1_TRANSFER_V1_FREEZE.md`
- Frozen deterministic gzip SHA-256: `2beb620c3421389575175349e28f16dd4ef75364fcf675efe7933d298c49da78`
- Frozen decompressed JSON SHA-256: `fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681`
- Scoring workflow: `r1-akron-retrieval-evaluation`
- Scoring workflow run: `32302508603`
- Scoring artifact ID: `9383700181`
- Scoring artifact digest: `sha256:7406e8c84cb8bedc0363bfd0c586cafb2cba113bf433d4fd351d45bbad945e9a`
- First scoring head: `dce8e2cd4dbfd9e2af777b8ec7cd5cde1e7f8fcd`
- Evaluation depth: `k=10`

The workflow verified both frozen benchmark identities before scoring and again after scoring.

## Durable score core

The exact compact measurement core is preserved as:

`r1-transfer-v1-score-core.tar.gz`

Deterministic bundle SHA-256:

`afb475dc59c57056155776e54c97cf9eb33e62c55c8d66a35ba4f59c7f143af2`

The bundle contains the exact first-run bytes for:

- `evaluation.json` — SHA-256 `3793ef6cabfc0643a3b5f76bfcd5dc81de7d9b1662264288f3442d7ea5d691ce`
- `scorable-report.json` — SHA-256 `5bf5f5fb0f2ae4f4b7fd6dfdc0f4b79e8fad24ef1270ca14e163e5741a110826`
- `summary.json` — SHA-256 `f8e7957c348dc78b6a6df8fd2e6f8e0e4e5c6a69155687aff958ad3e8029a292`
- `index.json` — SHA-256 `74e8d665e0b8f74ee3083a5cf42f79b1b7531c80a67985abccce462b9c49329f`
- `status.json` — SHA-256 `abf3a1d681aae2363983ee53d1aa03610b3931f0af62b8fd71d947d2b0a7aaa0`

The full Actions artifact also contains the live acquisition receipts:

- `agenda-items.json` — SHA-256 `375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`
- `sync.json` — SHA-256 `084dce08bbf0d6ff95d31439edb371275f7a3fe7c9ff6b2a5a72bcec09942771`

The agenda-manifest hash exactly matches the prior T2/T4 Akron manifest identity.

## Live source state at first score

The clean scoring rebuild independently produced:

- **33** meetings with available agendas;
- **1,475** canonical agenda-item resources;
- **1,475 new / 0 changed / 0 unavailable** canonical watcher results in the clean state;
- **1,509** evidence units indexed in total, including support provenance;
- **1,025** structured facts;
- lexical query mode: `all_terms`;
- lexical tokenizer: `unicode61 remove_diacritics 2`.

This matters because the perfect score was not obtained by silently dropping unresolved frozen targets or changing the publisher population.

## Raw evaluator result

- cases: **37**
- expectation accuracy: **1.0**
- positive hit rate at 10: **1.0**
- target recall at 10: **1.0**
- negative accuracy: **1.0**
- provenance validity: **1.0**
- unresolved target count: **0**
- failure classes: **none**

## Scorable result

- scorable cases: **37/37**
- unscorable cases: **0**
- positive cases: **32/32 hit**
- explicit positive target recall: **54/54 = 1.0**
- negative controls: **5/5 = 1.0**
- mean scorable provenance validity: **1.0**
- scorable retrieval failures: **0**

Per-mode scorable expectation accuracy is **1.0** for:

- lexical;
- exact date;
- publisher-native identifier;
- identifier negative control;
- money negative control.

There were no positive money cases because the frozen canonical Akron corpus contained no explicit currency evidence. The negative money case remained a valid false-positive guard.

## Transfer result

Akron materially differs from Canton at the publisher and evidence-unit layers:

- Canton canonical meeting evidence is PDF/page based and required agenda-item segmentation;
- Akron canonical evidence is publisher-supplied agenda-item HTML and is already atomic at `record:1`.

Despite that difference, the same Proofline Bronze/Silver storage, extraction, lexical retrieval, structured retrieval, provenance resolution, and evaluation contracts transferred without a source-specific retrieval implementation.

The first frozen Akron benchmark therefore strengthens the transfer claim: deterministic retrieval reproduced every frozen target across a second municipal publisher stack while preserving exact evidence provenance.

## Decision on semantic/vector retrieval

**Still not justified by measured evidence.**

Across the frozen Akron suite there was no lexical miss, no partial target recall, no structured retrieval miss, no unresolved frozen target, no negative-control failure, and no provenance failure.

This does not claim universal retrieval completeness. It records that neither the broader Canton canonical benchmark nor the first Akron transfer benchmark has exposed a failure class requiring probabilistic/vector retrieval complexity.

## Integrity rule

The frozen suite and this first score are historical measurement records. Future publisher changes, benchmark expansion, evaluator changes, or retrieval changes must create a new versioned measurement rather than rewriting this result.
