# Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems

**Joseph JM Walker**  
ORCID: 0009-0005-5099-807X  
Paper DOI: https://doi.org/10.5281/zenodo.22698012  
Companion measurement-package DOI: https://doi.org/10.5281/zenodo.22697967  
Version: 1.0 (archival release candidate)  
License: CC BY 4.0

> **Publication status:** Archival release candidate. The Zenodo DOIs above are reserved but the records are not yet published. Results are bounded to the frozen Canton and Akron benchmark artifacts identified below. This manuscript intentionally excludes the still-open Akron T21 terminal-disposition investigation. Intended manuscript license at deposit: CC BY 4.0.

## Abstract

Public records are often technically available yet difficult to reconstruct as evidence because relevant material is distributed across publisher-specific meeting systems, revisions, attachments, minutes, notices, legislation databases, and later records. Retrieval quality alone is therefore insufficient: a research system must also preserve which source authorized an evidence unit, which transformations produced it, and which conclusions remain unearned.

This report evaluates Proofline, a provenance-first public-record research system, on two municipal publisher stacks with materially different evidence boundaries. The first canonical Canton, Ohio benchmark contains 42 frozen cases (37 positive cases and 5 negative controls). The first Akron, Ohio transfer benchmark contains 37 frozen cases (32 positive cases, 5 negative controls, and 54 explicit positive evidence targets). In both experiments, benchmark targets were frozen before retrieval scoring and bound to canonical source identity, an exact evidence locator, and artifact identity. At evaluation depth k=10, both frozen suites produced expectation accuracy 1.0, target recall 1.0, negative-control accuracy 1.0, provenance validity 1.0, and zero unresolved targets. The Akron transfer required a new publisher acquisition adapter and a different canonical evidence boundary, but did not require a source-specific retrieval implementation.

These measurements do not establish universal retrieval completeness, corruption detection, or semantic adequacy. They support a narrower result: within the two frozen test populations, Proofline preserved exact evidence provenance while deterministic retrieval and evaluation contracts transferred across heterogeneous municipal publishing systems. Because neither benchmark exposed a repeatable deterministic retrieval failure class, semantic/vector retrieval remained deferred under the project's complexity gate. A separate Canton R0 case demonstrates an additional governance property: when a segmentation correction changed the deterministic identity of a machine-selected lead, the prior human review remained preserved but did not silently transfer; a second review receipt explicitly re-affirmed the benign `explained` disposition for the corrected lead.

## 1. Introduction

Public access to government information is not equivalent to usable evidence access. A municipal matter may appear in one system as an agenda item, in another as a revised PDF, in another as minutes or a notice, and later under a different publisher-native identifier. A search result can therefore be textually relevant while still being evidentially ambiguous: the retrieved item may be a discovery page rather than a canonical record, an outdated version, a transport URL rather than a stable source identity, or a document whose relationship to another record has not been established by the publisher.

Proofline was built around the proposition that public-record research requires two simultaneous capabilities:

1. **retrieval**, so a researcher can find the relevant evidence; and
2. **authority-preserving provenance**, so the system can show exactly why a retrieved or derived statement is permitted by the public record.

The governing architecture separates three layers:

- **Bronze:** preserved source artifacts and retrieval history;
- **Silver:** stable, human-inspectable evidence units with exact locators and extraction provenance; and
- **Gold:** regenerable analysis, observations, candidate leads, and other derived outputs.

The operating rule is:

> **Gold may be wrong. Silver must be reproducible. Bronze must remain immutable.**

This report does not claim that provenance, document retrieval, government-information retrieval, or evidence traceability are novel concepts. The W3C PROV family provides general provenance models and access mechanisms [1]; digital-forensics work such as DEX addresses reproducible transformation lineage [2]; government-information retrieval and large-scale government-document processing are established research areas [3,4]; and recent work addresses municipal metadata extraction, evidence attribution, epistemic action selection, and temporally evolving authoritative documents [5-8]. The contribution evaluated here is narrower: a provenance-first retrieval architecture is tested through benchmark identities frozen before scoring, then transferred across two materially different municipal publisher stacks while preserving explicit source authority and bounded claims. A separate R0 lineage demonstrates that human review authority is bound to an exact deterministic lead identity rather than silently inherited when that identity changes.

