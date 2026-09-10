# Zenodo Deposit Plan — Proofline R0/R1

**Status:** DOI-reserved pre-publication plan  
**Date:** 2026-09-10  
**ORCID:** 0009-0005-5099-807X

## Record A — Research report

**Resource type:** Publication / Preprint (or the closest current Zenodo publication subtype available in the deposit UI)  
**Title:** Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems  
**Reserved DOI:** `10.5281/zenodo.22698012`  
**Creator:** Joseph JM Walker  
**ORCID:** 0009-0005-5099-807X  
**License:** CC BY 4.0  
**Files:** final archival PDF; optional plain-text/Markdown source if desired  
**Publication date:** date the Zenodo record is first published

### Description

Proofline is evaluated on two frozen municipal public-record retrieval benchmarks with materially different publisher/evidence boundaries. The Canton canonical benchmark contains 42 cases; the Akron transfer benchmark contains 37 cases with 54 explicit positive evidence targets. Benchmark identities were frozen before scoring. In both bounded populations, target recall, negative-control accuracy, and provenance validity were 1.0, with zero unresolved targets. The Akron transfer required publisher-specific acquisition and a different canonical evidence boundary but no source-specific retrieval implementation. A separate R0 governance case records how human review did not silently transfer when a segmentation correction changed the deterministic lead identity.

The report does not claim universal retrieval completeness, corruption detection, causal inference, or general superiority of deterministic retrieval over semantic/vector retrieval.

### Keywords

- provenance
- public records
- information retrieval
- reproducibility
- municipal records
- evidence governance
- digital government
- benchmark

### DOI sequence

1. Zenodo draft created.
2. DOI reserved: `10.5281/zenodo.22698012`.
3. Insert the reserved DOI into the archival PDF.
4. Add the dataset DOI `10.5281/zenodo.22697967` as **isSupplementedBy**.
5. Upload the final PDF and preview the record.
6. Publish only after the file, title, creator/ORCID, license, description, and related identifiers are verified.

Do not delete the Zenodo draft unless intentionally abandoning the reserved DOI.

## Record B — Measurement package

**Resource type:** Dataset  
**Title:** Proofline R0/R1 Measurement Package: Canton Canonical and Akron Transfer Benchmarks  
**Reserved DOI:** `10.5281/zenodo.22697967`  
**Creator:** Joseph JM Walker  
**ORCID:** 0009-0005-5099-807X  
**License:** CC BY 4.0 for the included research-owned files  
**Files:** one deterministic archive plus its external SHA-256 and machine-readable manifest

### Intended contents

Include research-owned durable artifacts necessary to inspect the reported measurement boundary, such as:

- Canton canonical benchmark and freeze/score receipts;
- Canton research-owned score/evaluation outputs;
- Akron compressed frozen benchmark and freeze/score receipts;
- Akron durable score-core archive;
- `ARTIFACT_MANIFEST.md`;
- `CLAIM_EVIDENCE_MATRIX.md`;
- `R0_REVIEW_LINEAGE.md`;
- the two R0 review receipts;
- publication artifact verifier and its verification receipt/log summary; and
- a top-level measurement-package README describing exclusions and reconstruction paths.

### Default exclusions

Do **not** bundle:

- third-party municipal source bytes;
- Proofline software source as a software publication;
- live mutable state;
- Akron T21 materials that belong to the ongoing investigation rather than this closed R0/R1 publication boundary.

The package may contain source URLs, hashes, locators, and provenance metadata needed to identify/reconstruct the source evidence.

## Related identifiers

The two reserved DOIs are now fixed:

- Record A / paper: `10.5281/zenodo.22698012` identifies Record B / dataset `10.5281/zenodo.22697967` as **isSupplementedBy**.
- Record B / dataset: `10.5281/zenodo.22697967` identifies Record A / paper `10.5281/zenodo.22698012` as **isSupplementTo**.
- The repository URL may be included as a related resource/reference, but the moving repository is not the archival identity of either deposit.

Zenodo's relation vocabulary supports `isSupplementedBy` and `isSupplementTo`; use those exact directional meanings in the Related works fields.

## ORCID

Zenodo is connected to the author’s ORCID. After publication, verify that both records appear as separate works with the correct title, DOI, work/resource type, creator identity, and source provenance. Do not create duplicate manual ORCID entries if Zenodo has already pushed them successfully.

## Final publication gate

Before either record is published:

- the publication-specific hash verifier must pass on the release-candidate Git commit;
- the paper’s bibliography and claims must be verified;
- the PDF must embed reserved paper DOI `10.5281/zenodo.22698012`;
- the PDF should identify companion dataset DOI `10.5281/zenodo.22697967`;
- the measurement archive must have its own deterministic SHA-256 recorded outside the archive;
- Zenodo previews must match `RIGHTS_DECISION.md`; and
- Record A and Record B must link to one another with the correct directional relationship.
