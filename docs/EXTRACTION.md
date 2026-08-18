# Progressive Extraction — v1

Proofline treats extraction as an append-only attempt to read a stable evidence unit. Extraction output is not the identity of the evidence itself.

## Stable evidence, replaceable methods

For a PDF page:

```text
artifact:<sha256>
  -> evidence:<sha256>  (page:7)
      -> native-text attempt
      -> OCR attempt
      -> future layout/VLM attempt
```

`evidence_id` is derived from the immutable artifact identity, evidence-unit type, and source locator. A better OCR engine does not create a new page identity.

Each extraction attempt records:

- method
- extraction text
- quality score
- software version
- model/backend version when relevant
- timestamp
- warnings

The extraction attempt ID also includes producer/version information. An upgraded extractor may therefore append a new auditable attempt even if it emits exactly the same text as an earlier version.

## Preferred extraction

Proofline retains every attempt but selects a preferred extraction for normal review/retrieval workflows.

The v1 rule is deterministic:

1. highest quality score wins;
2. on equal quality, the newer attempt wins;
3. row order breaks any remaining tie.

Chronological attempts remain queryable. “Preferred” does not erase “earlier.”

## Quality is not truth

An extraction quality score estimates whether the source content was read cleanly enough for downstream use. It does **not** estimate whether statements inside the source are true.

Examples:

- A perfectly OCR'd false statement can have quality `1.0`.
- A badly scanned but important handwritten note can have low extraction quality.
- A structured CSV row can be parsed with quality `1.0` while still containing incorrect data supplied by its publisher.

Truth assessment belongs to later corroboration and human investigation.

## Progressive OCR

Native extraction is always attempted first for PDFs. Low-quality pages enter the review queue.

```text
native PDF text
    |
    +-- quality >= threshold --> keep; no OCR cost
    |
    +-- quality < threshold --> review / optional OCR
                                   |
                                   +--> append OCR attempt
```

The default review threshold is `0.70`.

Proofline's first OCR backend uses PyMuPDF's Tesseract bridge. Tesseract is intentionally an optional external runtime dependency: Proofline can ingest, hash, extract what it can, and queue scans for review even when Tesseract is not installed.

```bash
proofline review
proofline extract artifact:<sha256> --ocr tesseract
```

Useful options:

```bash
proofline review --threshold 0.80
proofline extract artifact:<sha256> --ocr tesseract --language eng --dpi 300
proofline extract artifact:<sha256> --ocr tesseract --force
```

`--force` is intended for deliberate reprocessing or producer-version comparisons. Normal runs skip pages whose preferred extraction already clears the threshold.

OCR failures are recorded as processing events and do not delete or replace native extraction attempts.

## Native structured records

### CSV

CSV files are streamed row-by-row. Each non-empty physical row becomes a `spreadsheet_range` evidence unit with a locator such as:

```text
sheet:CSV!A2:F2
```

Data rows include both normalized header/value pairs and the raw row values in the extracted representation. The header row is itself citeable evidence.

### XLSX / XLSM

Excel workbooks are opened in read-only mode and streamed row-by-row. Each non-empty row receives a locator such as:

```text
sheet:Awards!A12:F12
```

Proofline opens workbooks with `data_only=False`: formulas are preserved as source expressions and are **not evaluated**. This avoids silently replacing what the workbook contains with locally recomputed values.

### JSON / XML / text

Text-like source files are preserved as logical record evidence with UTF-8 decoding and quality assessment. Original bytes remain available in Bronze regardless of the derived text representation.

## Review queue

`proofline review` lists evidence whose **preferred** extraction is below the requested threshold.

A later forced extraction that performs worse does not push a page back into review if a better retained attempt already exists. Conversely, all low-quality attempts remain available for audit.

## Scale behavior

CSV and XLSX extraction iterate rows rather than materializing the entire workbook into memory. This is necessary for the large-record use case Proofline targets.

The current ingest API still persists one evidence/extraction record at a time; future performance work may batch SQLite writes without changing evidence IDs or extraction semantics.

## Current limits

M2 intentionally does not yet provide:

- handwriting-specific VLM extraction
- table reconstruction from scanned PDFs
- layout geometry / bounding boxes
- image-region evidence extraction
- audio transcription
- factual verification of extracted statements

Those can be added as new extraction producers without changing the Bronze/Silver identity model.
