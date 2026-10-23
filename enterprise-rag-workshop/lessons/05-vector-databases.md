# 05 — Vector databases, indexing and metadata filters

**Time: 15 minutes** · **Objective:** Store chunk vectors with provenance; explain ANN indexing and demonstrate filtering **before** similarity ranking.

## What a vector database stores

For each chunk we persist a stable ID, embedding, original text and metadata. An approximate-nearest-neighbour index such as HNSW speeds similarity lookup. Enterprise designs also need persistence, deletion, versioning, tenant boundaries, access controls, backup, observability and scalable keyword search.

| Option | Training/enterprise fit | Considerations |
|---|---|---|
| **Chroma** | Local teaching and prototypes | Embedded persistent mode is not enterprise SSO/authorization |
| **PostgreSQL + pgvector** | Teams with existing relational governance | SQL joins, transactions, RLS; index tuning and recall testing |
| **Qdrant/Milvus/Weaviate** | Dedicated search infrastructure | Payload filters, scaling, operational expertise |
| **OpenSearch/Elasticsearch** | Existing search and hybrid-search stack | Text+vector index tuning, field mappings and relevance |

The workshop runs a local **Chroma cosine-indexed collection**. Its returned value is **cosine distance**, not a probability; only in that metric, `1 - distance` equals cosine similarity. The details of `configuration`, `.upsert`, `where` and `.query` follow current Chroma documentation.

## Code: persist and index chunks

The full implementation is [`../src/vector_store.py`](../src/vector_store.py). A minimal version:

```python
from src.loading import load_catalog
from src.chunking import create_chunks
from src.embeddings import LocalEncoder
from src.vector_store import collection, upsert_chunks

docs = [d for d in load_catalog() if d.metadata["status"] == "active"]
chunks = [c for doc in docs for c in create_chunks(doc, "headings", 550, 80)]

encoder = LocalEncoder()
coll = collection()  # Chroma PersistentClient, cosine HNSW collection
print("Indexed:", upsert_chunks(coll, chunks, encoder))
print("Rows:", coll.count())
```

```bash
python -m src.cli index
```

The working code performs **upsert**, so rerunning the same corpus does not create duplicates with the same chunk IDs. It intentionally does not implement distributed ingestion, atomic blue/green reindexing, or obsolete-ID deletion. When the model/chunk strategy/catalog changes, make a fresh index with a new collection/namespace and swap traffic only after validating it.

## Code: authorize at the search layer

```python
from src.vector_store import authorization_filter

print(authorization_filter("engineer", "runbook"))
# {'$and': [{'tenant_id': {'$eq': 'northstar-demo'}},
#          {'status': {'$eq': 'active'}},
#          {'role_engineer': {'$eq': True}},
#          {'doc_type': {'$eq': 'runbook'}}]}
```

These fields are set by a trusted catalog in the demo; in production, entitlements must come from an identity service and be enforced by secure services/storage. A local CLI flag is *not* authentication. Avoid relying solely on application-supplied Chroma metadata predicates for high-assurance tenant isolation.

## Production alternative: PostgreSQL with pgvector

This is an **illustrative schema**, not the local workshop runtime:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE knowledge_chunks (
    chunk_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    doc_id text NOT NULL,
    version text NOT NULL,
    status text NOT NULL,
    content text NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX knowledge_hnsw_cosine
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

-- RLS policies and trusted session identities must be configured separately.
-- $1 = trusted tenant ID; $2 = authorized query vector.
SELECT doc_id, content, 1 - (embedding <=> $2::vector) AS cosine_similarity
FROM knowledge_chunks
WHERE tenant_id = $1 AND status = 'active'
ORDER BY embedding <=> $2::vector
LIMIT 5;
```

Important: this SQL alone **does not enforce user-role ACLs**. Real deployments need row-level security or equivalent, indexes suited to filtered ANN retrieval, and recall-vs-filter testing. With approximate indexes, filtering and recall can interact.

## Lab: role and version checks

```bash
python -m src.cli search --role engineer --mode dense --question "fraud verification phrase"
python -m src.cli search --role security --mode dense --question "fraud verification phrase"
python -m src.cli search --role engineer --mode dense --question "restart database without approval"
```

Examine **source IDs**, not merely whether some chunk is returned. Dense search may return the closest authorised chunk even to an unanswerable question. The restricted document must never appear for `engineer`; the retired document must never appear for any role.

**Next:** [06 — Similarity and hybrid search](06-similarity-and-hybrid-search.md). [Vector database references](../references.md).
