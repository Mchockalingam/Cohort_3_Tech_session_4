"""Secured wrappers over the ORIGINAL dense / BM25 / RRF hybrid retrieval (Task C.1).

The original functions already push the ACL predicate (tenant, status=active, role flag,
doc_type) into the Chroma `where` clause, i.e. filtering happens INSIDE the store before
ranking. These wrappers add a fail-closed post-check on every returned record.
"""

from src import retrieval as _orig

from .store import enforce_authorized


def dense(coll, encoder, question, role, k=5, doc_type=None):
    return enforce_authorized(_orig.dense(coll, encoder, question, role, k, doc_type), role)


def lexical(coll, question, role, k=5, doc_type=None):
    return enforce_authorized(_orig.lexical(coll, question, role, k, doc_type), role)


def hybrid(coll, encoder, question, role, k=5, doc_type=None):
    return enforce_authorized(_orig.hybrid(coll, encoder, question, role, k, doc_type), role)


SEARCH = {
    "dense": lambda coll, enc, q, role, k=5, doc_type=None: dense(coll, enc, q, role, k, doc_type),
    "keyword": lambda coll, enc, q, role, k=5, doc_type=None: lexical(coll, q, role, k, doc_type),
    "hybrid": lambda coll, enc, q, role, k=5, doc_type=None: hybrid(coll, enc, q, role, k, doc_type),
}
