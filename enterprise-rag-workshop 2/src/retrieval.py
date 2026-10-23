"""Dense, lexical and RRF hybrid retrieval with filters before ranking."""

import re

from .models import SearchHit
from .vector_store import authorization_filter


def dense(coll, encoder, question: str, role: str, k: int = 5,
          doc_type: str | None = None) -> list[SearchHit]:
    if k < 1:
        raise ValueError("k must be >= 1")
    if coll.count() == 0:
        return []
    result = coll.query(query_embeddings=[encoder.query(question)], n_results=k,
                        where=authorization_filter(role, doc_type),
                        include=["documents", "metadatas", "distances"])
    hits = []
    for id_, text, meta, distance in zip(
        result["ids"][0], result["documents"][0],
        result["metadatas"][0], result["distances"][0]
    ):
        # Only valid for a cosine-indexed collection; never mix with L2 scores.
        hits.append(SearchHit(id_, text, meta, 1.0 - float(distance), "dense"))
    return hits


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower())


def lexical(coll, question: str, role: str, k: int = 5,
            doc_type: str | None = None) -> list[SearchHit]:
    """Small-corpus BM25 demo. Don't full-scan a large enterprise collection!"""
    from rank_bm25 import BM25Okapi

    records, offset, limit = [], 0, 500
    where = authorization_filter(role, doc_type)
    while True:
        page = coll.get(where=where, include=["documents", "metadatas"],
                        limit=limit, offset=offset)
        records.extend(zip(page["ids"], page["documents"], page["metadatas"]))
        if len(page["ids"]) < limit:
            break
        offset += limit
    if not records or not _tokens(question):
        return []
    corpus = [_tokens(text) for _, text, _ in records]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokens(question))
    ranked = sorted(range(len(records)), key=lambda i: (-float(scores[i]), records[i][0]))
    # In this demo, zero-scoring chunks are excluded (unlike nearest-neighbour fallback).
    return [SearchHit(records[i][0], records[i][1], records[i][2], float(scores[i]), "bm25")
            for i in ranked[:k] if scores[i] > 0]


def reciprocal_rank_fusion(ranked_lists: list[list[SearchHit]], k_const: int = 60,
                           limit: int = 5) -> list[SearchHit]:
    """RRF fuses RANKS, never adds incommensurable BM25 and cosine scores."""
    scores: dict[str, float] = {}
    exemplars: dict[str, SearchHit] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k_const + rank)
            exemplars[hit.id] = hit
    ranked_ids = sorted(scores, key=lambda id_: (-scores[id_], id_))[:limit]
    return [SearchHit(id_, exemplars[id_].text, exemplars[id_].metadata,
                      scores[id_], "rrf") for id_ in ranked_ids]


def hybrid(coll, encoder, question: str, role: str, k: int = 5,
           doc_type: str | None = None) -> list[SearchHit]:
    return reciprocal_rank_fusion([
        dense(coll, encoder, question, role, max(10, k), doc_type),
        lexical(coll, question, role, max(10, k), doc_type),
    ], limit=k)
