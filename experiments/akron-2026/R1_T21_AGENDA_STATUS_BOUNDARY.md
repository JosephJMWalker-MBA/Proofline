# R1.T21 — Explicit agenda-status authority boundary

## Purpose

Continue T21 outcome tracing after the frozen April 27 record-family contextual audit without converting recurring agenda placement into a terminal disposition.

The audited family currently establishes substantial chronology and surrounding-record context, but it does **not** establish final passage, denial, withdrawal, or another terminal outcome. The next implementation step therefore needs a smaller primitive: preserve explicit publisher agenda-status labels as procedural observations while refusing to assign outcome authority.

## Method

`proofline-explicit-agenda-status/v1` normalizes only structurally supplied publisher labels with exact anchored patterns.

Initial bounded vocabulary:

- `TIME` -> `time` / `hold`
- `REFERRED` -> `referred` / `referral`
- `FIRST READING AND REFERRED` -> `first_reading_referred` / `referral`
- first-reading/referral labels that explicitly schedule a public hearing -> `first_reading_referred_public_hearing` / `referral`
- `UP FOR PUBLIC HEARING ...` or `TO BE SCHEDULED FOR PUBLIC HEARING ...` -> `public_hearing` / `hearing`
- `NO ITEMS` -> `no_items` / `empty_section`

Every observation carries `terminal_outcome_assigned = false`.

## Fail-closed boundary

Version 1 intentionally does **not** normalize terminal-sounding words such as:

- `PASSED`
- `APPROVED`
- `DENIED`
- `WITHDRAWN`

Those terms can occur in many contexts and require a separately governed terminal-outcome method with stronger structural and provenance requirements. Likewise, arbitrary prose containing words such as `time` or `referred` is not accepted as a publisher status label.

The caller remains responsible for proving the structural association between a publisher status heading and a specific agenda item. This primitive does not infer that association from proximity or text similarity.

## T21 interpretation boundary

For `PC-2025-80-CU`, recurring `TIME` placement is evidence that the publisher repeatedly presented the matter under a procedural hold/status heading. It is **not** evidence of:

- approval or denial;
- withdrawal;
- why the matter remained under `TIME`;
- whether a meeting occurred merely because an agenda was published;
- whether absence from a later agenda means disposition;
- causation by public comments, applicant requests, staff action, or council action.

Until an explicit terminal record is found and governed, disposition remains `Unknown`.

## Next bounded stage

After this primitive is independently green, wire it into publisher-structured agenda capture and freeze the exact observed status sequence for the planning-case reference. Only after that receipt is frozen should T21 search for and evaluate candidate terminal records.

No detector, lead, anomaly, persuasion, or civic-effectiveness authority is introduced in this stage.
