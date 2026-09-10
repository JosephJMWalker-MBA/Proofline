# Proofline R0/R1 Claim → Evidence Matrix

> **Purpose:** Bind every material empirical claim in the first Proofline publication to the frozen research record. This matrix governs the manuscript; README summaries are convenient orientation but are not sufficient authority when a freeze or score receipt exists.

## Status vocabulary

- **SUPPORTED** — directly supported by a frozen receipt or exact recorded experiment artifact.
- **SUPPORTED / BOUNDED** — supported only with the limitation stated in the manuscript.
- **INTERPRETATION** — reasonable synthesis of supported facts, but not itself a measured result.
- **OPEN** — must be verified before publication.
- **EXCLUDED** — intentionally outside this paper.

---

## Core claims

| ID | Manuscript claim | Primary authority | Status | Publication constraint |
| --- | --- | --- | --- | --- |
| C01 | Canton canonical benchmark was frozen before retrieval scoring. | `experiments/canton-2026/retrieval/R1_CANONICAL_V2_FREEZE.md` | SUPPORTED | Preserve the exact frozen benchmark identity. |
| C02 | Canton canonical benchmark contains 42 cases: 37 positive and 5 negative controls. | `R1_CANONICAL_V2_FREEZE.md`; `R1_CANONICAL_V2_SCORE.md` | SUPPORTED | Do not imply probability sampling. |
| C03 | Canton positive targets are restricted to canonical sources and bound to exact source URI, page locator, and artifact SHA-256. | `R1_CANONICAL_V2_FREEZE.md` | SUPPORTED | “Canonical” is defined by the frozen source policy, not universal authority. |
| C04 | Canton evaluation depth is k=10. | `R1_CANONICAL_V2_SCORE.md` | SUPPORTED | Keep `@10` on hit/recall claims. |
| C05 | Canton: 42/42 scorable; expectation accuracy 1.0; positive hit rate @10 1.0; target recall @10 1.0; negative accuracy 1.0; provenance validity 1.0; unresolved targets 0; no failure classes. | `R1_CANONICAL_V2_SCORE.md` | SUPPORTED / BOUNDED | Must say this is the frozen canonical benchmark population, not universal retrieval accuracy. |
| C06 | Earlier Canton unresolved targets were associated with volatile discovery/support targets; canonical v2 removed that benchmark-target class rather than repairing the scored result in place. | `R1_CANONICAL_V2_SCORE.md`; `R1_CANONICAL_V2_FREEZE.md` | SUPPORTED / BOUNDED | Phrase as support for the benchmark-target-volatility diagnosis, not proof of sole causality. |
| C07 | Akron canonical evidence boundary differs materially from Canton: publisher-supplied agenda-item HTML is atomic at `record:1`, while Canton requires PDF/page evidence and source-profile segmentation. | `experiments/akron-2026/README.md` T3/T5; `R1_TRANSFER_V1_SCORE.md` | SUPPORTED | Do not imply all OnBase deployments behave identically. |
| C08 | Akron benchmark was selected/frozen without consulting retrieval results or building/consulting the lexical retrieval index. | `R1_TRANSFER_V1_FREEZE.md` | SUPPORTED | Preserve the retrieval-blind wording. |
| C09 | Akron benchmark contains 37 cases, 32 positive cases, 5 negative controls, and 54 explicit positive evidence targets. | `R1_TRANSFER_V1_FREEZE.md`; `R1_TRANSFER_V1_SCORE.md` | SUPPORTED | Maintain distinction between cases and targets. |
| C10 | Akron positive targets are bound to canonical source role, locator `record:1`, and exact artifact SHA-256. | `R1_TRANSFER_V1_FREEZE.md` | SUPPORTED | Keep “canonical under the frozen source policy.” |
| C11 | Akron had no positive money case because the frozen canonical population contained no explicit currency evidence; the negative money control remained. | `R1_TRANSFER_V1_FREEZE.md`; `R1_TRANSFER_V1_SCORE.md` | SUPPORTED | This is a property of the frozen corpus, not of Akron records generally. |
| C12 | Akron evaluation depth is k=10. | `R1_TRANSFER_V1_SCORE.md` | SUPPORTED | Keep `@10` qualification. |
| C13 | Akron: 37/37 scorable; 32/32 positive cases hit; 54/54 explicit positive targets recovered; 5/5 negative controls passed; provenance validity 1.0; unresolved targets 0; retrieval failures 0. | `R1_TRANSFER_V1_SCORE.md` | SUPPORTED / BOUNDED | Must not be presented as universal completeness. |
| C14 | Akron required source-specific acquisition infrastructure but downstream Bronze/Silver storage, extraction, lexical/structured retrieval, evidence-target resolution, and evaluation contracts transferred. | `R1_TRANSFER_V1_SCORE.md`; `experiments/akron-2026/README.md` Transfer conclusion | SUPPORTED / BOUNDED | Limit claim to the tested Canton→Akron transfer. |
| C15 | No source-specific retrieval implementation was required for the Akron transfer. | `R1_TRANSFER_V1_SCORE.md`; Akron transfer conclusion | SUPPORTED / BOUNDED | Acquisition adapter is source-specific; retrieval layer is the part claimed to transfer. |
| C16 | Neither frozen canonical benchmark exposed a deterministic retrieval failure class requiring semantic/vector retrieval. | `R1_CANONICAL_V2_SCORE.md`; `R1_TRANSFER_V1_SCORE.md` | SUPPORTED / BOUNDED | Say “not justified by these measurements,” never “semantic retrieval is unnecessary.” |