### 1.1 Research questions

**RQ1 - Bounded retrieval and provenance.** Within a frozen canonical municipal-record benchmark, can Proofline recover the expected evidence targets while preserving exact provenance and negative controls?

**RQ2 - Transfer.** Can the same evidence, retrieval, provenance-resolution, and evaluation contracts transfer to a second municipal publisher stack whose canonical evidence boundary differs materially from the first?

**RQ3 - Complexity gate.** Do the frozen benchmark populations expose a repeatable deterministic retrieval failure class that justifies adding semantic/vector retrieval?

A fourth concern is methodological rather than performance-oriented: can the system surface a candidate for human review without turning recurrence, missing information, or procedural facts into an accusation or terminal conclusion, and can that human judgment remain explicitly bound to the evidence-derived identity it reviewed?

## 2. Related Work

### 2.1 Provenance and reproducibility

The W3C PROV family defines a general model for describing provenance and mechanisms for obtaining provenance records associated with web resources [1]. Proofline does not replace such standards; its concern is application-level enforcement of source roles and backward traceability from derived observations to evidence units and preserved source artifacts.

Digital-evidence research has likewise treated provenance as a reproducibility problem. Levine and Liberatore's DEX work described tool-independent provenance records that preserve transformations from raw evidence to investigative products, enabling reproduction and comparison across tools [2]. Proofline adopts a related separation between preserved source material and derived products, but applies it to evolving public-record publisher systems rather than forensic disk evidence.

### 2.2 Government-document and municipal-record retrieval

Research on e-government information retrieval predates modern generative systems. FRED explored faceted retrieval over government web content and documented metadata heterogeneity across government pages [3]. Lee and Owens likewise examined the practical challenge of processing and searching very large born-digital government PDF collections [4].

Recent work is particularly relevant to municipal records. MiNER evaluates metadata extraction from municipal meeting minutes and reports reduced cross-municipality generalization, highlighting the danger of assuming that one municipality's document conventions transfer directly to another [5]. Proofline addresses a related but distinct layer: it permits publisher-specific acquisition and evidence boundaries while testing whether downstream provenance and retrieval contracts transfer unchanged.

### 2.3 Evidence attribution and evolving authoritative documents

Recent retrieval research increasingly distinguishes answer quality from evidence attribution. ProvenAI separates answer correctness, citation fidelity, and document influence [6]. EPRAG separates evidence-state diagnosis from response action in multi-source enterprise retrieval [7]. TIDE demonstrates that temporally evolving official documents create version-resolution failures even when authoritative text is available [8].

These results reinforce a design assumption of Proofline: a retrieved record should not automatically become an authorized conclusion. Proofline therefore keeps retrieval, source authority, publisher-backed relationships, derived observations, and human disposition as separate operations.

## 3. System Architecture

### 3.1 Bronze: source preservation

Bronze preserves original publisher artifacts and retrieval history, including source URI, retrieval timestamp, SHA-256 identity, publisher-native identifiers where available, and source/version relationships. Content-addressed artifact identity prevents repeated acquisition from silently rewriting what was previously analyzed.

A critical distinction is made between **stable source identity** and **transport location**. Some publishers issue temporary or signed download URLs. Proofline may use those URLs to retrieve bytes while preserving a stable publisher route or identifier as the source identity.

### 3.2 Silver: evidence units

Silver represents the human-inspectable unit that can support a claim or retrieval target: a PDF page, spreadsheet row, agenda item, or other logical record. Each unit records its source artifact, exact locator, extracted text, extraction method/version, and quality metadata.

The evidence boundary is publisher-dependent. Canton meeting evidence required agenda-item segmentation within larger PDFs. Akron's OnBase system supplied agenda-item HTML pages whose publisher-defined boundary already represented one logical record, so additional segmentation was rejected rather than added merely for consistency.

