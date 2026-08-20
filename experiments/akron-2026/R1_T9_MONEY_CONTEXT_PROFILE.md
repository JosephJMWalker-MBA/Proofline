# R1.T9 — Frozen Akron Money Context Profile

## Status

Completed on the exact 31-money-fact population frozen from R1.T8.

R1.T9 is a characterization stage. The machine-readable output assigns **no semantic money roles**. Its purpose is to prove that the same Bronze artifacts, preferred Silver evidence, money facts, and exact token anchors can be reproduced before any role contract is written.

## Final live evidence run

- Workflow: `r1-akron-money-context-profile`
- Run: `32383485273`
- Validated head: `8b28d2e4d8d3369dfee8632cbf67451091af065f`
- Artifact: `r1-akron-money-context-profile` (`9412128339`)
- Artifact digest: `sha256:f1b16b438c15eb50af8f5c23306b0cf2686196e9712c4c36bda507217dd2c170`
- Full repository tests: **135 passed**
- Canton validation: passed
- Akron OnBase source-contract probe: passed

Frozen T8 money-population signature:

`6e9ea2cc4c6e219c749e65ebc9b068b998ca5776159f37415268237b43ed3df0`

## Reproduction result

The fresh T9 state reproduced:

- **7/7** frozen money-bearing source identities;
- **7/7** exact T8 Bronze artifact identities;
- **31/31** frozen structured money facts;
- the exact frozen population signature;
- **31/31** exact `char_start:char_end` token anchors in preferred Silver;
- **8** unique preferred-Silver pages containing those facts;
- **0** machine-assigned semantic roles.

Preferred-Silver extraction behind the 31 facts:

- `pymupdf_tesseract_ocr`: 26 facts
- `pymupdf_native_text`: 5 facts
- minimum preferred quality: `0.9996`
- maximum preferred quality: `1.0`

Each fact now has a 320-character local context window, evidence ID, extraction method and quality, source URI, Bronze artifact ID/SHA, page-text SHA-256, byte-level context SHA-256, and normalized-context SHA-256.

## What the local Silver actually says

The following categories are a **human characterization of the frozen T9 contexts**, not output labels from the T9 profiler and not a production classifier.

### Conditional-use fee schedule — 24 facts across three petitions

Three separate scanned conditional-use petitions reproduce the same City of Akron filing-fee table. The local text explicitly pairs the heading/labels:

- `Estimated TOTAL Project Cost`
- `Applicable Fee`
- `A NON-REFUNDABLE FILING FEE`

with these values:

| Contextual meaning | Values per petition | Occurrences across 3 petitions |
| --- | --- | ---: |
| Project-cost range boundaries | `$0`, `$20,000`, `$20,001`, `$100,000`, `$101,001` | 15 |
| Filing-fee amounts | `$250`, `$750`, `$1,500` | 9 |

These 24 facts are not 24 financial events. They are three repetitions of the same fee schedule. The range boundaries are reference thresholds; the fee values are schedule prices.

The contexts also contain a separate sentence that a fee `has been ... received for investigation incident to this proposal`, but the frozen structured facts above are the printed schedule values. T9 does not infer the actual paid fee from OCR-corrupted handwritten material.

### Estimated project cost — 1 fact

One conditional-use petition contains the explicit field:

`Estimated TOTAL project cost: $400,000`

This supports a future role such as `estimated_project_cost`. It does not establish that the City paid, awarded, appropriated, or received $400,000.

### City expenditure form — 2 structured facts, one underlying amount repeated

A native-text Uniform Report context explicitly says:

- `City Expenditures`
- `Amount: $51,780 .00`
- `Total expenditure (if applicable): $ 51 ,780.00`

The current structured parser emits two facts:

- `$51,780` → `51780.00`
- `$ 51` → `51.00`

The second fact is **not** a real $51 amount. It is a parser-fragmentation defect caused by whitespace around the comma in `$ 51 ,780.00`. The surrounding Silver proves the intended printed amount is $51,780.00.

This is also a useful anti-double-counting example: the form repeats the same expenditure in an `Amount` field and a `Total expenditure` field. Even after parser repair, those are two evidence occurrences supporting one form-level amount, not automatically two independent expenditures.

### Contract amount — 1 fact

A native-text context states that the City is to contract with **Raftelis** to support implementation of **SpryCIS**, states that it will be funded from an **OWDA loan** for the Fixed Network Advanced Metering Infrastructure project, and prints:

