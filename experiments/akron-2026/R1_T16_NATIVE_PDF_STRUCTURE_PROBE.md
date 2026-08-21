# R1.T16 — Native PDF Structure Capability Probe

## Question

Can native PDF table geometry recover the row/column distinctions that R1.T14 showed were lost by flattened text, without changing canonical Silver or tuning financial semantics against the already-opened T13b population?

## Experimental boundary

T16 is a **post-hoc development capability probe**, not a new holdout or accuracy estimate.

It reuses the exact already-opened T13b ranks 33–64 population:

- source identities: **32**
- unique Bronze artifacts: **28**
- unique artifact pages: **270**
- selection signature: `b0986198c10856b8235c87361dc54999f93c5bcb59514ca8ff26cf957db2b966`

No T12/T13b financial-representation rule was changed. `src/proofline/pdf_structure.py` remains unwired from ingestion, canonical Silver, search, and `StructuredIndex`.

## Validated run

- workflow: `r1-akron-pdf-structure-probe`
- run: **32446939703**
- measured head: `fd3aa067a09355b295323d10fc5732d8b2da262c`
- artifact: **9434556487** (`r1-akron-pdf-structure-probe`)
- artifact digest: `sha256:989fd15cbe01f0b65d995d1f86d4ff9da255753a9ea7e004594edbe496187684`
- Python: **3.12.14**
- PyMuPDF: **1.28.2**
- full suite: **190 passed**
- live attachment manifest SHA-256 remained `7f3ad866a54c15c423589439826f45210a9be11a515e1886cf9e930ecda3e82a`
- global rejected publisher links: **0**

### Exact Bronze continuity

Because a stable publisher URI does not imply stable source bytes, T16 also compared every selected source identity against the preserved T13b source-to-Bronze mapping rather than relying only on URI continuity.

- preserved T13b artifact: **9432387690**
- preserved T13b artifact digest: `sha256:d7b6a90f6133b4e457ebea201d866dcc9b465aac2fd3ba0dfa93f7d44b43e338`
- frozen map: `experiments/akron-2026/r1_t13b_source_artifact_map.json`
- source-to-Bronze mapping signature: `797f8986110664bf23019536a3c9721c7e283cd81b730e3eb867459b34848edf`
- exact source identities compared: **32 / 32**
- exact source-to-Bronze matches: **32 / 32**
- byte-identity drift: **0**

The dedicated T16 workflow now enforces this frozen mapping on reproduction runs. If any selected publisher source later serves different bytes, T16 fails closed instead of treating the new artifact as the original T13b evidence.

## Native structure result

Using `page.find_tables()` with default line-based PyMuPDF detection, T16 measured:

- artifacts with at least one detected table: **9 / 28**
- artifacts with no detected table: **19 / 28**
- pages with detected tables: **23 / 270**
- detected tables: **52**
- detected cells: **762**
- page-level detection failures: **0**

This is not a null capability result: native table detection clearly recovers useful structure in part of the population.

## T14 failure-population result

The important question was whether that capability reaches the known T14 semantic failures.

### Fee schedules

T14 contained six known fee-schedule groups where flattened text caused project-cost thresholds/ranges to be assigned the same `filing_fee_amount` type as the actual fee column.

After excluding the single malformed `$20` token already repaired by T15:

- fee-schedule groups examined: **6**
- groups structurally separable by native detected columns: **0 / 6**
- candidate native tables in the six target artifacts: **0**

The preserved T13b artifact explains why. All six target source artifacts have **zero native nonblank pages**. Every target fee-schedule fact was recovered by `pymupdf_tesseract_ocr`:

1. CRASI Homes petition — `page:2`
2. OPC Cultivation petition — `page:2`
3. Balbir Singh petition — `page:2`
4. Akron Summit Community Action petition — `page:2`
5. Information from Petitioner packet — `page:4`
6. older parking-lot conditional-use packet — `page:13`

So the native-table layer cannot recover these relationships because the relevant source pages are image/scanned evidence. The flat OCR text preserved the words but not the spatial relationships needed to distinguish the two columns.

### Assessment counterexample

T14 also found `$220,682.90` incorrectly assigned `assessment_rate` even though its preserved context says:

`CASH ASSESSED: $220,682.90`

This case is different from the fee schedules:

- source: `Supporting Document for - ()`
- artifact: `artifact:d7ca1617be6a2d6138c7d279abcc93d63934798c24f33528762a7cbe2c0cd2c2`
- locator: `page:5`
- extraction method: `pymupdf_native_text`
- quality: **1.0**
- detected-table matches for `$220,682.90`: **0**

Therefore the problem is broader than OCR tables alone. A page can have high-quality native text and still lose field/label relationships when Proofline preserves only flattened text and ruled-table detection.

## Decision

**Native `find_tables()` is not sufficient for the T14 failure population and must not be wired into canonical Silver as if it solved structure.**

The next representation boundary should be a common deterministic **spatial text layer** for both native and OCR extraction:

- word text
- page coordinates / bounding boxes
- deterministic reading order
- block/line identity where the extractor exposes it
- extraction method and software/model version
- exact link back to the existing page evidence identity

Table, row, column, and label/value relationships can then be derived from that shared geometry. Existing page text should remain untouched so historical Silver and parser reproduction stay stable.

## Governance boundary

T16 changes no financial semantics and authorizes no detector.

- canonical Silver changed: **false**
- `StructuredIndex` changed: **false**
- financial semantic contract changed: **false**
- event identity assigned: **false**
- detector authorized: **false**
- lead count: **null**

The 52 native tables are structure evidence only. They are not transactions, independent events, anomalies, conflicts, wrongdoing, or leads.
