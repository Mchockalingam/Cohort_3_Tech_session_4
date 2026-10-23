"""Single-node Chroma demonstration; real deployments need an authenticated store."""

from pathlib import Path

from .models import TextChunk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / ".local_chroma"
COLLECTION_NAME = "northstar_rag_v1"
ROLES = {"engineer", "operator", "manager", "security"}
TENANT_ID = "northstar-demo"  # A fixed synthetic tenant, NOT user-supplied input.


def collection(db_path: Path = DEFAULT_DB):
    import chromadb

    client = chromadb.PersistentClient(path=str(db_path))
    # The cosine metric is explicit: Chroma returns a DISTANCE (lower is better).
    return client.get_or_create_collection(
        name=COLLECTION_NAME, configuration={"hnsw": {"space": "cosine"}}
    )


def authorization_filter(role: str, doc_type: str | None = None) -> dict:
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    clauses = [
        {"tenant_id": {"$eq": TENANT_ID}},
        {"status": {"$eq": "active"}},
        {f"role_{role}": {"$eq": True}},
    ]
    if doc_type and doc_type != "all":
        if doc_type not in {"runbook", "policy", "postmortem"}:
            raise ValueError(f"Invalid document type: {doc_type}")
        clauses.append({"doc_type": {"$eq": doc_type}})
    return {"$and": clauses}


def upsert_chunks(coll, chunks: list[TextChunk], encoder, batch_size: int = 50) -> int:
    permitted = [c for c in chunks if c.metadata["status"] == "active"]
    for start in range(0, len(permitted), batch_size):
        batch = permitted[start : start + batch_size]
        texts = [c.text for c in batch]
        metadata = []
        for chunk in batch:
            meta = {k: v for k, v in chunk.metadata.items() if k != "allowed_roles"}
            # Boolean role fields work in this teaching index; real ACLs should use
            # authoritative entitlements and tenant-specific security boundaries.
            meta.update({f"role_{role}": role in chunk.metadata["allowed_roles"] for role in ROLES})
            metadata.append(meta)
        coll.upsert(ids=[c.id for c in batch], documents=texts,
                    embeddings=encoder.documents(texts), metadatas=metadata)
    return len(permitted)