`$ 853,000.00`

The local wording is strong enough to motivate a future `contract_amount` / explicitly authorized-or-reported contract role. T9 does not yet promote that role into code.

### Special-assessment rates — 2 facts

A native ordinance context identifies a resurfacing project and prints:

- `RESURFACING RESIDENTIAL/CHARITABLE $4.50`
- `RESURFACING OTHER USE $11.25`

followed by `CASH ASSESSED: 205,010.28` and installment information.

The `$4.50` and `$11.25` facts are rates, not total expenditures. The unlabeled `205,010.28` is intentionally not manufactured into a free-form money fact by the current explicit-currency parser.

### Private biographical sales volume — 1 structured fact with a magnitude-suffix defect

The appointments packet context is a résumé/background page. It says the person is a REALTOR and includes:

`Sold over $138MM since 2013, 466+ transactions`

The current money regex emits only `$138` and normalizes it to `138.00`. That is a **partial-token / magnitude-suffix defect**: the preferred Silver contains `$138MM`, not a standalone $138 municipal amount. It is also private biographical sales-volume context rather than a City expenditure, contract, award, appropriation, or receipt.

## Contextual composition of the frozen 31 facts

| Human-characterized context | Structured-fact count |
| --- | ---: |
| Fee-schedule project-cost thresholds | 15 |
| Fee-schedule filing-fee amounts | 9 |
| Estimated project cost | 1 |
| City expenditure-form occurrences | 2 |
| Contract amount | 1 |
| Special-assessment rates | 2 |
| Private biographical sales-volume token | 1 |
| **Total** | **31** |

This is a characterization of evidence contexts, not an estimate of distinct transactions or financial events.

## Two parser-integrity defects exposed by T9

T9 identifies two deterministic defects that should be repaired **before** building a financial-role classifier:

1. **Whitespace-separated thousands punctuation**
   - Silver: `$ 51 ,780.00`
   - Current fact: `$ 51` → `51.00`
   - Required behavior: parse the complete printed currency token or fail closed; never silently emit the prefix as a different amount.

2. **Magnitude suffix truncation**
   - Silver: `$138MM`
   - Current fact: `$138` → `138.00`
   - Required behavior: do not silently truncate a contiguous magnitude suffix. If suffix semantics are not explicitly supported, reject/exclude the partial match rather than inventing a smaller amount.

So **2/31 current structured money facts are demonstrably numerically incomplete**, even though their Silver extraction quality is high. Extraction quality and fact-parser correctness are distinct dimensions.

## Proposed role model — not yet production

T9 suggests that a future money interpretation should not be a single label. At minimum it needs separate axes for:

### Semantic role

Candidate roles supported by this bounded context set include:

- `fee_schedule_threshold`
- `filing_fee_amount`
- `estimated_project_cost`
- `city_expenditure_amount`
- `contract_amount`
- `assessment_rate`
- `private_background_amount`
- `unclassified_money`

### Numeric integrity

Candidate integrity states include:

- `exact`
- `fragmented_currency_format`
- `magnitude_suffix_truncated`
- `ocr_uncertain`
- `unclassified`

A value should not become an investigative financial signal merely because its semantic role is known. Scope, recurrence, document-level duplication, and matter linkage remain separate questions.

## Decision for the next stage

Do **not** write the Akron financial detector next.

The next stage should first harden the generic structured-money parser against the two defects proven above, with explicit regression tests. That parser change should be measured as a delta rather than retroactively rewriting the T8/T9 receipts.

After parser integrity is restored, freeze a conservative role contract derived from these T9 contexts and evaluate it on a **disjoint, content-blind attachment sample** selected by source identity and excluding the original T8 eight sources. The disjoint sample must be allowed to produce unknown/unclassified roles and null financial signal.

Only after that out-of-sample evaluation should Proofline decide whether an Akron-specific financial detector, matter linking, or recurrence analysis is justified.

## Non-claims

R1.T9 does not claim:

- that 31 money facts represent 31 transactions;
- that repeated fee schedules are independent events;
- that the `$400,000` estimate is a City expenditure;
- that both `$51,780` form occurrences are separate expenditures;
- that `$138` is a valid amount at all under the current parser;
- that every municipal dollar value in the source documents has been extracted;
- that the bounded eight-document sample represents all 2,327 Akron attachments;
- that any person, vendor, contract, or expenditure is suspicious.