### 3.3 Gold: derived analysis

Gold contains regenerable observations, relationships, chronology, comparisons, candidate leads, and other derived material. A Gold statement must trace backward through Silver evidence to Bronze source material. When a comparison depends on a relationship between records, the relationship itself must be authorized by preserved publisher evidence rather than inferred from name similarity alone.

Gold is deliberately weaker in authority than Silver. A derived candidate can be wrong without corrupting the source record.

### 3.4 Human review boundary

Machine processing does not determine misconduct, significance, motive, or publication. Human review is explicit and append-only. A durable review receipt is bound to the exact deterministic `lead_id` it names. If an evidence, segmentation, detector, or packaging change produces a different lead identity, the earlier human judgment remains historical evidence but is not automatically inherited by the new lead.

This rule distinguishes **preservation of prior judgment** from **authorization of current judgment**. The R0 case below exercised that distinction in practice.

## 4. Experimental Design

### 4.1 Canton R0: end-to-end methodological and authority validation

R0 asked whether Proofline could ingest a real public-record corpus, normalize it into reproducible evidence, surface at least one non-preselected pattern, and preserve a benign human explanation rather than rewarding suspicious-sounding output.

The machine-selected candidate involved a recurring municipal matter with stable structured anchors and changing deadline facts. Human inspection found an ordinary administrative explanation: the underlying Board of Control records described sequential expenditure-deadline amendments. The first deterministic lead was therefore reviewed as `explained`, with an explicit note that no misconduct was inferred.

A subsequent segmentation correction changed the deterministic lead identity while leaving the substantive underlying matter and ordinary explanation intact. Proofline did not silently transfer the first human review to the new identity. The original receipt remained preserved as historical review evidence, and a second human review receipt explicitly re-affirmed `explained` for the corrected lead after inspection.

The two durable receipts are:

- initial lead: `lead:3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c`, reviewed `explained` at 2026-08-19T17:14:00+00:00;
- corrected lead: `lead:ab70a8e49322a7662e31fa1331926d34358a549527b293427c96ade005206a51`, explicitly re-reviewed `explained` at 2026-08-19T18:56:00+00:00 after the segmentation correction changed the deterministic identity.

R0 therefore serves here as a governance and authority-lineage demonstration, not as evidence of wrongdoing-detection accuracy. It shows that a benign outcome can count as a successful system test and that human authority does not silently cross an evidence-derived identity change.

### 4.2 Canton R1 canonical retrieval benchmark

The canonical Canton benchmark was frozen before scoring.

Frozen composition:

- 42 cases total;
- 37 positive cases;
- 5 deterministic negative controls;
- canonical evidence only as positive targets;
- exact source URI;
- exact page locator;
- exact artifact SHA-256;
- evaluation depth k=10.

Frozen benchmark SHA-256:

`aee4d01b3b7fa505d008296e226bbaff43af6022c025ad9764f14b412e9cfbbc`

The suite included lexical/entity, exact-money, exact-date, publisher-native identifier, and negative-control cases. Retrieval results for this canonical-v2 suite were not consulted before that suite was frozen.

### 4.3 Akron transfer benchmark

Akron intentionally changed the source conditions. Instead of Canton-style PDF/page canonical evidence, Akron's Hyland OnBase stack exposed publisher-supplied agenda-item HTML whose logical boundary was already atomic.

The acquisition path was established through bounded publisher-declared routes rather than numeric-ID sweeping. A generic OnBase adapter then acquired canonical agenda-item sources while preserving discovery and agenda-tree pages as support provenance rather than positive benchmark targets.

The first Akron transfer benchmark was selected and frozen without building or consulting the lexical retrieval index.

Frozen composition:

- 37 cases total;
- 32 positive cases;
- 5 deterministic negative controls;
- 54 explicit positive evidence targets;
- canonical source role;
- exact `record:1` locator;
- exact artifact SHA-256;
- evaluation depth k=10.

Frozen decompressed benchmark SHA-256:

`fc9829b5f2221b7bd5d8eca992700d05e784e1c2f3a08760d862b1ef65ecb681`

