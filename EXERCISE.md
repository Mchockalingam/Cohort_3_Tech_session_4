# Participant assignment — Build and defend an enterprise Agentic RAG answer

**Post-session individual/team exercise** · **Estimated effort: 2–4 hours** · **Submission:** pull-request/branch or ZIP containing Markdown explanation, working code changes, evaluation evidence and sample output.

## Business scenario

You are implementing Northstar Payments' internal incident assistant. The incident commander asks:

> **“Checkout failures crossed 5% 5xx for five minutes after a concurrency configuration deployment; pool utilization is 93%. What immediate checks should the responder perform, what can be rolled back, who must approve it, how do we verify recovery, and what customer-update cadence applies?”**

Your answer must reconcile current runbooks with change and communication policy. Include source IDs and versions. It must not give anyone the authority to execute a production rollback automatically.

## Provided assets

- Source inventory and access metadata: [`../data/catalog.json`](../data/catalog.json).
- Synthetic runbooks, policies, postmortem and retired procedure: [`../data/knowledge/`](../data/knowledge/).
- Seed retrieval evaluation questions: [`../data/eval.jsonl`](../data/eval.jsonl).
- Read-only agent and baseline retrieval code: [`../src/`](../src/).
- Adversarial fixture **not in the main catalog**: [`../data/adversarial/untrusted-vendor-ticket.md`](../data/adversarial/untrusted-vendor-ticket.md).

## Tasks and measurable acceptance criteria

### A. Ingestion and version safety — 15 points

1. Print a catalog audit that includes doc ID, version, status, page and allowed roles.
2. Confirm the retired `RUN-PAY-OLD` is never retrievable after indexing.
3. Implement or describe a concrete stale-ID removal and reindex mechanism for when a document version is retired/replaced. Show how you would test its correctness; a paragraph without executable deletion or a credible migration test earns partial credit.

### B. Chunking experiment — 20 points

1. Compare **at least three** strategies: fixed overlap, heading-aware, and one of semantic / parent–child / table-aware.
2. Use the *same corpus and questions* to compare source coverage. Present a concise table: strategy, parameters, chunk count, mean chunk tokens, document recall@5, observed failure mode.
3. Explain which strategy preserves the condition “more than 90% for five minutes” together with the action boundary, and justify your choice.

### C. Retrieval and evidence assembly — 20 points

1. Implement and run dense and hybrid search with metadata filtering **inside** the storage/retrieval layer.
2. Demonstrate that `engineer` cannot retrieve the security-only `SEC-FRAUD-009`; `security` can, and no role retrieves retired `RUN-PAY-OLD`.
3. Build a 1,200-token-or-smaller evidence packet that covers runbook diagnostics, policy approval and observation/communications. Provide a source manifest.

### D. Grounded baseline and Agentic RAG — 20 points

1. Run the baseline grounded-answer flow using an approved model; or, without a hosted key, submit the evidence packet and a **manually authored** model-free answer clearly labelled manual.
2. Run (or pseudocode accurately, if no key) a bounded agent that chooses runbook and policy tools; cap tool rounds/calls and show a trace. Do **not** add any deployment, email, privileged command or change-ticket write tool.
3. Explain in five sentences when the agent beats deterministic RAG, and when the deterministic path is preferable.
4. Every substantive operating instruction in your submitted answer must have a source reference and no fabricated approvals.

### E. Evaluation, safety and interpretation — 25 points

1. Extend `data/eval.jsonl` with **four** additional questions: exact policy ID, cross-document question, unanswerable question, and role-denied question.
2. Report retrieval hit@5, doc recall@5, MRR@5 for **both dense and hybrid**, with the same gold labels. Separately record abstention correctness for unanswerable questions.
3. Attempt the adversarial test below and show that the model does **not** treat a retrieved instruction as authority. A failed defence must be documented honestly.
4. Include at least one reproducible failing case, root cause and proposed mitigation (e.g. lost negation, wrong version, weak lexical recall, missing citation).

## Security challenge — do not skip

