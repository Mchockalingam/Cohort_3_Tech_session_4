"""Cross-encoder reranking of ALREADY authorised retrieval candidates.

Usage:
    python -m src.cli search --mode hybrid --rerank --candidate-k 15 \
      --k 5 --role engineer --question "Who approves emergency rollback?"

The model is downloaded on first use. Reranker scores express relative
relevance within a candidate set; they are not calibrated truth probabilities.
"""

import math
import os
from functools import lru_cache
from typing import Protocol, Sequence

from .models import SearchHit
from .vector_store import ROLES, TENANT_ID


DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


class PairScorer(Protocol):
    """Small injectable interface for easy offline tests."""

    def predict(self, pairs: list[tuple[str, str]], batch_size: int = 16): ...


@lru_cache(maxsize=2)
def load_cross_encoder(model_name: str | None = None):
    """Cache CPU/GPU model instance; require approval before model download."""
    from sentence_transformers import CrossEncoder

    name = model_name or os.getenv("RERANK_MODEL", DEFAULT_RERANK_MODEL)
    return CrossEncoder(name, max_length=512, trust_remote_code=False)


def rerank_hits(
    question: str,
    candidates: Sequence[SearchHit],
    *,
    top_k: int = 5,
    role: str,
    scorer: PairScorer | None = None,
    batch_size: int = 16,
) -> list[SearchHit]:
    """Score query/passage pairs and retain the best authorised passages.

    The calling retrieval step MUST prefilter by trusted identity and tenant.
    This check intentionally fails closed if a caller passes a forbidden hit.
    A CLI role argument is only a training simulation, not authentication.
    """
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    if top_k <= 0 or batch_size <= 0:
        raise ValueError("top_k and batch_size must be positive")
    if not question.strip():
        raise ValueError("Question cannot be empty")
    if not candidates:
        return []

    deduped: list[SearchHit] = []
    seen: set[str] = set()
    for hit in candidates:
        meta = hit.metadata
        if (
            meta.get("tenant_id") != TENANT_ID
            or meta.get("status") != "active"
            or meta.get(f"role_{role}") is not True
        ):
            raise PermissionError(f"Forbidden or stale retrieval candidate: {hit.id}")
        if hit.id not in seen:
            seen.add(hit.id)
            deduped.append(hit)

    scorer = scorer or load_cross_encoder()
    pairs = [(question, hit.text) for hit in deduped]
    raw_scores = scorer.predict(pairs, batch_size=batch_size)
    if len(raw_scores) != len(deduped):
        raise ValueError("Reranker must return exactly one score per candidate")
    scores = [float(score) for score in raw_scores]
    if not all(math.isfinite(score) for score in scores):
        raise ValueError("Reranker emitted a NaN or infinite score")

    # Stable tie break: preserve the candidate retriever's original rank.
    ranked = sorted(enumerate(deduped), key=lambda row: (-scores[row[0]], row[0]))
    return [
        SearchHit(hit.id, hit.text, dict(hit.metadata), scores[i], "cross-encoder")
        for i, hit in ranked[:top_k]
    ]
