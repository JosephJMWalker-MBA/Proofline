# Search & Retrieval Evaluation — lexical baseline

Proofline treats search as a disposable derivative over Silver evidence. Retrieval may rank or omit evidence; it may never redefine evidence identity.

## Lexical index

The current baseline uses SQLite FTS5 over the **preferred extraction** for each evidence unit.

```bash
proofline index
proofline search "Northstar Civic Systems"
```

Each result includes:

- search-index build ID
- stable `evidence_id`
- immutable `artifact_id`
- source locator
- highlighted snippet
- BM25 rank value
- extraction method and quality
- observed source URI(s) and native identifier(s)

The index can be deleted and rebuilt without changing any Bronze or Silver identity.

## Query normalization

The v1 lexical query path case-folds input, extracts Unicode alphanumeric terms, and joins them with FTS5 `AND` semantics.

For example:

```text
C-002 / Lakeview Systems
```

becomes:

```text
"c" AND "002" AND "lakeview" AND "systems"
```

This is intentionally conservative and deterministic. It favors explainability over hidden query expansion.

## Exact native identifiers

Publisher-native identifiers should not be forced through semantic search.

```bash
proofline lookup CSV-B
```

This follows exact `native_identifier` metadata to the indexed evidence units associated with the corresponding artifact(s).

## Index builds

`proofline index` rebuilds the FTS table transactionally from preferred evidence and records build metadata:

- build ID
- build time
- indexed evidence count
- tokenizer
- query mode

Index construction reads preferred evidence in bounded batches rather than materializing the full corpus in memory.

## Retrieval benchmark

Proofline evaluation cases explicitly name the evidence they expect retrieval to find.

```json
{
  "schema": "proofline-retrieval-eval/v1",
  "name": "Example suite",
  "cases": [
    {
      "case_id": "contract-award",
      "query": "Contract award 250 000",
      "expected": [
        {
          "source_uri": "https://example.gov/report.pdf",
          "locator": "page:7"
        }
      ]
    }
  ]
}
```

An optional `artifact_sha256` can pin a target to a particular source version when one URI has produced multiple artifacts.

Run a suite with:

```bash
proofline evaluate tests/retrieval_eval.json --k 5
```

## Metrics

The baseline reports separate measures:

### Hit rate at k

Fraction of research questions for which at least one expected evidence target appears in the top `k`.

### Target recall at k

Fraction of all resolved expected evidence targets recovered in the top `k` results.

This matters when one question deliberately expects multiple pages or records.

### Provenance validity

Fraction of returned hits whose evidence ID, artifact ID, locator, and source lineage still resolve through Proofline's system of record.

Provenance validity is deliberately separate from relevance. A perfectly traceable search result can still be irrelevant to the research question.

### Unresolved targets

Evaluation definitions are themselves checked. If an expected source/locator cannot be resolved to evidence in the corpus, Proofline reports it rather than silently lowering the denominator.

## Initial difficult-corpus suite

The first lexical suite contains targets from three different record forms:

1. a born-digital PDF contract amount;
2. a specific value in a conflicting CSV record;
3. a row in a formula-bearing XLSX workbook.

These are baseline sanity checks, not a claim that lexical retrieval is sufficient for investigative research.

## What FTS5 does not solve

The current lexical baseline is expected to miss some classes of retrieval:

- synonyms and conceptual paraphrases;
- relationships stated across distant passages;
- severe OCR variants;
- implicit references and aliases;
- date/value normalization across incompatible formats;
- questions whose answer requires joining multiple evidence units.

Those failures should become benchmark cases.

## When semantic retrieval is justified

Proofline should not add a vector database simply because vectors are fashionable.

The intended sequence is:

```text
known evidence targets
       |
       v
measure lexical retrieval
       |
       +-- sufficient --> keep simpler system
       |
       +-- repeatable semantic failures
               |
               v
        test semantic retrieval
               |
               v
        compare benchmark delta
```

Embedding similarity would remain a retrieval signal, never evidence strength or corroboration.

## Current open M3 work

The next retrieval work is deterministic structured lookup for dates and numeric values. This should complement FTS rather than overloading token search with semantics it does not actually possess.
