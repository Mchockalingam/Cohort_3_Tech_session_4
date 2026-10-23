# 07 — From retrieved hits to relevant evidence context

**Time: 10 minutes** · **Objective:** Assemble the smallest sufficient, authorised set of sources that supports an answer without exceeding the model's context budget.

## Why top-k is not yet context

Search yields a ranked list of chunks, not a coherent evidence packet. Before generation, engineers should check:

1. **Authorization:** role/tenant still valid at time of retrieval; no source from a retired document.
2. **Relevance:** the passages answer *all* subquestions, not only the first one.
3. **Coverage:** runbook thresholds, approval constraints and post-mitigation monitoring may be in different sources.
4. **Deduplication:** overlapping chunks can consume the budget twice.
5. **Provenance:** attach exact IDs, document versions, page/section and source path.
6. **Budget:** reserve tokens for question, instructions and output; avoid truncating a critical `unless`/`must not` clause.

## Code: build a token-budgeted evidence packet

[`../src/context.py`](../src/context.py) assigns `[S1]`, `[S2]` etc. The IDs are local to **one answer**, so keep their corresponding source manifest in the audit trail.

```python
from src.context import build_packet
from src.embeddings import LocalEncoder
from src.retrieval import hybrid
from src.vector_store import collection

question = "Who approves a P1 rollback and which metrics verify recovery?"
hits = hybrid(collection(), LocalEncoder(), question, role="engineer", k=6)
packet = build_packet(hits, max_tokens=1000)
print(packet.text)
print("Source IDs:", list(packet.sources), "tokens:", packet.token_count)
```

```bash
python -m src.cli context --role engineer --budget 900 --question "Who approves emergency rollback and how is recovery verified?"
```

The workshop's `build_packet` is intentionally simple: it keeps retrieval order and truncates long passages to fit a budget. **It cannot detect lost negations or automatically prove that the combined evidence is sufficient.** For production, prefer clause-aware passage extraction and re-check material facts after trimming.

## More precise multi-hop context: retrieve per subquestion

```python
from src.retrieval import reciprocal_rank_fusion

runbook_hits = hybrid(collection(), LocalEncoder(),
                      "payments database saturation recovery verification",
                      role="engineer", k=4, doc_type="runbook")
policy_hits = hybrid(collection(), LocalEncoder(),
                     "P1 emergency rollback approval requirements",
                     role="engineer", k=4, doc_type="policy")

evidence = reciprocal_rank_fusion([runbook_hits, policy_hits], limit=6)
packet = build_packet(evidence, max_tokens=1200)
print(packet.text)
```

This technique reduces the chance that one dominant topic (e.g. pool saturation) crowds out the change-approval requirement. In a larger design, use a reranker to rerank the union, then apply diversity and clause-completeness checks.

## Parent expansion warning

For small-to-big retrieval, a matched child can identify a parent section. That **parent must be fetched using the same trusted ACL/tenant controls**. Never load a large parent from an unprotected cache merely because a child was accessible; permission labels can differ inside documents.

## Lab checkpoint

Reduce `--budget` to 250 and compare the evidence against 1200 tokens. What condition or approval statement disappears? Can the assistant still deliver a complete, reliable answer? This is why **token budgeting is an evidence-quality decision**, not just a cost optimization.

**Next:** [08 — Grounded answer generation](08-grounded-answer-generation.md).
