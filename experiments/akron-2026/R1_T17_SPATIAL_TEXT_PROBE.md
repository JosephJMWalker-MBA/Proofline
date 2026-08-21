# R1.T17 — Common Spatial Text Evidence Probe

## Purpose

R1.T17 tests whether one deterministic spatial-text boundary can preserve useful word geometry across both native PDF text and Tesseract-backed OCR without changing canonical Silver or assigning financial semantics.

The task follows R1.T16, which found real native ruled-table capability but solved 0/6 frozen fee-schedule structure failures and did not recover the native-text `CASH ASSESSED: $220,682.90` relationship.

## Frozen population

T17 reuses the already-opened T13b/T14 development population. It is **not** a new holdout and must not be reported as an out-of-sample accuracy estimate.

- source identities: **32**
- unique Bronze artifacts: **28**
- exact source→Bronze matches: **32/32**
- Bronze byte-identity drift: **0**
- frozen selection signature: `b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966`
- frozen source→artifact mapping signature: `797f8986110664bf23019536a3c9721c7e283cd81b730e3eb867459b34848edf`

## Spatial evidence boundary

`src/proofline/spatial_text.py` adds a parallel derivation layer that preserves:

- the caller-supplied canonical page `evidence_id`
- artifact identity and 1-indexed page number
- page and word bounding boxes
- PyMuPDF block / line / word indices
- deterministic word order
- flat source-text SHA-256 and quality score
- native-vs-OCR extraction method
- OCR language and DPI provenance
- deterministic word signature and `spatial:` derivation identity

T17 does **not** write spatial rows to SQLite, alter canonical Silver/page text, enter search, change `StructuredIndex`, assign financial roles, create transactions/events, authorize a detector, or emit leads.

## Successful capability run

Frozen evidence comes from GitHub Actions run **32490067725** at head `ee85e5bd27856bbd4b5fe7ce79b682e0cddee1e5`.

- artifact: **9449926547** (`r1-akron-spatial-text-probe`)
- artifact digest: `sha256:6dce2fa8198bb6d3d9c8537bcd86acad1b39a2ff49c6fe575bec45a316662dc9`
- Python: **3.12.14**
- PyMuPDF: **1.28.2**
- Tesseract: **5.3.4**
- OCR contract: `eng`, 200 DPI
- full suite: **194 passed**

The probe exercised seven frozen target pages: one native-text page and six OCR-backed pages, producing **929 words** across **370 PyMuPDF lines**.

## Result 1 — geometry exists for every frozen fee group

After the T15 numeric-integrity correction, all **6/6** frozen fee-schedule groups had complete spatial observations for the expected supported filing-fee values and contradicted threshold/range values.

This is a positive infrastructure result: Proofline can preserve the relevant OCR word geometry under one provenance contract.

It is not a semantic result. The values remain observations until a separately justified representation can establish their roles.

## Result 2 — global x-band separation fails

Despite complete geometry, **0/6** fee groups were globally separable by the tested rule that all supported fee-value x-centers must lie wholly to one side of all contradicted threshold/range x-centers.

Therefore the frozen failure population rejects a simple global-column heuristic as the next financial-role boundary.

This does **not** establish that the source pages lack meaningful visual organization. It establishes only that one page-wide x-band partition is insufficient on these six known cases.

## Result 3 — PyMuPDF line identity still loses the assessment field relationship

For the frozen `$220,682.90` counterexample, T17 independently found:

- target money value matches: **1**
- `CASH ASSESSED` label matches: **1**
- same PyMuPDF line pair: **false**
- same line with label left of value: **false**

So preserving native word geometry recovers both observations but not their relationship through PyMuPDF line identity alone.

This is important: flat text was not the only lossy boundary. Treating extractor line IDs as semantic field structure would also be wrong for this counterexample.

## Stage decision

T17 establishes a viable shared spatial-evidence substrate while rejecting two overly simple structural assumptions:

1. page-wide x-band separation is not sufficient for the six fee-schedule failures;
2. PyMuPDF line identity is not sufficient for the `CASH ASSESSED` field relationship.

The next boundary should therefore remain below financial semantics and derive **bounded local layout relationships** from the preserved geometry: neighborhood, alignment, reading adjacency, local grouping, and distance evidence can be measured without declaring rows, columns, fields, transactions, or leads trustworthy in advance.

A null result at that next stage remains valid.

## Non-claims

- T17 is not out-of-sample validation.
- Spatial words, bounding boxes, block IDs, and line IDs are extraction evidence, not trusted document semantics.
- Complete geometry does not imply correct financial-role classification.
- Zero x-band separation does not imply no local document structure exists.
- The assessment counterexample does not authorize a generic key-value detector.
- No transaction identity, event independence, anomaly, conflict, suspiciousness, wrongdoing, or lead conclusion is authorized.
