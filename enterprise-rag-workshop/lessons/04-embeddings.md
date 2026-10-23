# 04 — Embeddings and vector representations

**Time: 15 minutes** · **Objective:** Convert text into vectors, compare distances and choose a model whose task, licence and operational constraints match enterprise retrieval.

## The concept

An embedding model maps a text passage to a vector of real numbers. Semantically related passages often lie closer in embedding space; they are **not** guaranteed to be factually compatible or relevant to the user's exact operational question. Embeddings can miss important negations, identifiers, units or superseding policy clauses.

For a vector `a` and `b`, **cosine similarity** is:

\[
\operatorname{cos}(a,b)=\frac{a\cdot b}{\|a\|\,\|b\|}
\]

For normalized vectors, cosine similarity is the dot product. The demonstration uses a local sentence-transformer, `sentence-transformers/all-MiniLM-L6-v2`, so no source text needs to be sent to a hosted embedding API. Its small footprint helps in the classroom, but you should benchmark stronger, domain-specific and multilingual models before production.

## Code: embed documents and questions

[`../src/embeddings.py`](../src/embeddings.py) wraps the encoding calls.

```python
import numpy as np
from src.embeddings import LocalEncoder

encoder = LocalEncoder()
passages = [
    "Database connection pool exhaustion increases payment timeouts.",
    "A short outage at the cafeteria stopped lunch orders.",
]
doc_vectors = encoder.documents(passages)
query_vector = encoder.query("What causes payments database timeouts?")

print("Vector dimension:", len(query_vector))
for text, vector in zip(passages, doc_vectors):
    print(round(float(np.dot(query_vector, vector)), 3), text)
```

Run the comparison without writing code:

```bash
python -m src.cli embed
```

The current Sentence Transformers documentation provides `encode_query` and `encode_document` for asymmetric retrieval: questions and passages may be treated differently when a model defines distinct instructions/routes. Use **the same embedding model and dimensionality** at both indexing and query time; if the model changes, build a new versioned index.

## Enterprise model-selection checklist

| Dimension | What to measure or verify |
|---|---|
| Domain relevance | Retrieval results on actual incident tickets, policies and code identifiers |
| Language | Indian languages, mixed English/local-language queries, transliteration |
| Latency | CPU/GPU p50/p95, batching, cold start, request throughput |
| Token limits | Long chunks may be truncated silently by an embedding model |
| Privacy | Local embedding versus approved hosted provider; residency and retention |
| Versioning | Model ID, dimensions, normalization, pre-processing and index manifest |
| Cost | Indexing volume, re-embedding churn, query traffic and infrastructure |

## Frequent errors

- Comparing embeddings from *different* model families as if they shared coordinates.
- Applying a universal “score above 0.80 = true answer” rule; similar vectors do not verify truth.
- Using only dense search for exact incident IDs, error codes and policy numbers; supplement with lexical retrieval.
- Forgetting to evaluate non-English queries and domain abbreviations.

**Next:** [05 — Vector databases](05-vector-databases.md). [Embedding model docs](../references.md).
