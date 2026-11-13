"""Version-safe index maintenance (Task A.3) around the original Chroma demo store.

Reuses the ORIGINAL `src.vector_store.authorization_filter`, ROLES and TENANT_ID.
"""

from pathlib import Path

from src.models import SearchHit, TextChunk
from src.vector_store import ROLES, TENANT_ID

SUBMISSION_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SUBMISSION_ROOT / ".chroma"        # separate from the workshop's .local_chroma
COLLECTION_NAME = "northstar-assignment-v1"


def collection(db_path: Path = DEFAULT_DB, name: str = COLLECTION_NAME, ephemeral: bool = False):
    """Cosine collection. `ephemeral=True` gives an isolated in-memory test store.

    embedding_function=None: we always pass our own vectors, so Chroma never downloads or
    silently applies its default model.
    """
    import chromadb

    client = chromadb.EphemeralClient() if ephemeral else chromadb.PersistentClient(path=str(db_path))
    return client.get_or_create_collection(
        name=name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None)


# --- Fail-closed authorisation re-check --------------------------------------------------------

def is_authorized(metadata: dict, role: str) -> bool:
    return (metadata.get("tenant_id") == TENANT_ID and metadata.get("status") == "active"
            and metadata.get(f"role_{role}") is True)


def enforce_authorized(hits: list[SearchHit], role: str) -> list[SearchHit]:
    """Defence in depth: the store filter is primary; if it ever leaks, raise instead of serving."""
    leaked = [h.metadata.get("doc_id") for h in hits if not is_authorized(h.metadata, role)]
    if leaked:
        raise PermissionError(f"Store returned unauthorised records for role={role}: {leaked}")
    return hits


# --- Upsert / stale detection / reindex ---------------------------------------------------------

def store_metadata(chunk: TextChunk) -> dict:
    meta = {k: v for k, v in chunk.metadata.items() if k != "allowed_roles"}
    meta.update({f"role_{role}": role in chunk.metadata["allowed_roles"] for role in ROLES})
    meta["doc_version_key"] = f"{chunk.metadata['doc_id']}@{chunk.metadata['version']}"
    return meta


def upsert_chunks(coll, chunks: list[TextChunk], encoder, batch_size: int = 50) -> int:
    permitted = [c for c in chunks if c.metadata["status"] == "active"]  # retired never written
    for start in range(0, len(permitted), batch_size):
        batch = permitted[start:start + batch_size]
        texts = [c.text for c in batch]
        coll.upsert(ids=[c.id for c in batch], documents=texts, embeddings=encoder.documents(texts),
                    metadatas=[store_metadata(c) for c in batch])
    return len(permitted)


def _all_records(coll) -> list[tuple[str, dict]]:
    records, offset, limit = [], 0, 500
    while True:
        page = coll.get(include=["metadatas"], limit=limit, offset=offset)
        records.extend(zip(page["ids"], page["metadatas"]))
        if len(page["ids"]) < limit:
            return records
        offset += limit


def stale_ids(coll, current_chunks: list[TextChunk]) -> list[str]:
    """Store IDs not in the current active chunk set, or whose stored metadata drifted.

    Chunk IDs hash doc_id + version + text, so a replaced version, a retired document, a
    removed document, an edited chunk and (via metadata drift) an ACL-only change all surface.
    """
    wanted = {c.id: store_metadata(c) for c in current_chunks if c.metadata["status"] == "active"}
    stale = []
    for id_, meta in _all_records(coll):
        expected = wanted.get(id_)
        if expected is None or any(meta.get(k) != v for k, v in expected.items()):
            stale.append(id_)
    return sorted(stale)


def delete_document(coll, doc_id: str) -> int:
    """Hard-delete every vector of one doc_id (all versions), e.g. on retention request."""
    ids = coll.get(where={"doc_id": {"$eq": doc_id}}, include=[])["ids"]
    if ids:
        coll.delete(ids=ids)
    return len(ids)


def verify_index(coll, current_chunks: list[TextChunk]) -> None:
    """Post-condition: store IDs == active chunk IDs and no non-active record present."""
    expected = {c.id for c in current_chunks if c.metadata["status"] == "active"}
    actual = {id_ for id_, _ in _all_records(coll)}
    if actual != expected:
        raise AssertionError(f"Index drift: extra={sorted(actual - expected)[:5]} "
                             f"missing={sorted(expected - actual)[:5]}")
    if coll.get(where={"status": {"$ne": "active"}}, include=[])["ids"]:
        raise AssertionError("Non-active record found in index")


def reindex(coll, current_chunks: list[TextChunk], encoder) -> dict:
    """Make the store exactly equal the active catalog: delete stale IDs, then upsert new ones.

    Delete-before-upsert means a retired version never coexists with its replacement after
    this returns. Production: build a new collection, verify, then switch an alias (blue/green).
    """
    removed = stale_ids(coll, current_chunks)
    if removed:
        coll.delete(ids=removed)
    active = [c for c in current_chunks if c.metadata["status"] == "active"]
    existing = set(coll.get(ids=[c.id for c in active], include=[])["ids"]) if active else set()
    new = [c for c in active if c.id not in existing]
    upsert_chunks(coll, new, encoder)
    verify_index(coll, current_chunks)
    return {"deleted": len(removed), "added": len(new), "unchanged": len(active) - len(new),
            "count": coll.count()}
