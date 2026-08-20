# R1.T6 Akron Supporting-Document Contract — Probe Result

This record documents the bounded source-contract experiment that tested whether Akron OnBase `Supporting Documents` links can be promoted into auditable Proofline evidence sources.

## Provenance

- PR: `#61`
- final probe workflow: `32305176642`
- final probe artifact: `r1-akron-attachment-probe` (`9384697136`)
- final artifact digest: `sha256:d7922d6588a9a1f19bdc6673710734e2bd65d22bbaccbdcf3e5a2fe3a2f75358`
- final probe head: `a0c07740ea5638b4cf3a52269ec360a4eaff1b8c`
- base canonical Akron manifest SHA-256: `375fe1ca8843509adfef9616fc2d7fb65353ee8866e168d1c89218e9e5f8c9d0`

The probe rebuilt the existing production Akron corpus first. It did not alter the OnBase production adapter, sweep document IDs, guess attachment URLs, or consult attachment contents when selecting the sample.

## Publisher-declared relationship population

From **1,475** canonical OnBase agenda-item records:

- **1,472** contained the visible `Supporting Documents` section;
- **1,472** contained at least one qualifying attachment anchor;
- **2,327** explicit item → attachment relationships were discovered;
- **2,327** unique attachment URIs were discovered;
- **2,327/2,327** were on the same official OnBase instance;
- **0** external attachment URIs were present.

Every discovered attachment URI had the same contract shape:

- path under `/OnBaseAgendaOnline/Documents/DownloadFile/...pdf`;
- `documentType=1`;
- `meetingId=<publisher value>`;
- `itemId=<publisher value>`;
- `publishId=<publisher value>`;
- `isSection=False`;
- `isAttachment=True`.

Every discovered path ended in `.pdf`, but the probe did **not** treat the extension as proof of media type.

Each relationship retains the exact parent agenda-item source URI and parent artifact SHA-256 that published the link.

## First transport hop: `DownloadFile`

The deterministic sample contained at most eight same-instance attachment URIs, preferring distinct meetings and selected only from publisher-declared identities.

All **8/8** initial `DownloadFile` requests returned:

- HTTP 200;
- `text/html; charset=utf-8`;
- exactly **1,454 bytes**;
- identical wrapper SHA-256:
  `c043c33c100c5c96632d9e514681cf24cb0c0a445e8916034f7e31b11c08e093`;
- no redirect.

The preserved wrapper explicitly contains first-party JavaScript that, when the current URL does not already contain `DownloadFileBytes`, replaces `DownloadFile` with `DownloadFileBytes` to perform the actual download.

Therefore the HTML response is a publisher transport wrapper, not the attachment bytes themselves.

## Second transport hop: publisher-declared `DownloadFileBytes`

The final probe followed only that explicit wrapper declaration. It did not infer a new document ID, filename, host, or query value.

Result:

- **8/8** wrappers exposed the declared byte transport;
- **8/8** byte-transport requests succeeded;
- **0** payload errors;
- **8/8** responses declared `application/pdf`;
- **8/8** began with `%PDF-` magic bytes;
- **8/8** remained on the same official host;
- **8/8** were complete within the 4 MiB sample cap;
- every sample produced a distinct content SHA-256.

Sample payload receipts:

| # | meeting | item | bytes | SHA-256 |
|---:|---:|---:|---:|---|
| 1 | 662 | 46012 | 1,302,550 | `4c5cea19f103675557d9abef93c4ba1f0b7a9d89aa66ff5e55bff0b93f6efe02` |
| 2 | 665 | 46253 | 1,366,837 | `446060594dc237b9b3373d0b059c5534a8776dcc0087f4826b71d3c24e00fb2e` |
| 3 | 683 | 47645 | 1,629,584 | `6e73c6d666c599b6b74b3100d2906735a99406463914f8e37a4bc008358b67ad` |
| 4 | 690 | 48268 | 189,636 | `7f3a9b77d6b385f8eec3b610af88a6dab0700bdef99793bbfb5ec82e13844b64` |
| 5 | 666 | 46355 | 715,326 | `9e1a310c95b0dcb3969bf081f03eecc48f1d9d14db42e60ab9f2e36dae1af688` |
| 6 | 670 | 46649 | 112,561 | `5a359bb75403a4a376a72184b046314bef1bbce6ecd7350cde272e8adc99abf2` |
| 7 | 693 | 48617 | 144,422 | `a33432ab4950069ed043d26b430a5a68f7e769f1154bf59b62b0e9a8b949a2ca` |
| 8 | 696 | 48826 | 498,363 | `1762e848222403119af1a5519af3c1eb2b9cca033e23613d5840553e1d1c7699` |

## Source identity / transport decision

The stable evidence-source identity should remain the exact publisher-declared `DownloadFile` URI found in the canonical item page.

The `DownloadFileBytes` URI should be treated as **transport**, not a separately discovered source identity. Production code should obtain it only after validating that the official `DownloadFile` wrapper explicitly declares the transformation for that exact URL.

This mirrors Proofline's existing CivicClerk separation between stable logical source identity and temporary/derived transport.

## Relationship provenance decision

A promoted attachment should retain an explicit source relation:

```text
attachment source
  -- supporting_document_of -->
canonical agenda-item source
```

The relation evidence must be the exact preserved parent agenda-item artifact that published the attachment anchor. Text similarity, filename similarity, shared IDs, or a successful byte fetch alone are insufficient to manufacture this relation.

## T6 conclusion

**Promotion is justified.**

The Akron OnBase instance exposes a high-coverage, publisher-declared, same-instance attachment relationship and a deterministic two-stage transport contract:

```text
canonical agenda item HTML
→ explicit Supporting Documents anchor
→ stable DownloadFile source URI
→ first-party HTML wrapper
→ wrapper-declared DownloadFileBytes transport
→ validated PDF bytes
```

This does not prove every future OnBase publisher uses the same contract. A generic production adapter must validate the contract at runtime and fail closed when the wrapper declaration, host relationship, query shape, or returned bytes do not match the proven boundary.

## Next stage

T7 should promote this contract into production without importing Akron-specific hostnames or semantic assumptions:

1. derive attachment resources only from preserved canonical OnBase item HTML;
2. retain the `DownloadFile` URI as stable source identity;
3. add a bounded `onbase_download_bytes` watcher transport strategy that validates the first-party wrapper declaration before fetching bytes;
4. require PDF magic-byte validation for these proven attachment resources;
5. reuse ordinary Bronze/Silver ingestion;
6. add append-only `supporting_document_of` source relations backed by the exact parent item artifact;
7. validate deterministic discovery and unchanged reruns on the live Akron corpus.
