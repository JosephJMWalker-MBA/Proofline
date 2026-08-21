# R1.T18 — Bounded Local Layout Relationship Probe

## Status

R1.T18 is complete as a **post-hoc capability measurement** on the already-opened T13b/T14 development population.

It does not authorize document semantics, financial roles, event identity, detectors, or leads.

## Why T18 exists

R1.T17 established a deterministic spatial word-evidence substrate across native and OCR extraction, but rejected two simple structural assumptions:

- **0/6** frozen fee-schedule groups were separable by the tested page-wide x-band rule;
- `CASH ASSESSED` and `$220,682.90` were both preserved spatially but were not assigned the same PyMuPDF line.

T18 asks whether bounded local geometry preserves useful relationships that those global/extractor-native identities lose.

## Frozen evidence boundary

The workflow regenerated T17 spatial evidence from the exact already-opened population and required:

- source identities: **32**;
- unique Bronze artifacts: **28**;
- exact source→Bronze matches: **32/32**;
- Bronze byte drift: **0**;
- T13b ranks 33–64 signature: `b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966`;
- source→artifact mapping signature: `797f8986110664bf23019536a3c9721c7e283cd81b730e3eb867459b34848edf`;
- T17 target spatial pages: **7** — one native and six OCR-backed.

This is not a new holdout or an out-of-sample accuracy estimate.

## Reusable local-layout boundary

`src/proofline/local_layout.py` derives deterministic region and relation records from an existing T17 `SpatialPageResult`.

It preserves geometry and extraction-relative evidence only:

- exact `spatial_id` and page `evidence_id` lineage;
- deterministic region/relation identities;
- region bounding boxes;
- center deltas and Euclidean distance;
- page-normalized distance;
- local-word-height-normalized distance;
- horizontal/vertical overlap;
- horizontal/vertical edge gaps;
- reading-order delta;
- extractor-line coincidence;
- dominant geometric direction;
- bounded nearby-word relations ordered by measured distance.

No table, row, column, field, key/value, financial-role, transaction, event, anomaly, conflict, wrongdoing, or lead semantics are assigned.

## Measurement design

The fee measurement uses the frozen T14 `supported` / `contradicted` dispositions only as **post-hoc comparison labels**. Geometry never emits those labels.

For every frozen money target, T18 measures the nearest other money target by normalized local geometric distance and asks only whether the frozen comparison labels agree.

On these six fee pages, the frozen target set is also the complete page money-observation set:

- fee target regions: **49**;
- total money-observation regions on those six pages: **49**;
- omitted non-target money regions: **0**.

The assessment measurement ranks the frozen `$220,682.90` region among all explicit-currency money regions on the page by geometric distance from the `CASH ASSESSED` region.

No result-dependent distance threshold is fitted.

## Successful live run

Workflow: `r1-akron-local-layout-probe`

Run: **32493548953**

Validated PR head: `2fa4dd93bcc60b81ab4b106b5ab13b8d19232c6e`

Artifact: `r1-akron-local-layout-probe` (**9451052950**)

Artifact digest:

`sha256:7f8cc2ba38033b19c32a2f785190e876c773f95a09a3ccfbe7910caa7be737a6`

Runtime:

- Python **3.12.14**;
- Tesseract **5.3.4**;
- full repository suite: **200 passed**;
- Canton validation: passed;
- Akron OnBase probe: passed.

The dedicated workflow rebuilt the complete publisher-backed attachment graph, reproduced the exact frozen selection and Bronze map, regenerated T17 geometry, derived T18 relations, passed every non-semantic governance gate, and uploaded the full evidence bundle.

## Result 1 — local geometry strongly preserves the fee distinction

Canonical compact result:

- frozen fee money regions: **49**;
- regions with a comparable nearest money peer: **49**;
- nearest peer with the same frozen T14 disposition: **49/49**;
- nearest-peer same-disposition rate: **1.0**.

