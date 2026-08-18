# Proofline Governance

Proofline is designed to amplify investigative attention without converting machine pattern detection into accusation.

## Core epistemic boundary

The system distinguishes four things:

1. **Source fact** — something directly present in a preserved public artifact.
2. **Extracted evidence** — a machine-readable representation of source material, with method and quality metadata.
3. **Observation** — a reproducible pattern or discrepancy computed from evidence.
4. **Interpretation / lead** — a hypothesis or line of inquiry that may deserve human investigation.

These categories must not be silently collapsed.

## Human authority

Proofline may rank, group, compare, summarize, and suggest questions. It does not decide:

- guilt or innocence
- corruption or fraud
- whether an allegation is true
- whether something is newsworthy
- whether something should be published
- whether a named person deserves public suspicion

Those decisions require human judgment, contextual reporting, response from affected parties, and appropriate editorial/legal review.

## Evidence requirements

Consequential observations should carry the evidence needed to reproduce them.

Minimum expectation:

```text
artifact identity
source/native identifier
retrieval/version information
evidence unit locator
relevant excerpt/value
method that produced the observation
uncertainty or confidence where applicable
```

No generated prose should become a source of record merely because another model later cites it.

## Independent corroboration

Proofline must distinguish source independence from repetition.

A claim repeated by:

- three mirrors of one document,
- three articles quoting the same anonymous source, or
- three databases populated from the same filing

is not automatically independently corroborated.

Where possible, provenance should make shared ancestry explicit.

## Benign-explanation discipline

A lead should preserve plausible ordinary explanations when they are known or discoverable.

Example:

```text
Observation: procurement competition was waived.
Possible benign explanation: emergency procurement authority was in effect.
Question for reporter: what legal authority was invoked, and did the purchase meet its conditions?
```

The goal is to create better questions, not more confident suspicions.

## Named-person safeguards

A person's appearance in a public record is not evidence of misconduct.

Entity graphs and co-occurrence systems are especially vulnerable to guilt-by-association errors. Relationship edges should therefore distinguish:

- explicit relationships stated by a source
- structured relationships derived deterministically
- proximity/co-occurrence only
- probabilistic or LLM-inferred relationships

The interface should make these categories visible.

## Version integrity

Public records can change after publication. Proofline should preserve observed versions rather than overwrite them.

A later version does not automatically prove improper alteration; it creates a fact that can be investigated:

```text
Artifact A retrieved at T1 had hash X.
Artifact B retrieved from the same source at T2 had hash Y.
These versions differ in specified regions.
```

Any explanation of *why* they differ belongs at the interpretation layer unless independently documented.

## Extraction uncertainty

OCR and multimodal extraction are fallible.

Low-confidence text should remain identifiable as low confidence. Human-facing evidence views should make it possible to inspect the original source alongside the extraction when practical.

A detector should not treat a low-confidence OCR token as equivalent to a reliable native field without reflecting that uncertainty.

## Editorial trace

Lead lifecycle should preserve review history rather than overwrite it.

Suggested states:

```text
candidate
triaged
investigating
explained
corroborated
rejected
published
archived
```

A rejected lead is useful training evidence for future detector calibration. It should not simply disappear.

## Privacy and harm minimization

Public availability does not eliminate the possibility of harm. Proofline deployments should account for:

- victims and minors
- inadvertently exposed personal information
- protected or sealed information
- doxxing risk
- records whose publication status is disputed
- data whose reproduction may create harm disproportionate to investigative value

Collection capability and publication policy are separate decisions.

## Guiding principle

> “The one who states his case first seems right, until the other comes and examines him.” — Proverbs 18:17

Proofline should structurally encourage examination: preserve the record, surface competing evidence, retain uncertainty, and make it easy for humans to test the machine's interpretation.
