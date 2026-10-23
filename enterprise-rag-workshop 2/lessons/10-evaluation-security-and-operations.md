# 10 — Evaluation, security, performance and operational readiness

**Time: 10 minutes** · **Objective:** Define measurable acceptance criteria before treating a working prototype as an enterprise system.

## Evaluate the right subsystem

RAG failures should be localised instead of giving one subjective “answer quality” score:

| Layer | Suggested measures | Failure example |
|---|---|---|
| Ingestion | Source coverage, parse accuracy, stale version count, ACL sync lag | Old rollback procedure indexed |
| Chunking | Boundary integrity, table preservation, duplicate rate, chunk size distribution | Approval exception separated from rule |
| Retrieval | Doc recall@k, hit@k, MRR, authorized-source violations | Finds symptoms but misses approval policy |
| Context | Complete evidence coverage, evidence tokens, provenance completeness | Correct passage truncated before “must not” |
| Generation | Correctness, citation entailment, unsupported claim rate, abstention accuracy | Fabricated change-approval exception |
| Agent | Tool selection quality, tool-call success, median/p95 latency, cost/answer | Repeats search needlessly; crosses scope |

## Code: run a labelled retrieval benchmark

The synthetic gold questions in [`../data/eval.jsonl`](../data/eval.jsonl) specify expected supporting document IDs and caller roles.

```python
from src.embeddings import LocalEncoder
from src.evaluation import retrieval_report
from src.vector_store import collection

report = retrieval_report(collection(), LocalEncoder(), mode="hybrid", k=5)
print("Hit@5:", report["mean_hit_at_k"])
print("Document Recall@5:", report["mean_doc_recall_at_k"])
print("MRR@5:", report["mrr_at_k"])
```

```bash
python -m unittest discover -s tests -v
python -m src.cli evaluate --mode dense --k 5
python -m src.cli evaluate --mode hybrid --k 5
```

**Definitions:** hit@k = 1 when at least one gold document is among the k retrieved results; doc recall@k = fraction of gold document IDs returned; MRR = reciprocal rank of the first relevant result, averaged over answerable questions. Our evaluator excludes questions without expected sources from these three metrics, because **answer-level abstention** must be tested separately. It reports latency for inspection; the sample is too small for a statistically meaningful SLO.

## Build an answer-level test set

For each evaluation case, label expected answer claims, required citations, exact disallowed claims and whether abstention is required. Score with human review or an independently validated rubric/LLM evaluator. Run separate adversarial tests for malicious text inside retrieved documents and for cross-role information exposure.

## Threats and controls (minimum)

| Risk | Practical control |
|---|---|
| Cross-tenant data leakage | Verified identities, strict tenant isolation, pre-retrieval entitlement filters, negative access tests |
| Stale/poisoned knowledge | Trusted connector, document review, content hashes, revocation, signed source metadata, tombstone deletions |
| Indirect prompt injection | Treat retrieved text as data, least-privilege tools, no model-controlled credentialed actions, output validation |
| Sensitive data in prompts/logs | PII and secret filtering, restricted logging, provider/data residency review, encryption and retention policy |
| Wrong operational instructions | Citations, human review at critical steps, fresh runbooks, evidence verification and abstention |
| Excessive agency | Tool allowlists, bounded rounds/costs, human gates and read-only default |
| Availability and cost | Rate limits, caches with ACL awareness, batch indexes, timeouts, monitoring and fallback mode |

OWASP specifically identifies **prompt injection** and **vector/embedding weaknesses** as distinct RAG risks; retrieving a document does not make the content trustworthy.

## Suggested decision gate before enterprise pilot

The following thresholds are **facilitator-proposed acceptance targets, not external benchmarks**:

- 100% of adversarial role/tenant access tests block unauthorised source IDs.
- 100% of active/retired version tests exclude retired content.
- Retrieval doc recall@5 of at least **0.90 on a representative, sufficiently large labelled set** (not the eight toy questions alone).
- At least **0.95** claim-level support/citation correctness on a human-reviewed evaluation set; no material hallucinations for safety-critical procedures.
- Documented p95 latency, cost/query and incident escalation path, measured on the target workload.
- Human approval required for every high-impact production action, with auditability.

## End-of-session demonstration

Ask one participant to trace a tool result back to its source and version; another to demonstrate a denied role, and a third to explain why “high similarity” does not justify executing a rollback.

**Assignment:** [Participant exercise and review rubric](../exercises/PARTICIPANT_EXERCISE.md). **Sources:** [references.md](../references.md).
