# Proofline: Provenance-First Retrieval Across Heterogeneous Municipal Public-Record Systems

**Joseph JM Walker**  
ORCID: 0009-0005-5099-807X

> **Publication status:** Draft research report. Not yet published. Results reported here are bounded to the frozen Canton and Akron benchmark artifacts identified below. This manuscript intentionally excludes the still-open Akron T21 terminal-disposition investigation.

## Abstract

Public records are often technically available yet difficult to reconstruct as evidence because relevant material is distributed across publisher-specific meeting systems, revisions, attachments, minutes, notices, legislation databases, and later records. Retrieval quality alone is therefore insufficient: a research system must also preserve which source authorized an evidence unit, which transformations produced it, and which conclusions remain unearned.

This report evaluates Proofline, a provenance-first public-record research system, on two municipal publisher stacks with materially different evidence boundaries. The first canonical Canton, Ohio benchmark contains 42 frozen cases (37 positive cases and 5 negative controls). The first Akron, Ohio transfer benchmark contains 37 frozen cases (32 positive cases, 5 negative controls, and 54 explicit positive evidence targets). In both experiments, benchmark targets were frozen before retrieval scoring and bound to canonical source identity, an exact evidence locator, and artifact identity. At evaluation depth k=10, both frozen suites produced expectation accuracy 1.0, target recall 1.0, negative-control accuracy 1.0, provenance validity 1.0, and zero unresolved targets. The Akron transfer required a new publisher acquisition adapter and a different canonical evidence boundary, but did not require a source-specific retrieval implementation.

These measurements do not establish universal retrieval completeness, corruption detection, or semantic adequacy. They support a narrower result: within the two frozen test populations, Proofline preserved exact evidence provenance while deterministic retrieval and evaluation contracts transferred across heterogeneous municipal publishing systems. Because neither benchmark exposed a repeatable deterministic retrieval failure class, semantic/vector retrieval remained deferred under the project's complexity gate. A separate Canton R0 case also demonstrates the system's human-governance boundary: a machine-selected recurrence candidate received an ordinary administrative explanation and was dispositioned `explained` rather than being rewarded for sounding suspicious.

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

This report does not claim that provenance, document retrieval, government-information retrieval, or evidence traceability are novel concepts. Prior work establishes provenance models for web resources and scientific/digital evidence, retrieval systems for e-government material, and modern document-retrieval benchmarks. The contribution evaluated here is narrower: a provenance-first retrieval architecture is tested through benchmark identities frozen before scoring, then transferred across two materially different municipal publisher stacks while preserving explicit source authority and bounded claims.

### 1.1 Research questions

**RQ1 — Bounded retrieval and provenance.** Within a frozen canonical municipal-record benchmark, can Proofline recover the expected evidence targets while preserving exact provenance and negative controls?

**RQ2 — Transfer.** Can the same evidence, retrieval, provenance-resolution, and evaluation contracts transfer to a second municipal publisher stack whose canonical evidence boundary differs materially from the first?

**RQ3 — Complexity gate.** Do the frozen benchmark populations expose a repeatable deterministic retrieval failure class that justifies adding semantic/vector retrieval?

A fourth concern is methodological rather than performance-oriented: can the system surface a candidate for human review without turning recurrence, missing information, or procedural facts into an accusation or terminal conclusion?

## 2. Related Work

### 2.1 Provenance and reproducibility

The W3C PROV family defines a general model for describing provenance and mechanisms for obtaining provenance records associated with web resources. Proofline does not replace such standards; its concern is application-level enforcement of source roles and backward traceability from derived observations to evidence units and preserved source artifacts.

Digital-evidence research has likewise treated provenance as a reproducibility problem. Levine and Liberatore's DEX work described tool-independent provenance records that preserve the transformations from raw evidence to investigative products, enabling reproduction and comparison across tools. Proofline adopts a related separation between preserved source material and derived products, but applies it to evolving public-record publisher systems rather than forensic disk evidence.

### 2.2 Government-document and municipal-record retrieval

Research on e-government information retrieval predates modern generative systems. FRED explored faceted retrieval over government web content and documented metadata heterogeneity across government pages. Work on large born-digital government publication collections has also emphasized the difficulty of searching and analyzing large PDF corpora at scale.

Recent work is particularly relevant to municipal records. MiNER evaluates metadata extraction from municipal meeting minutes and reports reduced cross-municipality generalization, highlighting the danger of assuming that one municipality's document conventions transfer directly to another. Proofline addresses a related but distinct layer: it permits publisher-specific acquisition and evidence boundaries while testing whether downstream provenance and retrieval contracts transfer unchanged.

