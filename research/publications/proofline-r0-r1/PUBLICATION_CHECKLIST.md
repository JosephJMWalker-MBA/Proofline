# Proofline R0/R1 Publication Checklist

> **Status:** Active publication-preparation checklist. A checked item means the evidence for that gate has been inspected; it does not imply that the manuscript has been deposited or peer reviewed.

## 0. Scope freeze

- [x] First publication is a **research report / preprint**, not the first software DOI.
- [x] Working title frozen: **Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems**.
- [x] Canton R0 is used only as a human-governance demonstration.
- [x] Canton canonical R1 and Akron transfer R1 are the empirical core.
- [x] Akron T21 is explicitly excluded from this first paper while its terminal outcome remains unresolved.
- [x] Universal retrieval, corruption detection, wrongdoing detection, causal inference, and semantic-retrieval superiority are outside scope.

## 1. Prior-art / claim boundary

- [x] Provenance standards and prior digital-evidence provenance work identified.
- [x] Prior government-document/e-government retrieval work identified.
- [x] Recent municipal-record extraction work identified.
- [x] Recent evidence-attribution / epistemic retrieval work identified.
- [x] Recent version-aware official-document benchmark work identified.
- [x] `RELATED_WORK_BOUNDARY.md` records the non-novelty boundary and language to avoid.
- [ ] Final bibliography independently verified against publisher/DOI metadata before deposit.

## 2. Manuscript

- [x] First complete manuscript draft created.
- [x] Abstract reports bounded benchmark counts and metrics.
- [x] Research questions stated explicitly.
- [x] Bronze/Silver/Gold authority model described.
- [x] Canton and Akron evidence boundaries distinguished.
- [x] Frozen-before-score protocol described.
- [x] Results table included.
- [x] Complexity-gate decision bounded to observed failures.
- [x] Threats to validity included.
- [x] Claims-not-made section included.
- [x] Reproducibility/artifact map included.
- [ ] Independent claim-to-receipt review line by line.
- [ ] Editing pass for journal/report style after evidence audit.
- [ ] Final title/abstract frozen after review.

## 3. Measurement package

- [x] `ARTIFACT_MANIFEST.md` identifies the minimum research-owned evidence package.
- [x] Historical hashes copied from the frozen experiment receipts.
- [ ] Recompute SHA-256 over every exact file intended for deposit.
- [ ] Compare recomputed hashes with historical receipts.
- [ ] Generate machine-readable final manifest from the verified deposit files.
- [ ] Add exact publication repository commit/tag.
- [ ] Add measurement-package README.

## 4. Rights / redistribution

- [x] Do not silently assign an open-source license to Proofline software.
- [x] Do not automatically republish all municipal source bytes.
- [ ] Decide manuscript rights/license (for example CC BY 4.0, if intentionally chosen by the owner).
- [ ] Decide measurement-package rights/license.
- [ ] Review whether each municipal source-artifact class may appropriately be redistributed.
- [ ] Where source bytes are not deposited, preserve URL, retrieval context, source role, locator, and hash instead.
- [ ] Decide Proofline software license separately before any software DOI.

## 5. Reproducibility audit

- [ ] Verify current repository tests on the exact publication branch/head.
- [ ] Verify the historical freeze and score receipt paths still resolve.
- [ ] Verify the Canton frozen benchmark hash.
- [ ] Verify the Akron compressed and decompressed benchmark hashes.
- [ ] Verify the durable Akron score-core bundle hash.
- [ ] Verify all report numbers against the exact score outputs, not only README summaries.
- [ ] Confirm no ongoing T21 material leaked into the first paper's results.

## 6. External review

- [ ] Technical reader: provenance/reproducibility critique.
- [ ] Information-retrieval reader: benchmark/evaluation critique.
- [ ] Public-records/government-information reader: domain-boundary critique if available.
- [ ] Adversarial read specifically looking for overclaiming from 1.0 bounded scores.
- [ ] Resolve critiques through visible manuscript revisions; do not silently rewrite frozen experimental records.

## 7. Deposit metadata

Creator:

**Joseph JM Walker**  
ORCID: **0009-0005-5099-807X**

Candidate resource type:

**Report / preprint** (final repository/venue taxonomy to be selected at deposit)

Related software:

`https://github.com/JosephJMWalker-MBA/Proofline`

- [ ] Final publication date.
- [ ] Final abstract.
- [ ] Keywords.
- [ ] Rights/license.
- [ ] Related identifiers.
- [ ] Funding field, if applicable; otherwise leave absent rather than inventing support.
- [ ] Version identifier.

## 8. Persistent publication

- [ ] Deposit final report/preprint.
- [ ] Deposit or relate the verified measurement package.
- [ ] Inspect the resulting persistent record before treating the DOI as authoritative.
- [ ] Verify title, creator spelling, ORCID, version, abstract, rights/license, and related identifiers.
- [ ] Add/import the published work to ORCID.
- [ ] Verify the ORCID work record.
- [ ] Backfill DOI into the publication folder/repository if appropriate.

## 9. Stop conditions

Stop publication if any of the following occurs:

- a reported result cannot be traced to the frozen score artifacts;
- a benchmark digest fails without an explained versioned correction;
- the manuscript implies that 1.0 bounded scores equal universal accuracy;
- an unresolved T21 outcome is described as terminal;
- third-party source material is about to be redistributed without an explicit rights decision;
- software is about to be deposited under a license that has not been intentionally selected; or
- external review finds a material claim/evidence mismatch that has not been resolved.

## 10. Definition of done

The first Proofline publication is complete when:

1. the manuscript's empirical sentences trace to frozen evidence;
2. the measurement package has verified identities;
3. rights decisions are explicit;
4. a persistent publication record exists and has been inspected;
5. the work is correctly linked to ORCID; and
6. the repository records the publication without rewriting the historical experiments.
