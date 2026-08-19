# R1 Retrieval Benchmark Freeze Receipt

This receipt establishes the historical boundary between **benchmark selection** and
**benchmark scoring** for Proofline R1.

The candidate suite was generated and curated without consulting retrieval results.
No , search ranking, hit-rate, recall, or semantic retrieval result
was used to choose these cases before this freeze commit.

- Source branch head before freeze: `23e03ce2e3d963ce0b7cf793cd9bd39569f485c3`
- Pool workflow run: https://github.com/JosephJMWalker-MBA/Proofline/actions/runs/32285133807
- Frozen benchmark: `r1-benchmark-unscored.json`
- Frozen benchmark SHA-256: `867d6c47f3ae542c40cfa5748a0473c9dffd9af8bf5db6fa3af711690fe2da82`
- Preserved broad raw pool: `r1-raw-pool.json`
- Raw pool SHA-256: `994b052a29bdd0fc72567e2063ef17388ae4b9bef1ea8e83aa8a5df32642e18d`
- Evaluation schema: `proofline-retrieval-eval/v2`
- Selection method: `proofline-retrieval-benchmark-pool/v1` → `proofline-retrieval-benchmark-curation/v1`
- Retrieval results consulted before freeze: **false**

## Rule

Future retrieval evaluation must score this frozen file as written. Retrieval misses are
measurements, not reasons to rewrite the suite. Any later benchmark revision must receive
a new filename/version and its own pre-score freeze receipt.