### 2.3 Evidence attribution and evolving authoritative documents

Recent retrieval research increasingly distinguishes answer quality from evidence attribution. ProvenAI, for example, separates answer correctness, citation fidelity, and document influence. Other recent work on epistemic policies for multi-source retrieval systems separates evidence-state diagnosis from response action. TIDE demonstrates that temporally evolving official documents create version-resolution failures even when authoritative text is available.

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

Machine processing does not determine misconduct, significance, motive, or publication. Human review is explicit and append-only. A review receipt is bound to the exact deterministic lead identity so that a later evidence or detector change cannot silently inherit an earlier human judgment.

## 4. Experimental Design

## 4.1 Canton R0: end-to-end methodological validation

R0 asked whether Proofline could ingest a real public-record corpus, normalize it into reproducible evidence, surface at least one non-preselected pattern, and preserve a benign human explanation rather than rewarding suspicious-sounding output.

The machine-selected candidate involved a recurring municipal matter with stable structured anchors and changing deadline facts. Human inspection found an ordinary administrative explanation: the records described sequential expenditure-deadline amendments. The lead was dispositioned `explained`. R0 therefore serves here as a governance demonstration, not as evidence of wrongdoing-detection accuracy.

## 4.2 Canton R1 canonical retrieval benchmark

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

The suite included lexical/entity, exact-money, exact-date, publisher-native identifier, and negative-control cases. Retrieval results were not consulted before the benchmark was frozen.

## 4.3 Akron transfer benchmark

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

## 4.4 Metrics

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

An earlier Canton benchmark had included volatile discovery/support targets and produced unresolved targets. The canonical policy corrected the benchmark definition rather than changing retrieval results after scoring: positive targets were restricted to canonical evidence. The canonical benchmark was then frozen and scored as a distinct version.

### 5.2 Akron transfer result

All 37 Akron cases were scorable. All 32 positive cases hit, all 54 explicit positive targets were recovered, and all 5 negative controls passed. Provenance validity was 1.0 and no unresolved frozen target remained.

The relevant transfer result is architectural rather than merely numerical. Akron required new source-specific acquisition logic and a different evidence-unit boundary, but the same Bronze/Silver storage, extraction, lexical retrieval, structured retrieval, evidence-target resolution, provenance, and evaluation contracts were used downstream. The transfer did not require a source-specific retrieval implementation.

## 6. Complexity-Gate Decision

The project had considered semantic/vector retrieval as a possible addition. The decision rule was evidence-driven: probabilistic retrieval complexity would be introduced when a frozen real-corpus benchmark exposed a repeatable failure class that deterministic retrieval/index improvements could not adequately address.

Neither the Canton canonical benchmark nor the Akron transfer benchmark produced such a failure. Semantic/vector retrieval therefore remained deferred.

This is **not** evidence that semantic retrieval is unnecessary in public-record research. It establishes only that these two frozen benchmark populations did not justify the added complexity.

## 7. Governance Result: Preserving a Benign Explanation

The R0 case is methodologically important because systems intended for investigative support can be biased by their own success criteria. If a benchmark implicitly rewards suspicious-sounding findings, benign explanations become false negatives.

Proofline instead treated the first machine-selected recurrence as a successful system test even though human review found an ordinary administrative explanation. The immutable candidate remained preserved, the human review was recorded separately, and the derived current disposition became `explained`.

This design does not prove fairness or eliminate investigator bias. It does show that the software's success criterion does not require an adverse interpretation.

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

This does not eliminate researcher degrees of freedom during benchmark construction, but it makes one critical boundary inspectable: the scored target set existed before the score.

## 9. Threats to Validity

### 9.1 External validity

The evaluation covers two Ohio municipalities and two publisher stacks. These are not a representative sample of all municipal, state, federal, or international public-record systems. The results cannot be generalized to arbitrary government archives without further transfer studies.

### 9.2 Benchmark construction

The benchmark cases were curated under documented source-role and question-quality rules rather than drawn as a probability sample of all possible information needs. Perfect bounded scores therefore should not be interpreted as population-level retrieval accuracy.

### 9.3 Publisher drift

Public websites change. URLs, templates, transport behavior, and source populations may differ from the frozen experiment state. The preserved hashes and receipts establish what was measured, not that a future live run will encounter identical publisher behavior.

### 9.4 Metric scope

Provenance validity measures whether returned targets resolve through the expected evidence/provenance contracts. It does not establish that every extraction is semantically perfect or that a human interpretation based on the evidence is correct.

### 9.5 Absence of a deterministic failure class

