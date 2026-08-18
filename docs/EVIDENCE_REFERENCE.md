# Evidence Reference Contract — v1

Proofline evidence references are deliberately small, stable pointers from derived material back to a human-inspectable evidence unit.

## Contract

```json
{
  "evidence_id": "evidence:<sha256>",
  "artifact_id": "artifact:<sha256>",
  "locator": "page:7",
  "excerpt": "Optional convenience excerpt; never the system of record."
}
```

Required fields:

- `evidence_id` — deterministic identity of the stable evidence unit.
- `artifact_id` — content-addressed identity of the immutable source bytes.
- `locator` — human-readable locator inside the source artifact, such as `page:7`, `record:1`, `sheet:Budget!A12:F12`, or a transcript interval.

Optional field:

- `excerpt` — convenience text captured when the reference was created. It may help a human understand why the evidence was cited, but it must not replace retrieval of the current stored extraction or the original artifact.

## Deterministic evidence identity

For v1, Proofline derives an evidence identifier from:

```text
artifact_id + unit_type + locator
```

using the project's namespaced SHA-256 `stable_id` function.

This means the identity of `page:7` remains stable even when a better extraction method is later applied to the page. Extraction results are records attached to the evidence unit; they are not the identity of the evidence unit itself.

## Source lineage

Artifacts are content-addressed. The same bytes may legitimately be observed at multiple public source URIs or mirrors. Therefore an evidence reference points to the artifact and evidence unit, while source snapshots are resolved separately during tracing.

A trace may legitimately show multiple source observations for one artifact. Those mirrors must not automatically be counted as independent corroboration.

## Validation invariant

Before Proofline persists an observation or lead, each evidence reference must resolve to an existing evidence unit whose stored:

- `artifact_id` matches the reference,
- `locator` matches the reference.

A mismatched or nonexistent reference must be rejected rather than silently repaired.

## What is not part of v1

Retrieval chunks, embeddings, entity IDs, LLM citations, and search-result ranks are not evidence identity. They are disposable or derived structures that must ultimately resolve to this contract.

Future versions may add optional geometry, extraction identifiers, source-snapshot hints, or structured locators without changing the core rule:

> A consequential derived claim must be able to walk backwards to stable evidence and immutable source bytes without trusting the model that produced the claim.