Because the six pages contain no additional money observations outside these 49 targets, this is not an artifact of excluding competing page money regions.

This is a materially different result from T17's **0/6** page-wide x-band separation. The evidence says that the lost distinction is strongly organized in **local geometry**, even though one global page partition is insufficient.

### Pair-distance characterization

The following aggregate is derived after the successful run from the canonical T18 artifact's per-page pair summaries. It is descriptive, not preregistered accuracy evidence.

Normalized by page diagonal:

| Relationship | n | min | median | max |
| --- | ---: | ---: | ---: | ---: |
| within `supported` | 23 | 0.008995 | 0.024161 | 0.086504 |
| within `contradicted` | 64 | 0.008823 | 0.068389 | 0.097612 |
| cross-disposition | 101 | 0.079488 | 0.149359 | 0.184432 |

The medians are strongly separated, but the ranges overlap. T18 therefore **does not** justify a universal hard distance threshold.

The appropriate conclusion is weaker and more useful: deterministic local relationship structure exists and is worth representing without prematurely converting geometry into financial semantics.

## Result 2 — spatial alignment recovers what extractor line identity lost

The assessment counterexample remains cross-line under PyMuPDF:

- `same_extractor_line`: **false**;
- reading-order delta: **1**.

But the local relation between `CASH ASSESSED` and `$220,682.90` preserves exact visual alignment:

- center distance: **306.455 points**;
- `dx`: **306.455 points**;
- `dy`: **0.0 points**;
- horizontal gap: **242.028 points**;
- vertical gap: **0.0 points**;
- horizontal overlap ratio: **0.0**;
- vertical overlap ratio: **1.0**;
- normalized `dx` / page width: **0.500743**;
- normalized center distance / page diagonal: **0.306178**;
- dominant direction: **right**.

So extractor line identity lost a field-like visual relationship that the spatial layer can still preserve.

The money-distance rank itself is weak evidence:

- explicit-currency money candidate regions on the page: **1**;
- target rank: **1/1**;
- target is nearest money region: **true**.

Because there is no competing explicit-currency candidate, T18 does **not** claim robust key/value disambiguation from this example.

## Stage decision

T18 supports a positive infrastructure conclusion and a negative semantic conclusion at the same time.

### Supported

**Local geometry is materially informative on the frozen T14 structure-failure population.**

The 49/49 nearest-peer result, the pair-distance pattern, and the assessment vertical alignment justify continuing below semantics with a deterministic local-grouping / relationship representation.

### Not supported

T18 does **not** rehabilitate the page-wide x-band rule, justify a universal distance threshold, establish a table or key/value parser, validate a financial-role classifier, or authorize a detector.

### Next boundary

Before further representation development inspects any new documents, freeze a new untouched source-identity holdout from the preserved Akron attachment population.

Then, using only already-opened evidence, develop a **label-free deterministic local-grouping / relationship representation** based on relative geometry rather than T14 semantic labels. Evaluate its structural transfer on the untouched holdout before freezing any new financial semantic contract.

This keeps the sequence explicit:

```text
T17 spatial evidence
→ T18 local relationship capability
→ new untouched holdout freeze
→ label-free local grouping representation
→ structural transfer evaluation
→ only then reconsider financial semantics
```

## Non-claims

- T18 is not out-of-sample validation.
- The frozen T14 labels are comparison labels, not detector output or human ground truth.
- **49/49** nearest-peer agreement on this opened failure population is not a universal fee-table classifier or a population accuracy estimate.
- The within-class and cross-class distance ranges overlap, so T18 does not justify a universal hard cutoff.
- Assessment rank **1/1** is not evidence of robust key/value disambiguation.
- Visual alignment evidence is not field identity, transaction identity, or event independence.
- No anomaly, conflict, suspiciousness, wrongdoing, recurrence, investigative lead, or detector conclusion is produced.
- Detector authorization remains **false** and lead count remains **null**.