The semantic-retrieval complexity decision is conditional on the tested cases. A future benchmark may expose synonymy, paraphrase, multilingual, OCR, or conceptual-retrieval failures that justify semantic retrieval.

### 9.6 Human governance

The R0 `explained` disposition is a single reviewed case. It demonstrates that benign disposition is structurally supported; it does not establish inter-rater reliability, fairness, or calibrated investigative judgment.

## 10. Claims Not Made

This report does **not** claim that:

- Proofline detects corruption or misconduct;
- a recurrence, missing record, search non-finding, recommendation, vote arithmetic, or procedural status implies wrongdoing or terminal disposition;
- the benchmark scores represent universal retrieval completeness;
- deterministic retrieval is generally superior to semantic/vector retrieval;
- the two municipalities are representative of public-record systems generally;
- provenance guarantees truth;
- publisher-linked records imply causality;
- machine-selected candidates are newsworthy; or
- the still-open Akron T21 matter has a terminal outcome.

## 11. Reproducibility and Artifact Map

The authoritative research artifacts for this report are already version-controlled in the Proofline repository.

### Canton canonical benchmark

- `experiments/canton-2026/retrieval/R1_CANONICAL_V2_FREEZE.md`
- `experiments/canton-2026/retrieval/R1_CANONICAL_V2_SCORE.md`
- `experiments/canton-2026/retrieval/r1-canonical-v2-unscored.json`
- exact score artifacts under the corresponding score directory

### Akron transfer benchmark

- `experiments/akron-2026/retrieval/R1_TRANSFER_V1_FREEZE.md`
- `experiments/akron-2026/retrieval/R1_TRANSFER_V1_SCORE.md`
- `experiments/akron-2026/retrieval/r1-transfer-v1-unscored.json.gz`
- `experiments/akron-2026/retrieval/r1-transfer-v1-score-core.tar.gz`

A publication deposit should include a research-owned measurement package with a manifest of exact SHA-256 identities. Third-party municipal source bytes should not be republished automatically; source URLs, source roles, hashes, and retrieval provenance can be preserved while redistribution rights are reviewed separately.

## 12. Conclusion

Across two frozen municipal public-record benchmark populations, Proofline recovered the expected canonical evidence while preserving exact provenance and negative controls. The second experiment materially changed the publisher and canonical evidence boundary, yet the downstream retrieval, provenance-resolution, and evaluation contracts transferred without a source-specific retrieval implementation.

The result is intentionally bounded. It does not establish universal retrieval accuracy or automated investigative truth. It demonstrates that provenance can be treated as an executable constraint on retrieval research rather than a citation layer added after analysis, and that benchmark targets can be frozen with exact evidence identity before scoring. Within the tested populations, deterministic retrieval was sufficient to meet the frozen targets, so additional semantic/vector complexity remained unearned.

The next research step is not to broaden this result rhetorically, but to repeat the transfer test on additional publisher stacks and allow future frozen benchmarks to determine where the present architecture fails.

## References

1. W3C. *PROV-AQ: Provenance Access and Query.* W3C Recommendation, 2013. https://www.w3.org/TR/prov-aq/
2. Levine, B. N., & Liberatore, M. “DEX: Digital evidence provenance supporting reproducibility and comparison.” *Digital Investigation* 6(S), 2009, S48–S56. DOI: 10.1016/j.diin.2009.06.011.
3. Freund, L., Jinglewski, M., & Kessler, K. “Introducing FRED: Faceted retrieval of e-government documents.” *Proceedings of the American Society for Information Science and Technology* 49(1), 2012/2013. DOI: 10.1002/meet.14504901310.
4. Lee, B. C. G., & Owens, T. “Grappling with the Scale of Born-Digital Government Publications: Toward Pipelines for Processing and Searching Millions of PDFs.” arXiv:2112.02471, 2021.
5. Batista, R., Cunha, L. F., Silvano, P., Guimarães, N., Jorge, A., Amorim, E., & Campos, R. “MiNER: A Two-Stage Pipeline for Metadata Extraction from Municipal Meeting Minutes.” arXiv:2602.00316, 2026.
6. Faizan, M., & Alharthi, D. “ProvenAI: Provenance-Native Traces of Evidence in Generated Answers.” arXiv:2606.26449, 2026.
7. Kinalioglu, I. H. “EPRAG: An epistemic policy framework for action selection in multi-source enterprise retrieval-augmented generation.” *Knowledge-Based Systems*, 2026. DOI: 10.1016/j.knosys.2026.116929.
8. Sobhani, M. E., et al. “Time Present and Time Past: Benchmarking Large Language Models on Temporally Evolving Document Understanding.” arXiv:2608.08512, 2026.
