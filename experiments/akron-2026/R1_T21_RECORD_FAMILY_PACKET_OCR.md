# R1.T21 — Raw Silver OCR Receipt for Publisher-Linked Packet

## Purpose

Freeze the raw OCR result for the single unique Bronze packet in the T21 `PC-2025-80-CU` publisher-backed record chronology **before contextual interpretation**.

This receipt is deliberately narrower than a document audit. It preserves acquisition identity, OCR accounting, page-level extraction provenance, quality measurements, and text hashes. It does **not** reproduce or interpret the OCR text in Git.

## Frozen lineage

The preceding T21 evolution stage established 24 distinct publisher source identities that collapse to one byte-identical Bronze PDF. The deterministic OCR representative was the first identity in that already-frozen ordered population:

- meeting: `668`
- item: `46485`
- publish: `100240`
- source URI SHA-256: `a107c2c3331a4f6f6511b7031dcbef193b92d638692580e904d87b0068f454cc`

Before packet acquisition, workflow run `32528744848` reproduced the canonical Akron publisher graph and proved the frozen publisher relations and representative identity.

The reacquired representative reproduced the exact frozen Bronze artifact:

- artifact: `artifact:87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a`
- SHA-256: `87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a`
- bytes: **1,151,866**
- pages: **3**

## Raw OCR result

Existing bounded OCR machinery was used unchanged:

- backend: `pymupdf_tesseract_ocr`
- language: `eng`
- DPI: `200`
- progressive quality floor: `0.70`

Measured result:

- candidates: **3**
- attempted: **3**
- added: **3**
- skipped: **0**
- failed: **0**
- preferred OCR pages: **3/3**
- nonblank preferred pages: **3/3**
- pages meeting the existing quality floor: **3/3**
- aggregate characters: **3,259**
- aggregate lines: **182**

Each preferred page measured quality `1.0`. That is an extraction-quality measurement, not a claim that every OCR token is factually or typographically correct.

Page text is pinned by SHA-256 rather than copied into this receipt:

1. page 1 — `0cb8d94d8ac4b452f9e9af627a150cd755b39d278ebe2848048dffeb79539b98`
2. page 2 — `5f92672868553054c3cb376fa6f7948cc0c429bad878000b0b1df808bc4a73cd`
3. page 3 — `ca95e84f7ab01d9fc2cf7d2065757c89900649f48e0fea71a267a2b3fb71b25e`

Page-metadata signature:

`57842c8f8c211193011580e5d78a7448aad77cedec06f771f6464865a9f87a32`

## Canonical run receipt

- workflow run: `32528744848`
- job: `96916303071`
- head: `979299502a4a8b209865b5e4d1e29150d14276a1`
- harness-introduction commit: `7f3e4e76e7ca502193ae02f6e0c8079ac9cdf23e`
- artifact: `9463263931`
- artifact digest: `sha256:6c7a8d418663728b3fb3263d46fd1cf8233b7184e9d7a3ab3d751d808aae9274`
- raw `packet-ocr.json` SHA-256: `d806ada4f1ea2848b1f8f14193459881d6f590e2a0f7f7172eff574e5fe6648f`

## Provenance reuse

The Silver text was extracted once from the content-addressed Bronze artifact. It can therefore support all 24 publisher source lineages without pretending those 24 source identities are one source.

No new `SourceRelation` or authoritative `SourceFamily` was created.

## Interpretation boundary

At this receipt boundary:

- OCR text has **not** been read contextually;
- packet content has **not** been interpreted;
- no event identity has been assigned;
- no meeting occurrence has been asserted;
- no outcome has been assigned;
- no detector has been authorized;
- no lead has been emitted.

Disposition remains **Unknown**.

The next stage may inspect the already-frozen OCR text contextually. Any interpretation must be a new, later artifact/commit and must preserve the page/extraction hashes above. The broader record-family search should continue through publisher-proven edges rather than by weakening relation authority.
