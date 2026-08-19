# Retrieval evaluation: raw results versus scorable measurements

Proofline preserves two distinct layers of retrieval measurement.

## Raw evaluator output

`proofline evaluate` records what the evaluator observed at run time, including:

- resolved expected evidence IDs;
- returned evidence IDs;
- unresolved frozen targets;
- raw hit/recall/expectation fields;
- provenance validity;
- failure classifications.

Historical evaluation JSON is evidence and should not be rewritten after a metric-contract problem
is discovered.

## Why target resolution is separate from retrieval

A frozen benchmark can identify an exact expected artifact with:

- source URI;
- locator;
- artifact SHA-256.

If a public publisher later changes a volatile support page, that exact frozen artifact may no
longer be present in a fresh live rebuild. The benchmark target is then **unresolved**.

That is not the same as a search miss.

Proofline therefore treats a case as **scorable** only when every expected target in that case
resolves in the evaluated corpus. Negative/no-result controls have no positive targets and remain
scorable by construction.

Cases with one or more unresolved expected targets are reported separately as **unscorable** and do
not enter scorable retrieval hit/recall denominators.

## Derived scorable report

Run:

```bash
python -m proofline.evaluation_report_cli evaluation.json
```

or write a durable report:

```bash
python -m proofline.evaluation_report_cli evaluation.json --output scorable-report.json
```

The report includes:

- total cases;
- scorable cases;
- unscorable cases;
- unresolved target count;
- scorable expectation accuracy;
- scorable positive hit rate;
- scorable target recall;
- scorable negative accuracy;
- scorable provenance validity;
- retrieval failure classes **excluding** target-resolution failures;
- unscorable cases grouped by retrieval mode;
- per-mode scorable metrics.

The raw evaluator fields remain available for backward compatibility and historical reconstruction.
The derived report does not alter them.

## First R1 frozen score

The preserved first R1 evaluation is:

`experiments/canton-2026/retrieval/r1-first-score/evaluation.json`

Its raw v2 fields reported 33 cases with six `unresolved_target` cases. Reinterpreting the exact
saved JSON with the scorable-report contract gives:

- **33 total cases**
- **27 scorable cases**
- **6 unscorable cases**
- **10 unresolved frozen target records**
- **27/27 scorable expectation success**
- **22/22 scorable positive hits**
- **5/5 negative controls**
- **100% scorable target recall**
- **100% mean scorable case provenance validity**
- **0 scorable retrieval failures**

The six unscorable cases are five `date` cases and one `native_identifier` case. Their target
volatility is retained as experiment evidence; it is not relabeled as retrieval failure.

## Benchmark integrity

Do not repair a frozen benchmark after observing its score. If target-selection rules improve, make
a new benchmark version, freeze it before scoring, and retain the older version and its results.
