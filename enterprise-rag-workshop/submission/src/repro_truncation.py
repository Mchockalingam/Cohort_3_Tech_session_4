"""Reproduce failure F4: unmerged section siblings + the original truncating packet builder.

Run: python -m submission.src.repro_truncation
"""

from src.embeddings import LocalEncoder
from src.vector_store import authorization_filter

from .incident import SUB_QUERIES
from .packet import build_packet
from .retrieve import hybrid
from .store import collection


def raw_siblings(coll, hit, role):
    section = hit.text.split("\n", 1)[0]
    where = authorization_filter(role)
    where["$and"] += [{"doc_id": {"$eq": hit.metadata["doc_id"]}}]
    page = coll.get(where=where, include=["documents", "metadatas"])
    sibs = [(m["chunk_index"], i, t, m) for i, t, m in zip(page["ids"], page["documents"], page["metadatas"])
            if t.split("\n", 1)[0] == section]
    return [type(hit)(i, t, m, hit.score, "raw-sibling") for _, i, t, m in sorted(sibs)]


def main():
    enc, coll = LocalEncoder(), collection()
    hits, seen = [], set()
    for _, doc_type, query in SUB_QUERIES:
        for h in hybrid(coll, enc, query, "engineer", 3, doc_type)[:1]:
            for s in raw_siblings(coll, h, "engineer"):
                if s.id not in seen:
                    seen.add(s.id)
                    hits.append(s)
    for label, kwargs in (("ORIGINAL behaviour (truncate=True, unmerged)", {"truncate": True}),
                          ("FIXED behaviour (truncate=False, unmerged)", {"truncate": False})):
        p = build_packet(hits, 1200, **kwargs)
        last = p.text.rstrip().splitlines()[-1]
        print(f"{label}: sources={len(p.sources)} tokens={p.token_count} dropped={[d['doc_id'] for d in p.dropped]}")
        print(f"  last line: {last!r}")


if __name__ == "__main__":
    main()
