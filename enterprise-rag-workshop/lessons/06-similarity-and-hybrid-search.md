# 06 — Similarity search, lexical search, hybrid retrieval and reranking

**Time: 15 minutes** · **Objective:** Understand k-nearest-neighbour retrieval, rank fusion and trade-offs between semantic and exact-match search.

## Similarity is a retrieval signal, not a factual guarantee

Given a question vector `q` and document vectors `d`, dense retrieval returns top-k nearest neighbours. In a cosine index, higher cosine similarity is preferable. In Chroma's cosine **distance** output, lower is preferable. A distance of 0 is equivalent to cosine similarity of 1.

| Retrieval method | Most useful for | Typical failure |
|---|---|---|
| Dense/vector | Paraphrases, terminology mismatch, similar concepts | Exact error code or policy ID can be missed |
| BM25/keyword | Ticket IDs, `P1`, `HTTP 5xx`, product codes | Synonyms and intent paraphrases |
| Hybrid (dense + lexical) | Mixed enterprise questions | More cost, tuning and index complexity |
| Cross-encoder reranking | Select a precise top subset from an already retrieved pool | Extra latency; cannot recover documents absent from candidate pool |

## Code: dense search with trusted filters

The production-minded lesson rule is **filter first, rank within the authorized subset**. The workshop uses [`../src/retrieval.py`](../src/retrieval.py).

```python
from src.embeddings import LocalEncoder
from src.retrieval import dense
from src.vector_store import collection

coll = collection()
encoder = LocalEncoder()
hits = dense(coll, encoder,
             "Recent deployment caused payment database pool waiters",
             role="engineer", k=5, doc_type="runbook")
for hit in hits:
    print(hit.metadata["doc_id"], round(hit.score, 3), hit.text[:70])
```

The code uses `collection.query(query_embeddings=[...], where=authorization_filter(...))`. Document status and role are applied **inside the query**, not on a list of unauthorized hits afterward.

## Code: exact-term and hybrid RRF

BM25 is a statistical lexical ranking function that rewards informative word matches. Reciprocal rank fusion (RRF) combines result **positions**, not raw scores. This avoids incorrectly adding unrelated BM25 weights and cosine values.

\[
\operatorname{RRF}(d) = \sum_{r\in\{\mathrm{dense},\mathrm{BM25}\}} \frac{1}{60+\operatorname{rank}_r(d)}
\]

```python
from src.retrieval import dense, lexical, reciprocal_rank_fusion

question = "P1 payment API 5xx database pool saturation"
vector_hits = dense(coll, encoder, question, role="engineer", k=10)
keyword_hits = lexical(coll, question, role="engineer", k=10)
combined = reciprocal_rank_fusion([vector_hits, keyword_hits], limit=5)
for h in combined:
    print(h.method, round(h.score, 4), h.metadata["doc_id"])
```

```bash
python -m src.cli search --mode dense --question "P1 payments connection pool"
python -m src.cli search --mode keyword --question "P1 payments connection pool"
python -m src.cli search --mode hybrid --question "P1 payments connection pool"
```

In this **small demo**, BM25 enumerates authorised Chroma records and scores them in memory. That is not a scalable keyword index. For enterprise deployment use a purpose-built inverted index / PostgreSQL full-text search / search-engine native hybrid retrieval with the **same authorization filter**.

## Optional reranking example

Use a cross-encoder only on a small, already-authorised candidate set:

```python
# Optional: model download and additional inference latency.
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
pairs = [(question, hit.text) for hit in combined]
scores = reranker.predict(pairs)
reranked = sorted(zip(combined, scores), key=lambda row: -float(row[1]))
print([(h.metadata["doc_id"], round(float(s), 3)) for h, s in reranked])
```

This model is an example for teaching. Benchmark ranking quality, licence, latency and language coverage before use with real runbooks.

## Common retrieval enhancements

- **Query rewriting:** expand acronym-only questions but preserve their exact identifiers.
- **Multi-query retrieval:** for multi-part questions, retrieve evidence for each subquestion, then deduplicate.
- **MMR/diversification:** penalize redundant near-duplicate chunks to leave room for different evidence.
- **Metadata boosting:** prefer current approved source versions, never supersede access policy with a rank boost.
- **Time/version awareness:** use source status/validity rather than trusting document titles like “latest”.

**Teaching checkpoint:** Ask: “If BM25 score is 4.3 and cosine similarity is 0.76, may we simply average them?” No: scales differ; normalize appropriately or fuse ranks.

**Next:** [07 — Retrieving relevant context](07-context-retrieval.md).