Unlike Canton, the canonical Akron population contained no explicit currency evidence at benchmark-selection time. The benchmark therefore contained no positive money case, while retaining a deterministic money negative control. This absence was treated as a measured property of the source population rather than filled synthetically to create symmetrical coverage.

### 4.4 Metrics

The frozen benchmark reports use bounded metrics defined by the Proofline evaluation harness:

- expectation accuracy;
- positive hit rate at k=10;
- explicit target recall at k=10;
- negative-control accuracy;
- provenance validity;
- unresolved target count; and
- retrieval failure classes.

These metrics evaluate the frozen target population. They do not measure universal completeness, truth of arbitrary derived claims, or end-user investigative performance.

## 5. Results

| Measure | Canton canonical v2 | Akron transfer v1 |
| --- | ---: | ---: |
| Cases | 42 | 37 |
| Positive cases | 37 | 32 |
| Negative controls | 5 | 5 |
| Explicit positive targets | bounded canonical targets | 54 |
| Scorable cases | 42/42 | 37/37 |
| Expectation accuracy | 1.0 | 1.0 |
| Positive hit rate @10 | 1.0 | 1.0 |
| Target recall @10 | 1.0 | 1.0 (54/54 explicit targets) |
| Negative-control accuracy | 1.0 | 1.0 (5/5) |
| Provenance validity | 1.0 | 1.0 |
| Unresolved targets | 0 | 0 |
| Retrieval failure classes | none | none |

### 5.1 Canton result

All 42 canonical Canton cases were scorable. The benchmark produced no deterministic retrieval miss, partial target recall, unexpected negative-control result, or provenance failure.

An earlier Canton benchmark had included volatile discovery/support targets and produced unresolved targets. That earlier failure informed a canonical-source target policy. The policy restricted positive targets to canonical evidence; a distinct canonical-v2 benchmark was then constructed, inspected while unscored, frozen, and only afterward given its first retrieval score. The v2 freeze therefore prevents post-score editing of the v2 target set; it does not erase or conceal the fact that its benchmark policy was developed after diagnostic evidence from the earlier suite.

### 5.2 Akron transfer result

All 37 Akron cases were scorable. All 32 positive cases hit, all 54 explicit positive targets were recovered, and all 5 negative controls passed. Provenance validity was 1.0 and no unresolved frozen target remained.

The relevant transfer result is architectural rather than merely numerical. Akron required new source-specific acquisition logic and a different evidence-unit boundary, but the same Bronze/Silver storage, extraction, lexical retrieval, structured retrieval, evidence-target resolution, provenance, and evaluation contracts were used downstream. The transfer did not require a source-specific retrieval implementation.

### 5.3 Publication-artifact integrity verification

For this release candidate, a publication-specific verifier independently recomputed the SHA-256 identities of the durable Git-resident benchmark and score artifacts named by the historical receipts. The verifier checks the Canton frozen benchmark, raw pool, four durable score outputs, the Akron deterministic gzip benchmark, its decompressed JSON identity, the deterministic Akron score-core archive, and the five score files inside that archive.

GitHub Actions run `34528385659` completed successfully on the publication branch, including the `Verify durable artifact hashes` step. This closes the publication-specific question of whether the Git-resident durable measurement bytes still match the historical SHA-256 receipts. It does not re-run the original live municipal acquisition or replace the historical scoring workflows.

## 6. Complexity-Gate Decision

The project had considered semantic/vector retrieval as a possible addition. The decision rule was evidence-driven: probabilistic retrieval complexity would be introduced when a frozen real-corpus benchmark exposed a repeatable failure class that deterministic retrieval/index improvements could not adequately address.

Neither the Canton canonical benchmark nor the Akron transfer benchmark produced such a failure. Semantic/vector retrieval therefore remained deferred.

This is **not** evidence that semantic retrieval is unnecessary in public-record research. It establishes only that these two frozen benchmark populations did not justify the added complexity.

## 7. Governance Result: Human Authority Does Not Silently Transfer

