# Proofline R0/R1 Publication Checklist

> **Status:** Release-candidate publication checklist. A checked item means the evidence for that gate has been inspected; it does not imply that the manuscript has been deposited or peer reviewed.

## 0. Scope freeze

- [x] First publication is a **research report / preprint**, not the first software DOI.
- [x] Working title frozen: **Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems**.
- [x] Canton R0 is used only as a human-governance/authority-lineage demonstration.
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
- [x] Bibliography independently verified against W3C, publisher, DOI, and arXiv metadata; durable record in `REFERENCES_VERIFICATION.md`.

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
- [x] Claim-to-receipt matrix created and material empirical claims audited against frozen receipts.
- [x] R0 identity-change/re-review sequence incorporated into Release Candidate 1.
- [x] Bibliography corrected and normalized for Release Candidate 1.
- [x] Author-side editing pass completed for Release Candidate 1.
- [ ] Freeze final title/abstract after external/adversarial review.
- [ ] Insert reserved Zenodo DOI into final archival manuscript.

## 3. Measurement package

- [x] `ARTIFACT_MANIFEST.md` identifies the minimum research-owned evidence package.
- [x] Historical hashes copied from the frozen experiment receipts.
- [x] Publication-specific verifier created for the durable Canton/Akron measurement artifacts.
- [x] Recomputed historical benchmark/score SHA-256 identities match the receipts in CI run `34528385659`.
- [ ] Assemble the exact files intended for the Zenodo measurement deposit.
- [ ] Generate a deterministic measurement-package archive.
- [ ] Generate machine-readable final manifest from the verified deposit files.
- [ ] Compute and record SHA-256 of the final measurement-package archive.
- [ ] Add exact publication repository commit/tag.
- [ ] Add measurement-package README.

## 4. Rights / redistribution

- [x] Do not silently assign an open-source license to Proofline software.
- [x] Do not automatically republish municipal source bytes.
- [x] Manuscript deposit intent: **CC BY 4.0**.
- [x] Research-owned measurement-package deposit intent: **CC BY 4.0**.
- [x] Third-party municipal source bytes excluded from the first measurement deposit by default.
- [x] Where source bytes are not deposited, preserve URL, retrieval context, source role, locator, and hash instead.
- [x] `RIGHTS_DECISION.md` records that the publication license does not license Proofline software.
- [ ] Decide Proofline software license separately before any future software DOI.

## 5. Reproducibility audit

- [x] Historical freeze and score receipt paths resolve in Git.
- [x] Canton frozen benchmark and durable score hashes verified by the publication-specific workflow.
- [x] Akron compressed and decompressed benchmark hashes verified by the publication-specific workflow.
- [x] Durable Akron score-core archive and internal score-file hashes verified by the publication-specific workflow.
- [x] Report numbers checked against exact frozen score receipts rather than README summaries.
- [x] R0 review receipts checked against `docs/REVIEW_RECORDS.md` and the identity-change lineage recorded.
- [x] Ongoing T21 material excluded from the first paper's empirical result.
- [x] Archival hazard documented: historical CI artifacts can expire; Git-resident research artifacts are the durable measurement record.
- [ ] Verify general repository CI and publication-specific verifier on the final release-candidate commit after all publication-file edits.

## 6. External review

- [ ] Technical reader: provenance/reproducibility critique.
- [ ] Information-retrieval reader: benchmark/evaluation critique.
- [ ] Public-records/government-information reader: domain-boundary critique if available.
- [ ] Adversarial read specifically looking for overclaiming from 1.0 bounded scores.
- [ ] Resolve material critiques through visible manuscript revisions; do not silently rewrite frozen experimental records.

## 7. Deposit metadata

Creator:

**Joseph JM Walker**  
ORCID: **0009-0005-5099-807X**

Planned records:

1. **Publication / Preprint** — final research report, CC BY 4.0.
2. **Dataset** — research-owned R0/R1 measurement package, CC BY 4.0.

Related software repository:

`https://github.com/JosephJMWalker-MBA/Proofline`

- [x] Final creator spelling and ORCID.
- [x] Planned resource types.
- [x] Planned abstract/description for deposit.
- [x] Keywords.
- [x] Rights/license boundary.
- [x] Two-record relationship direction documented in `ZENODO_DEPOSIT_PLAN.md`.
- [ ] Reserve publication DOI.
- [ ] Reserve measurement-package DOI.
- [ ] Final publication date.
- [ ] Add reciprocal DOI related identifiers after both are reserved.
- [ ] Funding field, if applicable; otherwise leave absent rather than inventing support.
- [ ] Final version identifier/tag.

## 8. Persistent publication

- [ ] Render and inspect archival PDF with reserved publication DOI embedded.
- [ ] Build and inspect deterministic measurement-package archive.
- [ ] Deposit final report/preprint.
- [ ] Deposit verified measurement package.
- [ ] Inspect both persistent records before treating either DOI as authoritative.
- [ ] Verify title, creator spelling, ORCID, version, abstract, rights/license, and related identifiers.
- [ ] Verify Zenodo pushes both works to ORCID without creating duplicates.
- [ ] Backfill DOI metadata into the publication folder/repository if appropriate.

## 9. Stop conditions

Stop publication if any of the following occurs:

- a reported result cannot be traced to the frozen score artifacts;
- a benchmark digest fails without an explained versioned correction;
- the manuscript implies that 1.0 bounded scores equal universal accuracy;
- an unresolved T21 outcome is described as terminal;
- third-party source material is about to be redistributed outside the explicit rights boundary;
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
