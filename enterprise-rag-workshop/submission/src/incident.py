"""Deterministic multi-query evidence assembly for the assignment's incident question.

One broad query tends to return several chunks from the same runbook and miss the policy
documents. Fixed sub-queries per evidence need (diagnostics / approval / recovery /
communications), each restricted by doc_type inside the store, give predictable coverage.
"""

from .packet import build_packet
from src.models import SearchHit
from .packet import ScreenedPacket
from src.vector_store import authorization_filter

from .retrieve import hybrid
from .store import enforce_authorized

INCIDENT_QUESTION = (
    "Checkout failures crossed 5% 5xx for five minutes after a concurrency configuration "
    "deployment; pool utilization is 93%. What immediate checks should the responder perform, "
    "what can be rolled back, who must approve it, how do we verify recovery, and what "
    "customer-update cadence applies?"
)

# (evidence need, doc_type filter, focused query). Order = priority inside the token budget.
SUB_QUERIES = [
    ("p1_trigger", "runbook", "P1 trigger 5xx five consecutive minutes first ten minutes checks"),
    # v1 had only the two queries above; it returned the trigger + detection sections but
    # missed the actual check list and triage steps. These two close that coverage gap.
    # Pool words are deliberately absent: with them, RUN-DB-201 tied RUN-PAY-101 under RRF
    # (0.032 each) and the hash-ID tie-break dropped the check list (RESULTS.md, failure F3).
    ("immediate_checks", "runbook", "first ten minutes acknowledge P1 page record incident ID request "
                                    "rate 5xx error rate p95 latency error-budget last deployment "
                                    "sanitized logs trace IDs"),
    ("pool_detect", "runbook", "connection pool greater than 90% utilization five minutes triage recent changes"),
    ("pool_triage_steps", "runbook", "triage sequence recent changes pool size request concurrency slow "
                                     "queries connection leaks propose rollback escalate restart loops"),
    ("rollback_approval", "policy", "emergency rollback approval incident commander independent change approver"),
    ("customer_updates", "policy", "P1 customer-facing update every 30 minutes incident commander"),
    ("recovery_verification", "runbook", "after mitigation verify utilization below 75% error rate below 1% 15 minutes"),
]


def section_siblings(coll, hit: SearchHit, role: str) -> list[SearchHit]:
    """All chunks of the same heading section as `hit`, in document order.

    Heading-aware chunks start with 'Section: <path>'. A long section (e.g. a numbered list)
    is split into several chunks; returning only one would cut the list mid-way. The lookup
    goes through the store WITH the ACL filter, and results are re-checked fail-closed.
    """
    section = hit.text.split("\n", 1)[0]
    if not section.startswith("Section: "):
        return [hit]
    where = authorization_filter(role)
    where["$and"].append({"doc_id": {"$eq": hit.metadata["doc_id"]}})
    where["$and"].append({"version": {"$eq": hit.metadata["version"]}})
    page = coll.get(where=where, include=["documents", "metadatas"])
    siblings = [SearchHit(i, t, m, hit.score, "section-expand")
                for i, t, m in zip(page["ids"], page["documents"], page["metadatas"])
                if t.split("\n", 1)[0] == section]
    siblings = enforce_authorized(sorted(siblings, key=lambda h: h.metadata["chunk_index"]), role)
    return [merge_section(siblings)] if len(siblings) > 1 else [hit]


def _strip_overlap(previous: str, body: str, max_overlap: int = 200) -> str:
    """Remove the chunk-overlap prefix of `body` that repeats the tail of `previous`."""
    for size in range(min(max_overlap, len(body), len(previous)), 0, -1):
        if previous.endswith(body[:size]):
            return body[size:]
    return body


def merge_section(siblings: list[SearchHit]) -> SearchHit:
    """One evidence unit per section: drop repeated 'Section:' lines and overlap duplicates.

    Without this, two 80-char overlaps plus per-chunk headers pushed the packet over budget
    and the recovery rule was truncated to '... below 1% for at' (RESULTS.md, failure F4).
    """
    text = siblings[0].text
    for sib in siblings[1:]:
        body = sib.text.split("\n", 1)[1] if "\n" in sib.text else ""
        text = text.rstrip() + "\n" + _strip_overlap(text.rstrip(), body.strip()).strip()
    meta = dict(siblings[0].metadata)
    meta["merged_chunk_ids"] = ",".join(s.id for s in siblings)
    return SearchHit(siblings[0].id + f"+{len(siblings) - 1}", text, meta, siblings[0].score, "section-merge")


def gather(coll, encoder, role: str, per_query: int = 1, expand_sections: bool = True
           ) -> tuple[list[SearchHit], list[dict]]:
    """Top hit(s) per sub-query (+ their section siblings), de-duplicated, with a coverage log."""
    hits: list[SearchHit] = []
    seen: set[str] = set()
    log = []
    for need, doc_type, query in SUB_QUERIES:
        found = hybrid(coll, encoder, query, role=role, k=3, doc_type=doc_type)[:per_query]
        chosen = [s for h in found for s in (section_siblings(coll, h, role) if expand_sections else [h])]
        for hit in chosen:
            if hit.id not in seen:
                seen.add(hit.id)
                hits.append(hit)
        log.append({"need": need, "doc_type": doc_type, "query": query,
                    "selected": [(h.metadata["doc_id"], h.id[:8], h.method) for h in chosen]})
    return hits, log


def incident_packet(coll, encoder, role: str = "engineer", max_tokens: int = 1200
                    ) -> tuple[ScreenedPacket, list[dict]]:
    hits, log = gather(coll, encoder, role)
    return build_packet(hits, max_tokens), log
