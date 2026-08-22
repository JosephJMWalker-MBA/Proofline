# R1.T21 April 27 Acquisition Receipt Correction

## What failed

The first low-quality OCR workflow (`32594286157`) failed closed at the pre-OCR lineage proof for `publish_id=102590` with `source URI hash drifted`.

No selected OCR source was reacquired and no OCR was run in that attempt.

## Root cause

The canonical acquisition measurement was sound. Its raw `acquisition.json` has SHA-256 `012242bc20fbd07b1e70fdf58bc0b7a95b24e926d33f472fbc730eb004d53f07`, and all 20 document identities in that file match the pre-acquisition frozen selection exactly.

The defect was introduced later while manually assembling the v1 Git receipt in PR #89: document-row metadata became mis-associated beginning at `publish_id=102590`. The v1 receipt therefore must not be used for downstream source-identity, Bronze-artifact, byte-size, or page-metadata values.

This correction does **not** change:

- the canonical workflow run;
- the 20-source publisher selection;
- any acquired Bronze bytes;
- the global inventory counts (20 artifacts / 88 pages / 41 low-quality pages);
- the representation-only selection rule; or
- the four publish IDs selected for OCR (`102589`, `102590`, `102593`, `102597`).

## Corrected receipt

`r1_t21_april27_supporting_document_acquisition_summary_v2.json` is derived directly from the frozen canonical acquisition artifact and records:

- 20/20 identity agreement with the original publisher selection;
- canonical document-row signature `4a577f1ef2f9efbb09e531aea1ed4404d8fb205b1d86afe49ca624f935aba8eb`;
- corrected four-artifact OCR-frontier metadata; and
- corrected OCR-frontier signature `cd86100e5a6ff2d54159ae0437db95f79bdcfed24a054c1ed330792f3c07c357`.

The historical v1 receipt remains in Git history for chronology but is explicitly superseded for downstream metadata use.

## Scientific boundary

The failure occurred before reacquisition/OCR. No supporting-document content was contextually read as part of diagnosing or correcting the receipt. Disposition remains **Unknown**.