The R0 case is methodologically important because systems intended for investigative support can be biased by their own success criteria. If a benchmark implicitly rewards suspicious-sounding findings, benign explanations become false negatives. A second risk appears after a human has reviewed a machine-generated candidate: later evidence or processing changes can make it tempting to reuse the prior judgment without checking whether the object being judged is still the same object.

Proofline treated the first machine-selected recurrence as a successful system test even though human review found an ordinary administrative explanation. The immutable candidate remained preserved, the human review was recorded separately, and the derived current disposition became `explained`.

When the subsequent segmentation correction changed the deterministic lead identity, the prior review remained in history but no longer authorized the corrected lead. The corrected lead required a new review receipt. The same reviewer inspected the corrected derivation and explicitly re-affirmed `explained`, preserving both the continuity of the substantive interpretation and the discontinuity of authority between the two deterministic identities.

This sequence provides a concrete authority-lineage result:

**evidence/segmentation change -> deterministic identity change -> prior human authority stops for the corrected object -> new human review -> prior judgment remains historically preserved.**

The case does not prove fairness, calibrated judgment, or inter-rater reliability. It demonstrates a narrower property: Proofline's review machinery can prevent a recorded human conclusion from silently migrating to a changed evidence-derived object, while still preserving the prior judgment for audit.

## 8. Discussion

### 8.1 What transferred

The experiments support a bounded transfer claim for:

- immutable/content-addressed artifact handling;
- stable evidence identities;
- extraction history and quality handling;
- lexical retrieval;
- structured retrieval;
- publisher-native identifier lookup;
- evidence-target resolution;
- provenance validation; and
- benchmark scoring/reporting.

### 8.2 What did not transfer by assumption

The experiments also demonstrate the importance of refusing false uniformity. The following Canton-specific assumptions were not imported into Akron merely because they already existed:

- Canton agenda segmentation;
- Canton matter-key semantics;
- Canton financial-role policy; and
- Canton recurrence/detector configuration.

Akron directly invalidated one symmetry assumption: canonical agenda-item pages were already atomic, so additional segmentation would have weakened rather than improved provenance.

### 8.3 Why frozen-before-score identity matters

A benchmark can become deceptively easy if target definitions are adjusted after retrieval results are known. Proofline therefore preserves benchmark freeze receipts, exact artifact identities, and score artifacts as separate historical objects. A later correction creates a new benchmark version rather than rewriting the old result.

This does not eliminate researcher degrees of freedom during benchmark construction, nor does it make a later benchmark independent of lessons learned from earlier experiments. It makes one narrower boundary inspectable: the scored target set for a particular frozen version existed before that version's score.

### 8.4 Execution witness versus archival research record

The original scoring workflows were useful execution witnesses, but CI artifact retention is not an archival strategy. During preparation of this paper, at least one historical GitHub Actions artifact referenced by a score receipt had already expired. The durable benchmark and score materials, however, had been promoted into Git history, and the publication-specific verifier successfully reproduced their recorded SHA-256 identities from those durable copies.

The resulting publication model is therefore deliberately layered:

- **GitHub Actions:** execution witness;
- **Git:** durable experiment record and version history;
- **Zenodo:** frozen archival publication snapshot with persistent identifier;
- **ORCID:** author identity and output index.

## 9. Threats to Validity

### 9.1 External validity

The evaluation covers two Ohio municipalities and two publisher stacks. These are not a representative sample of all municipal, state, federal, or international public-record systems. The results cannot be generalized to arbitrary government archives without further transfer studies.

### 9.2 Benchmark construction and query distribution

The benchmark cases were curated under documented source-role and question-quality rules rather than drawn as a probability sample of all possible information needs. Lexical cases are source-grounded entity/phrase queries drawn from the corpus rather than a representative sample of natural-language user searches. Perfect bounded scores therefore should not be interpreted as population-level natural-language retrieval accuracy or evidence that arbitrary user queries would obtain the same result.

