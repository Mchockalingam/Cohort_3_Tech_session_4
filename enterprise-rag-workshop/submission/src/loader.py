"""Catalog loading on top of the ORIGINAL `src.loading.load_catalog` (unchanged).

Adds two normalisations after loading:
  * source_path in POSIX form (the original uses str(Path), i.e. backslashes on Windows);
  * a `trust` rating, defaulting to "trusted" for the approved catalog.
"""

from pathlib import Path

from src.loading import DEFAULT_CATALOG, load_catalog as _original_load_catalog
from src.models import SourceDocument

TRUST_LEVELS = {"trusted", "untrusted"}


def load_catalog(catalog_path: Path = DEFAULT_CATALOG) -> list[SourceDocument]:
    docs = []
    for doc in _original_load_catalog(catalog_path):
        meta = dict(doc.metadata)
        meta["source_path"] = meta["source_path"].replace("\\", "/")
        meta.setdefault("trust", "trusted")
        if meta["trust"] not in TRUST_LEVELS:
            raise ValueError(f"Invalid trust rating: {meta['doc_id']}")
        docs.append(SourceDocument(doc.text, meta))
    return docs


def catalog_audit(catalog_path: Path = DEFAULT_CATALOG) -> list[dict]:
    """One row per loaded page: the fields a reviewer needs to sign off an index build."""
    rows = []
    for doc in load_catalog(catalog_path):
        m = doc.metadata
        rows.append({"doc_id": m["doc_id"], "version": m["version"], "status": m["status"],
                     "page": m["page"], "allowed_roles": ",".join(m["allowed_roles"]),
                     "doc_type": m["doc_type"], "classification": m["classification"],
                     "trust": m["trust"], "effective_date": m["effective_date"],
                     "indexed": m["status"] == "active"})
    return rows
