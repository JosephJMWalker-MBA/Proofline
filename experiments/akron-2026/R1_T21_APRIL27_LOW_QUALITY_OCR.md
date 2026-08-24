# R1.T21 April 27 Low-Quality OCR Receipt

## Purpose

Freeze the raw Silver recovery result for the mechanically selected low-native-quality portion of the April 27, 2026 supporting-document family **before contextual reading of those supporting documents**.

This receipt is a representation-recovery result in an already opened case family. It is not a new blind validation and it does not assign documentary meaning, event identity, hearing occurrence, outcome, detector authority, or a lead.

## Preserved correction chronology

The correction history is part of the evidence rather than something to hide.

1. PR #89 froze the content-free 20-document acquisition inventory. The canonical raw acquisition was sound, but the later hand-built v1 receipt mis-associated row metadata beginning at publish ID `102590`.
2. The first OCR attempt failed closed **before OCR** when the publisher-lineage proof rejected the incorrect source-URI hash.
3. Receipt/selection v2 was reconstructed from the unchanged canonical `acquisition.json`. The underlying 20-document acquisition, selected four publish IDs, four Bronze artifacts, 48 source pages, and 41 low-quality pages did not change.
4. Corrected v2 run `32600657882` / job `97098314570` proved the corrected publisher identities and exact Bronze/native profiles and then executed OCR. The wrapper failed afterward because it incorrectly treated `ProgressiveExtractionResult.candidates` as the number of pages actually escalated to OCR. No OCR prose from that failed run was read or uploaded.
5. The existing `ProgressiveExtractor` contract was audited. Its `candidates` field counts all page units presented to the quality gate; `attempted` counts pages actually OCRed; `skipped` counts pages already meeting the threshold.
6. v3 changed only the evaluator accounting contract. The source population, Bronze hashes, OCR backend, threshold, language, DPI, and `force=False` behavior remained unchanged.

## Canonical v3 run

- workflow run: `32681674473`
- job: `97299320376`
- head: `e6fd4fd81bf7f4f017896a98f67c697d552b35e4`
- workflow artifact: `9504466994`
- artifact digest: `sha256:81426a330498c708ae107df63c73fa401a01597d86f80eb38c64b136a41ccd69`
- raw `low-quality-ocr-v3.json` SHA-256: `f7027285870fdec87328d2218391b7b28a13df3f4edf933cddca7a92b169c566`

All dedicated workflow steps succeeded: hash/freeze verification, tests, canonical publisher-graph reconstruction, unchanged four-artifact proof, exact Bronze reacquisition, OCR replay, accounting/authority validation, and artifact upload. The ordinary test, Akron OnBase, and Canton workflows were also green on the same head.

## Frozen population and OCR accounting

The population remains the four artifacts selected only by the pre-existing rule:

`artifact.native_low_quality_page_count > 0`

- selected publish IDs: `102589`, `102590`, `102593`, `102597`
- selected artifacts: **4**
- selected source pages: **48**
- pre-OCR pages below 0.70: **41**
- pages already at/above 0.70: **7**
- corrected selection signature: `cd86100e5a6ff2d54159ae0437db95f79bdcfed24a054c1ed330792f3c07c357`

The canonical v3 progressive result is:

- page units presented (`candidates`): **48**
- OCR attempted: **41**
- native pages skipped: **7**
- OCR extractions added: **41**
- OCR failures: **0**

After preferred-extraction selection:

- preferred OCR pages: **41**
- preferred native pages: **7**
- preferred nonblank pages: **47 / 48**
- preferred pages meeting the 0.70 floor: **47 / 48**

The receipt freezes a SHA-256 for every one of the 48 preferred page texts without embedding their prose. The ordered page-hash-list signature is:

`6e8a2ce042f80bd8127e2595f5efe260823c83c929154ba06cc6e665f20b9677`

## Residual quality exception

One page remains legitimately unresolved rather than being silently repaired:

- publish ID: `102590`
- Bronze SHA-256: `c628216c674093d496d107b2588a42730ef30f1de2ec7657b3c6de313379093e`
- page: **5**
- preferred method: `pymupdf_tesseract_ocr`
- quality: **0.0**
- nonblank: **false**
- text SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty text)
- warning: `OCR text remains below the default review threshold`

This is a representation limitation to carry into contextual audit as an unresolved page. It is not evidence that the source page itself is blank or meaningless.

## Interpretation boundary

At this receipt boundary, supporting-document prose has not been contextually read. The machine receipt includes hashes and extraction metadata, not OCR prose.

The authority boundary remains unchanged:

- no new SourceRelation;
- no SourceFamily mutation;
- no event identity;
- no meeting or hearing occurrence assertion;
- no outcome/disposition assignment;
- no detector authority;
- no lead.

Disposition remains **Unknown**.

## Next

After this receipt is committed and CI is green, contextual audit may begin in the already-frozen publisher order. The audit should use native Silver where adequate, OCR Silver for the four escalated artifacts, and explicitly preserve publish `102590` page 5 as unresolved unless a separately governed representation step later recovers it.