The Canton canonical-v2 suite was also not the project's first benchmark attempt. An earlier Canton suite exposed volatile discovery/support targets and produced unresolved/unscorable cases. That diagnostic informed the canonical target-source policy used to construct v2. Canonical v2 was then frozen before its own first score. Accordingly, the freeze demonstrates that the v2 target set was not revised in response to the v2 score; it does not demonstrate that v2's design was independent of earlier retrieval and benchmark-development experience.

### 9.3 Publisher drift

Public websites change. URLs, templates, transport behavior, and source populations may differ from the frozen experiment state. The preserved hashes and receipts establish what was measured, not that a future live run will encounter identical publisher behavior.

### 9.4 Metric scope

Provenance validity measures whether returned targets resolve through the expected evidence/provenance contracts. It does not establish that every extraction is semantically perfect or that a human interpretation based on the evidence is correct.

### 9.5 Absence of a deterministic failure class

The semantic-retrieval complexity decision is conditional on the tested cases. A future benchmark may expose synonymy, paraphrase, multilingual, OCR, or conceptual-retrieval failures that justify semantic retrieval.

### 9.6 Human governance

The R0 governance evidence concerns one substantive municipal matter and two linked review receipts produced by the same reviewer because a segmentation correction changed the deterministic lead identity. The sequence demonstrates non-transfer and explicit renewal of human authority across that identity change, but it provides no inter-rater evidence and does not establish fairness, calibrated investigative judgment, or general human-review reliability.

### 9.7 Archival reconstruction versus live re-execution

The publication-specific hash verifier establishes that the durable Git-resident research artifacts match the identities recorded by the historical freeze/score receipts. It does not prove that a fresh live crawl of the current municipal publisher interfaces would reproduce the same source corpus, because publisher state can drift over time. The archival claim and the live-reexecution claim are intentionally separate.

## 10. Claims Not Made

This report does **not** claim that:

- Proofline detects corruption or misconduct;
- a recurrence, missing record, search non-finding, recommendation, vote arithmetic, or procedural status implies wrongdoing or terminal disposition;
- the benchmark scores represent universal retrieval completeness;
- the curated/source-grounded benchmark represents natural-language user-query performance generally;
- deterministic retrieval is generally superior to semantic/vector retrieval;
- the two municipalities are representative of public-record systems generally;
- provenance guarantees truth;
- publisher-linked records imply causality;
- machine-selected candidates are newsworthy;
- one same-reviewer R0 lineage establishes inter-rater reliability or fairness; or
- the still-open Akron T21 matter has a terminal outcome.

## 11. Reproducibility and Artifact Map

The authoritative research artifacts for this report are version-controlled in the Proofline repository and will be frozen into a separate research-owned measurement-package deposit.

### 11.1 Canton canonical benchmark

- `experiments/canton-2026/retrieval/R1_CANONICAL_V2_FREEZE.md`
- `experiments/canton-2026/retrieval/R1_CANONICAL_V2_SCORE.md`
- `experiments/canton-2026/retrieval/r1-canonical-v2-unscored.json`
- `experiments/canton-2026/retrieval/r1-canonical-v2-raw-pool.json`
- exact score artifacts under `experiments/canton-2026/retrieval/r1-canonical-v2-score/`

### 11.2 Akron transfer benchmark

- `experiments/akron-2026/retrieval/R1_TRANSFER_V1_FREEZE.md`
- `experiments/akron-2026/retrieval/R1_TRANSFER_V1_SCORE.md`
- `experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz`
- `experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz`

### 11.3 R0 review authority lineage

- `docs/REVIEW_RECORDS.md`
- `experiments/canton-2026/reviews/lead-3619b8454017086bc9815781f50b5f9360526bdea77c9f862483f8363cd2025c.json`
- `experiments/canton-2026/reviews/lead-ab70a8e49322a7662e31fa1331926d34358a549527b293427c96ade005206a51.json`
- `research/publications/proofline-r0-r1/R0_REVIEW_LINEAGE.md`

### 11.4 Publication verification

