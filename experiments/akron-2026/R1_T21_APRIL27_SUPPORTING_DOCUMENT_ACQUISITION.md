# R1.T21 April 27 Supporting-Document Acquisition Receipt

## Purpose

Freeze the raw, content-free Bronze inventory produced from the previously frozen 20-document April 27, 2026 publisher expansion set before any of those supporting documents are read contextually.

## Merge chronology

The merge sequence did not contaminate the acquisition measurement.

- PR #87 merged at **2026-08-22 00:19:06 -04:00** as `3adf7934c8848fe4d86d7b7f3b6ce4399535cbbc`.
- PR #88 merged 24 seconds later at **2026-08-22 00:19:30 -04:00** as `07b9b864aa795e440d8a8f1dfe423406406b47cb`.
- The canonical acquisition run had already completed successfully at **2026-08-21 22:34:28 -04:00**, approximately 1 hour 45 minutes before either merge.

The frozen pre-acquisition selection and evaluator therefore existed before first content opening, and the raw measurement completed before the code was merged.

## Frozen selection

- parent meeting: `682`
- parent item: `47559`
- selected sources: **20**
- selection signature: `0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d`
- selection commit: `5c1bbe37ace4ff5eaa00aa601183975bd52e036a`

## Canonical acquisition evidence

- workflow run: `32532934705`
- job: `96928413041`
- run head: `d83b64bfc45225370091bac75c74b9fc38da7094`
- workflow artifact: `9464651696`
- artifact digest: `sha256:00a65ee433acc0f9906011467952d25c26ce31614582e9420dd89d43bcaaf9f6`
- raw `acquisition.json` SHA-256: `012242bc20fbd07b1e70fdf58bc0b7a95b24e926d33f472fbc730eb004d53f07`

## Raw inventory

All 20 frozen publisher identities were acquired.

- requested: **20**
- available: **20**
- unavailable: **0**
- unique Bronze artifacts: **20**
- duplicate Bronze artifact groups: **0**
- PDF artifacts: **20**
- total pages: **88**
- native nonblank pages: **47**
- native pages below the existing 0.70 quality floor: **41**

The 41 low-quality pages are concentrated in four artifacts. A later OCR stage may select those four artifacts mechanically using only the frozen rule `native_low_quality_page_count > 0`. That selection is a representation-quality decision, not a contextual or semantic one.

## Interpretation boundary

No supporting-document text is embedded in this receipt. Raw publisher link text and source URIs remain hashed. The acquisition stage does not interpret document content and does not assert event identity, meeting/hearing occurrence, outcome, wrongdoing, anomaly, detector authority, or a lead.

Disposition remains **Unknown**.

## Next

Freeze the four-artifact / 41-page OCR target set from this receipt before running OCR. After complete Silver recovery is frozen, contextual reading of the 20-document family can begin as a separate audit stage.
