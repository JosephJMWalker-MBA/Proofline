# Related-Work Boundary for the First Proofline Publication

> **Purpose:** Prevent novelty inflation and preserve the exact contribution boundary before submission.

## What is established prior art

The first Proofline paper should **not** claim novelty for any of the following ideas in isolation:

- data or evidence provenance;
- provenance query/access standards;
- reproducible transformation chains from raw evidence to derived products;
- government-document search or e-government retrieval;
- faceted retrieval over government content;
- large-scale retrieval over government PDF corpora;
- metadata extraction from municipal meeting records;
- citation/evidence attribution in retrieval-augmented systems;
- temporal/version-aware reasoning over changing official documents; or
- the general principle that evidence quality and answer quality are distinct.

## Prior work that constrains the manuscript

### W3C PROV family

General provenance standards already provide conceptual and interoperable models for entities, activities, agents, provenance access, and provenance queries.

**Implication for Proofline:** describe the Bronze/Silver/Gold model as an application architecture and authority discipline, not as the invention of provenance.

Reference:

W3C, *PROV-AQ: Provenance Access and Query*, W3C Recommendation, 2013.

### DEX — digital evidence provenance

Levine and Liberatore described a tool-independent provenance representation for recording transformations from raw digital evidence to investigative products so results could be reproduced and compared across tools.

**Implication for Proofline:** do not claim that preserving transformation lineage from source material to investigative products is new. Proofline's contribution must be tied to public-record publisher systems, explicit evidence authority, and the empirical transfer study.

Reference:

Levine, B. N., & Liberatore, M. “DEX: Digital evidence provenance supporting reproducibility and comparison.” *Digital Investigation* 6(S), 2009. DOI: 10.1016/j.diin.2009.06.011.

### FRED — faceted retrieval of e-government documents

FRED explored metadata-driven faceted retrieval across government web content and documented substantial metadata heterogeneity.

**Implication for Proofline:** government-information retrieval is an established research area. Proofline should distinguish itself through source-role governance, exact evidence identity, publisher-backed relationships, and frozen empirical validation.

Reference:

Freund, L., Jinglewski, M., & Kessler, K. “Introducing FRED: Faceted retrieval of e-government documents.” DOI: 10.1002/meet.14504901310.

### Large-scale born-digital government publications

Lee and Owens examined pipelines for searching and analyzing large government PDF collections and emphasized the scale and heterogeneity of born-digital public material.

**Implication for Proofline:** do not claim that government PDFs are uniquely difficult to search. The stronger point is that public-record evidence can be fragmented across changing publisher systems and that retrieval must preserve source authority.

Reference:

Lee, B. C. G., & Owens, T. “Grappling with the Scale of Born-Digital Government Publications: Toward Pipelines for Processing and Searching Millions of PDFs.” arXiv:2112.02471, 2021.

### MiNER — municipal meeting-minute extraction

MiNER studies metadata extraction from municipal meeting minutes and reports reduced cross-municipality generalization.

**Implication for Proofline:** this is useful adjacent evidence that municipality-specific document conventions matter. Proofline should not imply it is the first computational work on municipal meeting records.

Reference:

Batista, R., et al. “MiNER: A Two-Stage Pipeline for Metadata Extraction from Municipal Meeting Minutes.” arXiv:2602.00316, 2026.

### ProvenAI and evidence attribution

Recent RAG work distinguishes answer correctness, citation fidelity, and actual document influence.

**Implication for Proofline:** do not claim novelty for separating retrieval from evidence attribution. Proofline's empirical claim is about canonical evidence identity and provenance-preserving retrieval over public-record systems, without requiring a generative answer layer.

Reference:

Faizan, M., & Alharthi, D. “ProvenAI: Provenance-Native Traces of Evidence in Generated Answers.” arXiv:2606.26449, 2026.

### EPRAG and epistemic action selection

Recent work explicitly models authority, freshness, compatibility, and response policy in multi-source retrieval settings.

**Implication for Proofline:** avoid claiming that abstention or epistemic state separation is unique. Proofline's stronger evidence is its concrete public-record source contracts, authority paths, and historical benchmark receipts.

Reference:

Kinalioglu, I. H. “EPRAG: An epistemic policy framework for action selection in multi-source enterprise retrieval-augmented generation.” *Knowledge-Based Systems*, 2026. DOI: 10.1016/j.knosys.2026.116929.

### TIDE and evolving authoritative documents

TIDE demonstrates that official documents with changing versions create a distinct version-resolution problem and that models can fail to reject non-governing versions.

**Implication for Proofline:** version-aware official-document reasoning is an active research area. Proofline should emphasize publisher-backed version relationships and preserved historical source identity rather than claim discovery of the versioning problem.

Reference:

Sobhani, M. E., et al. “Time Present and Time Past: Benchmarking Large Language Models on Temporally Evolving Document Understanding.” arXiv:2608.08512, 2026.

## The contribution we can defend

The first paper can defend the following narrower contribution, subject to final independent review:

> Proofline operationalizes provenance as a retrieval constraint in municipal public-record research: positive benchmark targets are bound to canonical source roles, exact evidence locators, and artifact identities before scoring; derived relationships require publisher-backed authority; and the same downstream retrieval/provenance/evaluation contracts were exercised across two materially different municipal publisher stacks.

The evidence currently supports four bounded subclaims:

1. **Frozen-before-score evidence identity.** The reported benchmark targets existed in version-controlled form before their first score.
2. **Canonical provenance validity.** Within the frozen Canton and Akron populations, every scored expected target resolved through the governed provenance contracts.
3. **Cross-publisher transfer.** Akron required different publisher acquisition and evidence atomicity but did not require a different downstream retrieval implementation.
4. **Governed non-adverse outcome.** The Canton R0 candidate could be dispositioned `explained` without the system reclassifying a benign explanation as failure.

## Language to avoid

Do not use:

- “first provenance system”;
- “novel provenance architecture” without a specifically justified subcomponent;
- “solves public-record retrieval”;
- “perfect retrieval” without immediately bounding it to the frozen benchmark;
- “detects corruption”;
- “detects wrongdoing”;
- “proves deterministic retrieval is better than vector search”;
- “generalizes to municipalities” without naming the two tested publisher stacks and the limits of the transfer claim;
- “ground truth” when the object is actually a publisher-authorized evidence target; or
- “absence proves no disposition” or equivalent negative-evidence inflation.

## Language preferred

Prefer:

- “within the frozen benchmark population”;
- “canonical evidence target”;
- “publisher-backed relationship”;
- “bounded source search”;
- “no repeatable deterministic retrieval failure class was observed in this benchmark”;
- “semantic/vector retrieval was not justified by the measured failure profile”;
- “transfer across two materially different publisher/evidence-unit stacks”; and
- “no end-to-end substitute is claimed or required for this publication.”

## Publication posture

This paper should be framed as a **methods + empirical transfer report**, not a novelty manifesto.

The strongest scholarly value is that Proofline already contains a visible history of corrections, frozen benchmark identities, benign outcomes, source-contract failures, and explicit claims not made. The paper should expose that discipline rather than flatten it into a conventional product-performance narrative.
