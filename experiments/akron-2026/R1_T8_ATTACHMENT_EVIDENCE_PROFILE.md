# R1.T8 — Akron Attachment Evidence Profile

## Status

Completed on the bounded production attachment sample established by R1.T7.

This stage characterizes extraction quality and deterministic structured facts only. It does **not** transfer Canton matter-key, financial-role, recurrence, or detector policy to Akron.

## Final live run

- Workflow: `r1-akron-attachment-evidence-profile`
- Run: `32382105638`
- Head: `8d0d867e588d48331e620269ed0ec03445768abd`
- Artifact: `r1-akron-attachment-evidence-profile` (`9411607002`)
- Artifact digest: `sha256:36a8402a45567cae5a9c18ee2c7bbc94b7b15a2437cccf38f94b6ed4a01e1af2`
- Full repository tests: **131 passed**
- Canton validation: passed
- Akron source-contract probe: passed

## Sampling boundary

The sample was not selected for interesting content.

R1.T7 deterministically selected eight attachment source identities from the complete Akron Supporting Documents graph using source identity only. R1.T8 rebuilt a fresh state and profiled those same eight bounded production sources.

The result is evidence about those eight PDFs, not a claim about all 2,327 discovered Akron attachments.

## Extraction result

The eight PDFs contained **39 logical pages**.

| Measure | Result |
| --- | ---: |
| Attachment documents | 8 |
| Total pages | 39 |
| Native nonblank pages | 24 |
| Native pages below 0.70 quality | 15 |
| Documents requiring OCR | 4 |
| OCR pages attempted | 15 |
| OCR extractions added | 15 |
| OCR failures | 0 |
| Post-OCR nonblank pages | 39 |
| Post-OCR pages below 0.70 | 0 |

Preferred extraction after escalation:

- `pymupdf_native_text`: 24 pages
- `pymupdf_tesseract_ocr`: 15 pages

Tesseract version in the final live run: `5.3.4`.

### Extraction decision

Progressive OCR is justified for Akron attachment evidence. In this bounded sample, **15/39 pages (38.5%)** and **4/8 documents (50%)** would have remained below the declared quality floor without OCR. Quality-gated escalation recovered every one of those pages without changing logical page identity.

This does not justify OCR-everything. Native extraction remained preferred for 24/39 pages, so the existing progressive policy is the correct boundary.

## Structured-fact result

Before OCR, the sampled attachments produced:

- 14 date facts
- 5 money facts

After preferred OCR escalation, they produced:

- 21 date facts
- 31 money facts

OCR therefore added **26 preferred money facts** and 7 preferred date facts to this sample.

The important result is not simply that the count increased. The recovered money facts demonstrate why raw currency extraction must remain separate from financial interpretation.

## Money-fact composition

The 31 post-OCR money facts are heterogeneous.

### Three scanned conditional-use petitions

Three image-only conditional-use petitions each contain the same fee schedule on page 2.

Each fee schedule contributes eight explicit currency tokens:

- `$0`
- `$20,000`
- `$250`
- `$20,001`
- `$100,000`
- `$750`
- `$101,001`
- `$1,500`

That is **24/31 money facts** in the final profile. They are repeated fee thresholds and fees, not 24 distinct expenditures, contracts, awards, or transfers.

One of those petitions also contains an explicit **`$400,000` estimated project cost**, bringing the three petition documents to 25 money facts total.

### Other OCR-recovered token

A scanned appointments packet produced one `$138` token. R1.T8 does not assign it financial meaning. It remains an unclassified extracted currency token until its local context is evaluated.

### Native-text documents

The four native-text documents contributed five money facts:

- `$51,780`
- `$ 51`
- `$ 853,000.00`
- `$4.50`
- `$11.25`

The `$4.50` and `$11.25` values occur in a special-assessment ordinance and are rates, not total expenditures.

`$ 51` is suspicious beside `$51,780` and should not be promoted into a financial role without examining its exact local Silver context. R1.T8 preserves it as extraction output rather than silently deleting or repairing it.

One 13-page native-text attachment in the bounded sample produced no explicit money facts.

## What T8 proves

1. **Attachments materially change Akron evidence coverage.** Canonical agenda-item text previously produced no explicit monetary facts; the bounded supporting-document layer does.
2. **Progressive OCR is necessary.** Half of the sampled documents contained pages that native extraction could not use at the declared quality floor.
3. **OCR can preserve Proofline's evidence boundary.** All 15 escalated pages became preferred evidence with zero OCR failures while retaining the same Bronze artifact and page identity.
4. **Currency syntax is evidence, not interpretation.** A deterministic money fact cannot be treated as an expenditure, award, conflict, or anomaly merely because it contains `$`.
5. **Repeated boilerplate can dominate raw counts.** Twenty-four of 31 post-OCR money facts came from the same application fee schedule repeated in three documents.
6. **Null and ambiguous outputs remain valid.** The 13-page document with zero money facts and the ambiguous `$138` / `$ 51` tokens are retained rather than tuned away.

## What T8 does not prove

R1.T8 does not establish:

- an Akron financial-conflict population;
- an Akron matter-key contract;
- a relationship between any extracted amount and a person, vendor, award, payment, or appropriation;
- that repeated fee-schedule values should contribute independent financial signal;
- that `$138` or `$ 51` are valid financial values for downstream analysis;
- that the eight-document sample is representative of all 2,327 attachments.

## Decision for R1.T9

Do **not** move directly to a Canton-style financial detector.

The next stage should characterize **money roles in local Silver context** before any financial lead logic is authorized.

R1.T9 should remain bounded and retrieval-blind. For each of the 31 frozen T8 money facts it should emit the surrounding preferred Silver context and derive a conservative Akron attachment role profile from explicit document language. Candidate roles to test include:

- `fee_schedule_threshold`
- `fee_schedule_fee`
- `estimated_project_cost`
- `assessment_rate`
- `reported_or_authorized_amount` only where the document explicitly establishes that role
- `suspected_extraction_artifact`
- `unclassified_money`

Rules should be frozen only after inspecting the bounded contexts. Repeated boilerplate should be recognized as repeated context, not counted as independent financial events. Values that cannot be assigned a role from explicit local evidence should remain unclassified.

Only after that role profile is measured should Proofline decide whether a larger bounded attachment sample, matter linking, recurrence analysis, or an Akron-specific financial detector is justified.
