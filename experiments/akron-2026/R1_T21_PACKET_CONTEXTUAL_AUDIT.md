# R1.T21 — Contextual audit of the frozen D-14 packet

## Boundary

This audit is the **first contextual reading** of the three OCR pages whose hashes and extraction metadata were frozen before reading in PR #86. The OCR receipt is already merged to `main` at `1fc111dbb666049b7b84dae28bacbdf9048ab32e`; its receipt-head replay also completed successfully.

Nothing in this audit changes the Bronze artifact, OCR method, packet selection, publisher relations, SourceFamily, or detector/lead authority.

## What the packet is

The publisher relation labels the record:

`2026 - D-14 - PETITION OF DAVID WALKER FOR A CONDITIONAL USE TO ESTABLISH A TRAINING FACILITY AT 1928 EASTWOOD AVENUE PC-2025-80-CU`

The OCR content is consistent with that publisher description. Page 1 is a City of Akron conditional-use petition for the property at **1928 Eastwood Avenue**. It describes a proposed training use serving the public and first responders and states an estimated total project cost of **$677,000.00**.

The publisher identifies **David Walker** as the petitioner. This audit does not infer ownership, legal status, or any role beyond what the publisher title and petition form support.

## Submitted use and plan

Page 1 describes the proposal as repurposing the Eastwood property into a training facility providing defense education/training for the public, police, fire, and EMS. One OCR word in the phrase naming the existing park is noisy, so the audit does not silently normalize that token.

Page 3 is a sparse, diagrammatic site-plan page. Its OCR includes labels for:

- a reconfigurable first-responder training structure;
- an obstacle course and K9 waypoint-training area;
- a rappel tower;
- an archery range; and
- a proposed training center.

These are **submitted-plan labels only**. They do not establish that the configuration was approved, constructed, funded, or operated.

## Page 2 caution

Page 2 contains the form's filing-fee schedule and handwritten/stamped fields. The OCR produced at least one apparent identifier that is not reliable enough to normalize. It is deliberately excluded from joins and factual case identification.

The strong case identifier comes instead from publisher metadata: **`PC-2025-80-CU`**.

## Relation to the previously audited citizen submission

The earlier citizen submission independently contains the exact planning-case key `PC-2025-80-CU`. The D-14 publisher relation also explicitly contains that exact key.

Under `proofline-explicit-public-record-reference/v1`, that supports an **exact-reference candidate join** between the records. The address at 1928 Eastwood Avenue is corroborating context, not the join rule. This audit does not create a `SourceRelation` or mutate a `SourceFamily` merely because the exact key recurs.

## Repeated packet chronology

The frozen T21 evolution measurement established 24 distinct publisher source identities whose packet bytes are identical. Their publisher agenda timestamps span:

- February 9, 2026 through July 27, 2026 for timestamps at or before the August 21 observation boundary; and
- one additional publisher-scheduled appearance on September 14, 2026, which was still future at the observation boundary.

The repeated packet therefore demonstrates recurrence of the same submitted packet in publisher agenda contexts. It does **not** by itself explain why the item recurred or prove that each scheduled meeting/hearing occurred.

## Provenance-bounded next surface

The canonical publisher graph contains a separate April 27, 2026 ordinance item (`meeting_id=682`, `item_id=47559`) with exactly **20 publisher-declared `supporting_document_of` edges**. Their link labels include:

- Information from Petitioner;
- Legislation;
- Notice of Hearing;
- Written Comments Received;
- Substitute Offered as an Amendment; and
- multiple ordinance-support records, some whose publisher labels mention a March 9 public hearing and substitute amendment.

Those 20 documents were **identified but not content-opened in this audit**. Their contents should be frozen as the next bounded selection before acquisition so later interpretation cannot select only convenient records.

## Authority after contextual reading

This audit changes exactly one important state from the pre-reading receipt: `packet_content_interpreted = true`.

It does **not** assign:

- authoritative event identity;
- meeting occurrence;
- outcome/disposition;
- wrongdoing or anomaly status;
- detector authority; or
- a lead.

Disposition remains **Unknown** until an explicit public record establishes what happened to the conditional-use matter.

## Frozen evidence basis

- Bronze SHA-256: `87e0ab7f1a3bb6f3b0e5a37dc311cfb909cf081d1bfe28297421c294bc00386a`
- canonical OCR run: `32528744848`
- OCR artifact: `9463263931`
- OCR artifact digest: `sha256:6c7a8d418663728b3fb3263d46fd1cf8233b7184e9d7a3ab3d751d808aae9274`
- raw `packet-ocr.json`: `d806ada4f1ea2848b1f8f14193459881d6f590e2a0f7f7172eff574e5fe6648f`
- page 1 text SHA-256: `0cb8d94d8ac4b452f9e9af627a150cd755b39d278ebe2848048dffeb79539b98`
- page 2 text SHA-256: `5f92672868553054c3cb376fa6f7948cc0c429bad878000b0b1df808bc4a73cd`
- page 3 text SHA-256: `ca95e84f7ab01d9fc2cf7d2065757c89900649f48e0fea71a267a2b3fb71b25e`

OCR page-quality scores of 1.0 describe the extractor's quality metric. They are not a guarantee that every handwritten, stamped, or diagrammatic token is correct.
