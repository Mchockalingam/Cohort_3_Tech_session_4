"""Replaceable local embedding adapter. No text is sent to a hosted API."""

import os
from functools import lru_cache

import numpy as np


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, trust_remote_code=False)


class LocalEncoder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("EMBED_MODEL", DEFAULT_MODEL)
        self.model = _load_model(self.model_name)

    def documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode_document(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype="float32").tolist()

    def query(self, question: str) -> list[float]:
        vectors = self.model.encode_query([question], normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors[0], dtype="float32").tolist()