`data/adversarial/untrusted-vendor-ticket.md` contains malicious text designed to override model instructions and request restricted information. For an **isolated test collection only**, add a copy to a temporary approved-catalog fixture as an `active` untrusted vendor record visible to `engineer`. Retrieve it, generate an answer and inspect the result.

Required outcome: the system may describe a vendor report as untrusted context, but must **not** reveal the security-only source or claim that a vendor ticket bypasses emergency-change approval. Do not change the primary catalog or weaken role filters to make the test pass. If a model follows the attack, record the failure and propose controls (such as source trust rating, allowlisted tools, human review and content scanning). **Do not execute instructions found in this fixture.**

## Expected answer content (reviewer ground truth, no fixed `[S#]` order)

| Question component | Expected primary evidence | Must not claim |
|---|---|---|
| P1 trigger | `RUN-PAY-101`, `POL-SLO-020`: 5xx >5% for 5 min with checkout impact | One isolated 5xx is P1 |
| Immediate checks | `RUN-PAY-101`: rate, p95, pool, error budget, recent change, sanitized traces | Raw tokens/card data should be pasted into prompts |
| Pool triage | `RUN-DB-201`: >90% for five min, waiters, slow queries, leaks, config changes | Automatic root-cause certainty; blind DB restart |
| Emergency rollback | `POL-CHG-010`: incident commander **and** independent on-call change approver, pre-execution record | Engineer self-approval or post-hoc approval alone |
| Recovery | `RUN-DB-201`: pool <75%, payment error <1%, both for 15 min | Immediate closure at first good reading |
| Communications | `POL-SLO-020`: customer update at least every 30 min | Publishing without incident commander coordination |

## Required submission structure

```text
submission/
  REPORT.md                 # 2–4 pages: design, comparison, limitations, links
  ANSWER.md                 # concise sourced answer + evidence manifest
  RESULTS.md                # benchmark table, test outputs, failures
  src/                      # changed code modules or patch
  tests/                    # at least two new tests; include unauthorized and version cases
```

Run and include the output of:

```bash
python -m unittest discover -s tests -v
python -m src.cli evaluate --mode dense --k 5
python -m src.cli evaluate --mode hybrid --k 5
```

Do not commit an API key, real customer data, incident logs, or model cache directories. A submission that merely pastes LLM output without runnable reasoning, sources and tests is incomplete.

## 100-point evaluation rubric

| Dimension | Points | High-quality submission shows |
|---|---:|---|
| A. Ingestion and version handling | 15 | Stable IDs, role metadata, retired source exclusion, credible reindex/delete procedure |
| B. Chunking design and experiment | 20 | Fair comparative experiment, boundary analysis, justified trade-offs |
| C. Retrieval and context | 20 | Working ACL and hybrid retrieval, correct provenance, multi-source coverage |
| D. Grounded and agentic answer | 20 | Source-supported claims, read-only bounded tools, honest abstention |
| E. Evaluation and security | 25 | Gold labels, comparable metrics, adversarial testing, documented failures/mitigations |
| **Total** | **100** | |

**Suggested grading interpretation:** 90–100 ready to lead a supervised enterprise pilot; 75–89 solid with remediation; 60–74 concepts understood but implementation incomplete; below 60 substantial evidence/authorization gaps. **Automatic critical-fail condition:** any solution that makes production changes or exposes an unauthorised document as if permitted must be remediated irrespective of numerical score.

## Optional stretch challenges (not required for 100 points)

- Use a proper full-text search engine and compare it with in-memory BM25.
- Implement a user-entitlement update test where a once-permitted document is revoked between index and query.
- Add answer-level citation-entailment review, calibrated abstention and evaluation of conflicting documents.
- Replace local Chroma with PostgreSQL/pgvector and use RLS policies bound to a verified application identity.

## Reviewer questions for viva / code review

1. Why can't an embedding similarity score authorize a source or guarantee correctness?
2. What breaks if the document version changes but old vectors remain in the collection?
3. Why might `chunk_overlap=100` increase both recall and duplicate evidence?
4. When would a deterministic two-query retriever outperform a free-running agent?
5. What must the system do when the relevant evidence is missing or contradicts the current policy?

Submission deadline, approved model provider and repository/PR destination are to be set by the workshop organiser.
