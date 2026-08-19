# R1 Retrieval Benchmark — First Frozen Score

This document records the **first retrieval evaluation** run against the R1 benchmark that was
frozen before scoring.

## Provenance

- Frozen benchmark: `r1-benchmark-unscored.json`
- Frozen benchmark SHA-256: `867d6c47f3ae542c40cfa5748a0473c9dffd9af8bf5db6fa3af711690fe2da82`
- Freeze workflow run: `32285133807`
- First scoring workflow run: `32285784539`
- First scoring artifact ID: `9377585377`
- First scoring artifact digest: `sha256:ea460875dd8253f72725e10831a8bbef76fdfe0fbf83729cb1f72813ae0a000e`
- `evaluation.json` SHA-256: `a4e9aeedc7ca933af56fb8c6eb6b6cf72387417da287ba51ea6813ba26b5efbd`
- `summary.json` SHA-256: `d835c66f3af27b645a11393eff55c74c9ff24893afc7292c3031834661de76f0`
- `sync.json` SHA-256: `9db5e748154518e750b3f78f076512e127b7256b1f36b14ab3e73e77d775bcd6`
- Evaluation depth: `k=10`

The workflow verified the frozen benchmark SHA before and after scoring.

## Raw evaluator output

The v2 evaluator reported:

- cases: **33**
- expectation accuracy: **0.8484848485**
- positive hit rate at 10: **0.8214285714**
- aggregate target recall at 10 over resolved targets: **1.0**
- negative cases: **5**
- negative accuracy: **1.0**
- provenance validity: **1.0**
- unresolved target count: **10**
- failure classes: **6 `unresolved_target` cases**

No case was classified as:

- `miss_all_targets`
- `partial_target_recall`
- `unexpected_results`
- `invalid_provenance`

## Correct interpretation

The raw expectation/hit-rate denominators mix **retrieval performance** with **frozen-target
resolvability**. Six cases contain at least one exact frozen evidence target that no longer resolves
in a fresh live rebuild because the publisher-served supporting artifact changed bytes between the
freeze and score.

Separating those cases gives:

- total cases: **33**
- cases with one or more unresolved frozen targets: **6**
- unresolved target records: **10**
- fully scorable cases: **27**
- fully scorable cases meeting expectation: **27/27**
- scorable positive cases hitting target: **22/22**
- negative controls correct: **5/5**
- provenance validity: **100%**

Therefore the first R1 score found **no deterministic retrieval failure on a fully resolvable
case**.

This does **not** prove retrieval is complete. It means the current frozen benchmark did not expose
a lexical/structured miss among cases whose exact target evidence remained resolvable at score
time.

## What failed instead: longitudinal benchmark target identity

All six failure-class cases are `unresolved_target`:

- **5 date cases**
- **1 publisher-native identifier case**

The unstable targets are discovery/supporting records such as:

- the live Agenda Center index;
- `Previous Versions` HTML pages;
- Calendar month listings;
- Calendar event pages.

Those are useful Bronze provenance for **why** Proofline acquired a record, but their bytes can
change for routine publisher reasons. Exact artifact SHA-256 is correct for immutable evidence
identity, yet a longitudinal retrieval benchmark should not depend on volatile support-page bytes
when the retrieval question is really about a stable meeting record or published file.

This is a **benchmark-design failure class**, not evidence that the retrieval engine missed the
query.

## Evaluator metric issue exposed by the frozen run

The first score also exposed a metric-contract ambiguity:

- a case can have some unresolved targets while all remaining resolved targets are returned;
- such a case receives `failure_class = unresolved_target`;
- but `expectation_met` can still be `true` because it currently considers only resolved target IDs;
- aggregate hit/recall metrics therefore mix unscorable target-resolution cases with actual
  retrieval cases.

The first-score JSON is preserved as produced. It must **not** be rewritten after discovery of this
metric issue.

A subsequent evaluator revision should report separate counts/metrics for:

1. target resolvability;
2. scorable retrieval cases;
3. retrieval success among scorable cases.

## Decision on semantic/vector retrieval

**Not justified by this run.**

There is no measured `miss_all_targets` or partial-recall failure on a fully resolvable case. The
next work should fix benchmark/evaluator measurement semantics and broaden stable canonical evidence
targets before adding semantic retrieval complexity.

## Integrity rule

The frozen R1 benchmark remains unchanged. Any improved benchmark must be a **new version with a new
pre-score freeze receipt**. The six target-volatility failures are retained as part of the first
experiment rather than removed to improve the score.
