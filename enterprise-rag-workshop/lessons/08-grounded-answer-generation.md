# 08 — Generate grounded answers, citations and abstentions

**Time: 15 minutes** · **Objective:** Turn authorised passages into a helpful answer while exposing unsupported claims and source attribution.

## Grounded generation contract

For incident operations, a good answer should say *what is evidenced, which source supports it, and what cannot be concluded*. It should not invent a rollback approval, treat a retired policy as current, or present likely-but-unsourced troubleshooting guesses as enterprise policy.

An evidence-backed answer to our case should refer to:

- P1 detection/diagnostic checks in `RUN-PAY-101` and `RUN-DB-201`.
- Independent incident commander and on-call change approver in `POL-CHG-010`.
- Recovery observation after mitigation in `RUN-DB-201`.
- Customer update cadence in `POL-SLO-020`, if the question asks about communications.

The exact source IDs `[S1]` etc. vary with the retrieved order; never hard-code them into a final response.

## Code: a grounded answer from retrieved context

The implementation in [`../src/generation.py`](../src/generation.py) uses the current OpenAI Responses API. It calls `store=False` but enterprise retention, residency and data-handling policies still require separate approval.

```python
from src.context import build_packet
from src.embeddings import LocalEncoder
from src.generation import grounded_answer, citation_issues
from src.retrieval import hybrid
from src.vector_store import collection

question = "Who approves rollback and how do we verify recovery?"
hits = hybrid(collection(), LocalEncoder(), question, role="engineer", k=6)
packet = build_packet(hits, max_tokens=1200)
answer = grounded_answer(question, packet)  # OPENAI_API_KEY + OPENAI_MODEL
print(answer)
print("Citation-ID issues:", citation_issues(answer, set(packet.sources)))
```

CLI:

```bash
export OPENAI_API_KEY="your-approved-key"
export OPENAI_MODEL="gpt-4.1-mini"
python -m src.cli answer --role engineer \
  --question "What should we check and who can approve emergency rollback during P1 pool saturation?"
```

### Why the prompt is defensive but not sufficient

The system instructions tell the model to treat retrieved passages as untrusted reference text and to cite significant operational claims. The code also rejects **unknown citation IDs**. This is only a syntactic check: it cannot prove that the cited passage actually entails the claim, nor can it reliably stop an indirect prompt injection by itself. Production controls must also enforce authorization, tool permissions, content validation and post-generation review.

The underlying request is equivalent to:

```python
from openai import OpenAI

response = OpenAI().responses.create(
    model="gpt-4.1-mini",
    instructions="Only answer from supplied source evidence; cite [S#]; abstain if insufficient.",
    input="QUESTION:\n...\nAUTHORISED EVIDENCE:\n[S1] ...",
    store=False,
)
print(response.output_text)
```

The complete project prompt is more explicit about read-only behavior, evidence/data boundaries and incident approvals.

## Abstention behavior

There are two distinct no-answer situations:

1. **No permitted evidence retrieved:** the code directly returns `I don't have enough authorised evidence ...` without a model call.
2. **Some passages retrieved but none prove the answer:** the model is instructed to decline; this is **not yet a deterministic guarantee**. Use an answerability test and a human-reviewed gold set.

Test these questions after indexing:

```bash
python -m src.cli answer --role engineer --question "What is the CEO's private mobile number?"
python -m src.cli answer --role engineer --question "What is the restricted fraud verification phrase?"
```

The restricted phrase is deliberately fake and publicly visible in the synthetic GitHub fixture; the lesson tests **retrieval ACL enforcement**, not real secrecy. Record whether the answer abstains and whether the restricted source appears in the context (it must not).

## A practical grounding review

For every answer, check: claim correctness against approved sources, missing qualifications, correct source IDs, contradiction handling, no stale/forbidden source, honest uncertainty, and no implied execution of an operational action.

**Next:** [09 — Agentic RAG](09-agentic-rag.md). [OpenAI API references](../references.md).
