# R1.T21 terminal-record candidate boundary

## Purpose

After the frozen agenda-status sequence in PR #94, T21 still has no authoritative terminal disposition for `PC-2025-80-CU`. The next stage needs a mechanically bounded way to identify records that deserve terminal-disposition review without allowing search results, agenda disappearance, status words, or vote arithmetic to assign an outcome automatically.

This slice introduces `proofline-numbered-vote-record-candidate/v1`.

## Candidate contract

A v1 candidate requires both:

1. a publisher text line beginning with an explicit numbered legislative instrument such as `ORDINANCE NO. 44-2026` or `RESOLUTION NO. 45-2026`; and
2. an explicit `Vote: A-B` record before the next numbered instrument.

The extractor preserves the exact evidence identity, instrument type/number/year, record text, and observed vote counts.

## Fail-closed behavior

The following do **not** become terminal-record candidates in v1:

- unnumbered pending legislation;
- a recurring `TIME`, `REFERRED`, or hearing agenda status;
- words such as `passed`, `approved`, `denied`, or `withdrawn` in arbitrary prose;
- disappearance from a later agenda;
- a numbered instrument with no explicit vote in the same bounded record;
- a free-form narrative mention of an ordinance number and vote;
- a future publisher agenda timestamp.

## Authority boundary

A candidate is a review target, not an outcome.

`terminal_outcome_assigned` is always `false` in v1. The extractor does not infer passage or failure from vote arithmetic, does not prove meeting occurrence, and does not connect a numbered instrument to `PC-2025-80-CU` through semantic similarity.

A later T21 stage must separately prove that a candidate record is the same legislation using exact publisher-backed identifiers/text relationships before any disposition claim can be evaluated.

## Current T21 state

The frozen #94 sequence remains the governing chronology: one `referred` placement followed by 23 `time` placements, with the September 14 publisher row after the August 24 observation boundary. That future row is scheduling metadata only.

Disposition remains `Unknown`.

## Next bounded stage

After this primitive is green and merged:

1. apply candidate extraction only to canonical publisher evidence;
2. derive exact mechanical relationships between candidate records and the Eastwood legislation using stable identifiers and/or exact title/address text;
3. freeze any candidate population before human or machine disposition interpretation;
4. if no qualifying record exists, preserve `Unknown` rather than treating the empty candidate set as evidence of non-passage, denial, or withdrawal.