---

## R0 governance claims

| ID | Manuscript claim | Primary authority | Status | Publication constraint |
| --- | --- | --- | --- | --- |
| G01 | Canton R0 surfaced a non-preselected machine candidate from the real corpus. | `experiments/canton-2026/README.md`; `STATUS.md` | SUPPORTED | Do not characterize selection as wrongdoing detection. |
| G02 | The selected candidate involved recurring ECDI / Ordinance 60/2023 / $185,000 CDBG records with changing expenditure-deadline facts. | `experiments/canton-2026/README.md`; `STATUS.md` | SUPPORTED | These are source-local facts and recurrence observations, not evidence of misconduct. |
| G03 | Human review found an ordinary administrative explanation involving sequential deadline amendments. | version-controlled review receipt; `experiments/canton-2026/README.md`; `STATUS.md` | SUPPORTED | Preserve the distinction between machine candidate and human disposition. |
| G04 | The lead was dispositioned `explained`. | review receipt; `experiments/canton-2026/README.md`; `STATUS.md` | SUPPORTED | Do not say “false positive” unless a formal ground-truth framework is later defined. |
| G05 | Human review is bound to exact deterministic lead identity and does not silently transfer when derivation identity changes. | `docs/REVIEW_RECORDS.md`; R0 documentation | SUPPORTED | This is an implementation/governance invariant, not evidence of inter-rater reliability. |
| G06 | R0 demonstrates that a benign explanation is structurally permitted as a successful outcome. | G01–G05 | INTERPRETATION | Do not generalize to fairness or unbiased investigation. |

---

## Architecture claims

| ID | Manuscript claim | Primary authority | Status | Publication constraint |
| --- | --- | --- | --- | --- |
| A01 | Proofline separates Bronze source artifacts, Silver evidence units, and Gold derived analysis. | `README.md`; `ARCHITECTURE.md`; `GOVERNANCE.md` | SUPPORTED | This is Proofline's application model, not a claim to invent provenance layering generally. |
| A02 | Bronze preserves source identity/retrieval history and content-addressed artifact identity. | `ARCHITECTURE.md`; implementation/tests | SUPPORTED | Avoid “immutable” as a cryptographic/tamper-proof claim unless the implementation specifically supports it; manuscript uses immutable/content-addressed in the project sense. |
| A03 | Silver units have exact source locators and extraction provenance. | `ARCHITECTURE.md`; source/extraction docs | SUPPORTED | Exact unit shape remains source-profile dependent. |
| A04 | Gold is derived/regenerable and lower-authority than source evidence. | `README.md`; `GOVERNANCE.md` | SUPPORTED | Present as governance architecture, not truth guarantee. |
| A05 | Publisher-backed relationships authorize comparison where required; name similarity alone is insufficient. | `GOVERNANCE.md`; version/matter-key docs and experiment findings | SUPPORTED | Relationship authorization does not imply causal interpretation. |

