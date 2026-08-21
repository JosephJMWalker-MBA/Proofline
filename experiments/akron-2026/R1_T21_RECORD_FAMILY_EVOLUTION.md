# R1.T21 — Publisher-backed record-family packet evolution

## Purpose

Measure whether the publisher-linked D-14 packet associated with the exact public-record key `PC-2025-80-CU` changed across its repeated Council appearances, without assigning event, outcome, detector, or lead authority.

This stage follows the completed T21 exact-reference probe. The packet population was frozen by source identity before bounded family acquisition. It is a descriptive opened-case experiment, not a blind holdout.

## Frozen selection and method boundary

The exact-reference probe had already established 24 Council meeting appearances for `PC-2025-80-CU`. For each of those 24 parents, publisher evidence exposed exactly one supporting-document relation carrying the same literal case key. Before fetching those 24 packet sources as a bounded family, commit `923f85a06cb0c531d91b0b7bef62f8eb1cf2f9c3` froze:

- 24 `(meeting_id, item_id, publish_id, source_uri_sha256)` identities;
- selection signature `b46265ee254267230fa62dfc6dbc4a537fa608bd5052844fd19ffedb2a320921`;
- packet-evolution evaluator blob;
- explicit-reference implementation blob;
- structured OnBase meeting-metadata serializer blob.

The workflow then required all 24 frozen identities to match exactly one current publisher relation before any selected packet bytes were acquired.

## Canonical run

- workflow run: `32516590296`
- job: `96879483971`
- freeze head: `923f85a06cb0c531d91b0b7bef62f8eb1cf2f9c3`
- artifact: `9459168882`
- artifact digest: `sha256:f0796a3f555ce02a5f584001003a9a7b2da9f23096b70b6b0152b9c0bd5ca8b2`
- raw result SHA-256: `dd747691c0e51827cf75f75075db6e0f09d9cd0388caacd356fa74bd89ecc3ef`
- full repository suite in workflow: **244 passed**
- canonical Akron attachment identity graph: **2,327 sources**, preserved manifest SHA, zero discovery rejections

## Raw result

The 24 distinct publisher packet source identities collapse to **one Bronze artifact**.

- packet source identities: **24**
- unique Bronze artifacts: **1**
- repeated Bronze artifact groups: **1**
- consecutive Bronze changes across the 23 appearance transitions: **0**
- publisher meeting timestamps after the frozen August 21 observation boundary: **1**
- evolution signature: `6dee28ce1d206491032750bc17e675e8410c961b00499f598d5d4dc627c43c48`

Unique packet artifact:

- artifact ID: `artifact:87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a`
- SHA-256: `87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a`
- byte size: **1,151,866**
- media type: `application/pdf`
- pages: **3**
- native nonblank pages: **0**
- native pages below the existing 0.70 quality floor: **3**
- native-text signature: `2d8155eb7a8171a2f0052623256263cc16f1237c2d6a7fb9e91f83d11dd2b63d`

Thus the publisher exposed 24 distinct source identities / publish IDs over the Council chronology, but every one resolved to byte-identical copies of the same three-page PDF.

## Interpretation boundary

This is a source/version result, not yet a semantic result.

It supports saying that the **publisher-linked base D-14 packet bytes did not change across these 24 appearances**. It does not support saying why the matter remained on agendas, whether the same facts were considered each time, whether surrounding written comments or legislation changed, whether any meeting actually occurred solely from publisher scheduling metadata, or what the final disposition was.

The packet has no usable native text on any of its three pages. No OCR or content interpretation was performed in this stage. The next content-recovery step should therefore OCR this **single unique artifact once** and reuse that Silver evidence across its 24 source lineages rather than treating the 24 publisher identities as 24 documents.

## Authority boundary

The raw result preserves:

- `source_relation_created = false`
- `source_family_modified = false`
- `event_identity_assigned = false`
- `meeting_occurrence_asserted = false`
- `outcome_assigned = false`
- `detector_authorized = false`
- `lead_count = null`

Disposition remains **Unknown**.

## Journalism implication

This result narrows the next investigative question. The base petition packet itself is not where documentary evolution occurred: its bytes are invariant across the observed publisher appearances. If the public-record story changes over time, the change must be sought in other evidence surfaces—agenda-item status text, legislation/substitutes, written comments, staff materials, testimony, or other publisher-linked attachments—while retaining provenance for every step.