- `research/publications/proofline-r0-r1/ARTIFACT_MANIFEST.md`
- `research/publications/proofline-r0-r1/CLAIM_EVIDENCE_MATRIX.md`
- `research/publications/proofline-r0-r1/verify_artifacts.py`
- `.github/workflows/publication-proofline-r0-r1.yml`
- successful publication-verifier workflow run: `34528385659`

The companion measurement package is reserved at https://doi.org/10.5281/zenodo.22697967. The first measurement-package deposit is intentionally limited to research-owned artifacts. Third-party municipal source bytes are excluded by default. The package preserves source URLs, source roles, evidence locators, hashes, and other provenance needed to identify the evaluated sources without asserting a new license over third-party material. Proofline software is also outside the license scope of this paper and measurement package.

## 12. Conclusion

Across two frozen municipal public-record benchmark populations, Proofline recovered the expected canonical evidence while preserving exact provenance and negative controls. The second experiment materially changed the publisher and canonical evidence boundary, yet the downstream retrieval, provenance-resolution, and evaluation contracts transferred without a source-specific retrieval implementation. A separate R0 authority-lineage sequence showed that when a segmentation correction changed a deterministic lead identity, the prior human judgment remained preserved but was not silently inherited by the corrected lead.

The result is intentionally bounded. It does not establish universal retrieval accuracy or automated investigative truth. It demonstrates that provenance can be treated as an executable constraint on retrieval research rather than a citation layer added after analysis; benchmark targets can be frozen with exact evidence identity before scoring; and human review authority can be made conditional on the exact deterministic object that was reviewed. Within the tested populations, deterministic retrieval was sufficient to meet the frozen targets, so additional semantic/vector complexity remained unearned.

The next research step is not to broaden this result rhetorically, but to repeat the transfer test on additional publisher stacks and allow future frozen benchmarks to determine where the present architecture fails.

## References

1. Klyne, G., & Groth, P. (eds.). *PROV-AQ: Provenance Access and Query.* W3C Working Group Note, 30 April 2013. https://www.w3.org/TR/prov-aq/
2. Levine, B. N., & Liberatore, M. "DEX: Digital Evidence Provenance Supporting Reproducibility and Comparison." *Digital Investigation* 6, Supplement (September 2009): S48-S56. https://doi.org/10.1016/j.diin.2009.06.011
3. Freund, L., Jinglewski, M., & Kessler, K. "Introducing FRED: Faceted Retrieval of E-Government Documents." *Proceedings of the American Society for Information Science and Technology* 49(1): 1-4 (2012; first published online 24 January 2013). https://doi.org/10.1002/meet.14504901310
4. Lee, B. C. G., & Owens, T. "Grappling with the Scale of Born-Digital Government Publications: Toward Pipelines for Processing and Searching Millions of PDFs." *International Journal of Digital Humanities* 3 (2022): 91-114. https://doi.org/10.1007/s42803-022-00042-x
5. Batista, R., Cunha, L. F., Silvano, P., Guimaraes, N., Jorge, A., Amorim, E., & Campos, R. "MiNER: A Two-Stage Pipeline for Metadata Extraction from Municipal Meeting Minutes." *Advances in Information Retrieval. ECIR 2026*, Lecture Notes in Computer Science 16484 (2026). https://doi.org/10.1007/978-3-032-21300-6_33 ; arXiv:2602.00316.
6. Faizan, M., & Alharthi, D. "ProvenAI: Provenance-Native Traces of Evidence in Generated Answers." arXiv:2606.26449 (2026). https://doi.org/10.48550/arXiv.2606.26449
7. Kinalioglu, I. H. "EPRAG: An Epistemic Policy Framework for Action Selection in Multi-Source Enterprise Retrieval-Augmented Generation." *Knowledge-Based Systems* (2026). https://doi.org/10.1016/j.knosys.2026.116929
8. Sobhani, M. E., Sayeedi, M. F. A., Chowdhury, F. H., Arefeen, M. A., Sadeque, F., Bari, M. F., & Shatabda, S. "Time Present and Time Past: Benchmarking Large Language Models on Temporally Evolving Document Understanding." arXiv:2608.08512 (2026).
