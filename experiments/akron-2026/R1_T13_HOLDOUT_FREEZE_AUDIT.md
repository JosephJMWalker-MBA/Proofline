# R1.T13 Holdout Freeze Audit

## Status

R1.T13 did **not** reach financial-representation evaluation.

The first executable blind run failed closed while resolving the frozen source identities. No selected T13 attachment was synced by the frozen-selection step, no holdout PDF was passed through the T13 representation evaluator, and no v2 out-of-sample facet result exists from that run.

This receipt preserves the failure rather than rewriting the original T12 freeze artifact.

## Failed run

- PR: `#68`
- workflow run: `32439675353`
- job: `96647671038`
- head: `ef278c6260408c9218cb5e20ba997a7834fa5c06`
- failed-run artifact: `9432035602`
- artifact digest: `sha256:cf7b2ce704941254de272d2f165e2c28d0db8b6f3c13bb2b2820846f7987c395`
- tests before live acquisition: **175 passed**
- exact T12 contract/evaluator/holdout Git-blob guards: passed
- full live Akron attachment discovery: passed
- representation step: **skipped**

## What failed

The T12 freeze file:

`experiments/akron-2026/r1_t13_disjoint_attachment_sources.json`

correctly recorded the intended sampling rule:

> rank attachment source identities by `sha256(source_uri)`, then `source_uri`; exclude ranks 1–32 and use ranks 33–64 as the future holdout.

However, its stored 32-element `selected.source_uri_sha256` list was not a faithful materialization of that rule.

When T13 resolved those hashes against the live 2,327-source attachment graph:

- all **32/32** development-exclusion hashes resolved;
- only **8/32** selected hashes resolved;
- **24/32** selected hashes were absent.

The sync failed before attachment download/evaluation rather than replacing missing identities.

## Publisher drift ruled out

The failed T13 workflow uploaded its live `attachment-manifest.json`.

That live manifest and the preserved R1.T8 manifest are byte-for-byte identical:

- resource count: **2,327**
- preserved T8 manifest SHA-256: `7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a`
- failed T13 live manifest SHA-256: `7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a`

Therefore the missing 24 hashes are **not** explained by intervening publisher deletion, live topology drift, or a changed ranking population.

## Deterministic re-derivation

Recomputing `sha256(source_uri)` over the preserved 2,327-source T8 manifest and sorting by `(identity_hash, source_uri)` gives:

- rank 1–32 signature: `e0e72779fb4e88f1720ff5f00dcb7ac90a11c83ed56094c32a1da2f478383afb`
- rank 33–64 signature: `b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966`
- combined rank 1–64 signature: `ce876915836a86c914ca837964a95fcc4f4857d423eaadfa91749978eb9715a0`

Comparison with the T12 stored selected list:

- correct selected identities: **8/32**
- invalid stored identities: **24/32**
- omitted true rank-33–64 identities: **24/32**

The defect is therefore a holdout-list construction/transcription error, not a failure of the declared sampling rule.

## Correction policy

The original T12 freeze file remains unchanged as historical evidence.

T13b uses:

`experiments/akron-2026/r1_t13b_disjoint_attachment_sources.json`

This corrected execution file does **not** choose a new sample. It mechanically materializes the already-declared ranks 33–64 from the same preserved manifest and same ranking rule.

No document bytes, extracted text, source names, money facts, or v2 output were used to choose or repair the source identities.

The corrected file records:

- the same 32 development exclusions;
- the true preserved-manifest ranks 33–64;
- the failed T13 run/artifact provenance;
- the deterministic rank signatures above;
- `representation_applied_in_failed_run: false`.

## Scientific interpretation

T13 is an **invalid preregistration materialization with a successful fail-closed execution**, not an out-of-sample model result.

It contributes no evidence for or against financial-representation v2 generalization.

T13b may execute the unchanged v2 contract against the corrected deterministic realization of the predeclared holdout rule. Any T13b representation outcome remains binding test evidence and must not be tuned away.

## Non-claims

This audit does not claim:

- that v2 generalized;
- that any money fact represents an independent event;
- that any amount is anomalous, conflicted, suspicious, or improper;
- that a detector or lead generator is authorized.