---

## Related-work / novelty claims

| ID | Manuscript claim | Authority | Status | Publication constraint |
| --- | --- | --- | --- | --- |
| R01 | Provenance is established prior art; W3C PROV provides a general provenance model/family. | W3C PROV documentation | SUPPORTED | Proofline must not claim invention of provenance. |
| R02 | DEX addressed reproducible digital-evidence provenance and transformation lineage. | Levine & Liberatore, 2009, DOI 10.1016/j.diin.2009.06.011 | SUPPORTED | Distinguish public-record publisher systems from forensic evidence exchange. |
| R03 | E-government/government-document retrieval predates Proofline. | FRED; government-document retrieval literature | SUPPORTED | Avoid “first government retrieval system.” |
| R04 | Recent municipal-record work demonstrates cross-municipality heterogeneity. | MiNER, arXiv:2602.00316 | SUPPORTED / BOUNDED | Do not overstate similarity of task; MiNER focuses metadata extraction. |
| R05 | Recent retrieval work separates answer quality, attribution, authority, or temporal version resolution into distinct concerns. | ProvenAI; EPRAG; TIDE | SUPPORTED / BOUNDED | These are adjacent comparisons, not claimed end-to-end substitutes. |
| R06 | The defensible Proofline contribution is the tested combination of governed canonical evidence identity, publisher-backed authority, frozen-before-score benchmarks, and cross-publisher transfer. | C01–C16 + architecture record | INTERPRETATION | Phrase as “contribution evaluated here,” not proof of novelty. |

---

## Explicitly excluded claims

| ID | Claim | Status | Reason |
| --- | --- | --- | --- |
| X01 | Proofline detects corruption. | EXCLUDED | No such validation target exists. |
| X02 | Proofline detects wrongdoing. | EXCLUDED | Human/editorial interpretation remains outside machine authority. |
| X03 | 1.0 frozen scores imply universal retrieval completeness. | EXCLUDED | Benchmarks are bounded and curated. |
| X04 | Deterministic retrieval is generally superior to semantic/vector retrieval. | EXCLUDED | Only the present complexity gate is supported. |
| X05 | Canton and Akron are representative of municipalities generally. | EXCLUDED | No representative sampling claim. |
| X06 | Provenance establishes truth. | EXCLUDED | Provenance establishes traceability/authority path, not truth. |
| X07 | Akron T21 has a known terminal disposition. | EXCLUDED | Current governed outcome remains `Unknown`; T21 is parked pending authoritative evidence. |
| X08 | Missing records or zero-result searches establish adverse outcomes. | EXCLUDED | Proofline explicitly preserves non-findings as bounded non-findings. |

---

## Open verification before publication

- [ ] Re-open each primary authority file on the final publication commit and verify all numbers.
- [ ] Recompute hashes for the exact benchmark and score-package bytes selected for deposit.
- [ ] Verify bibliography metadata against original publisher/DOI records.
- [ ] Audit every use of “immutable” so it does not imply tamper-proof or cryptographically append-only storage unless supported by the cited subsystem.
- [ ] Confirm manuscript never collapses `case`, `target`, `source`, `artifact`, `evidence unit`, and `lead` into interchangeable terms.
- [ ] Confirm every `1.0` result has an immediate benchmark/scope qualifier.
- [ ] Confirm T21 appears only as excluded/open context, never as completed evidence.

## Merge gate

This publication branch should not be merged merely because CI passes. It becomes merge-ready only when the material manuscript claims above are either **SUPPORTED**, **SUPPORTED / BOUNDED**, or explicitly marked **INTERPRETATION**, and all **OPEN** items required for a repository-level draft have been resolved.
