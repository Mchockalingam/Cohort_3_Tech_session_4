# REPORT — Northstar incident assistant: enterprise Agentic RAG

**Deliverables:**
- [ANSWER.md](ANSWER.md): the sourced answer and evidence manifest.
- [RESULTS.md](RESULTS.md): benchmarks, test output and failures.
- [`src/`](src/): code.
- [`tests/`](tests/): 17 tests.
- [`data/eval.jsonl`](data/eval.jsonl): extended gold set.
- [`outputs/`](outputs/): raw evidence.

## 0. How to run it (from the workshop root)

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s submission/tests -t . -v      # 17 tests, offline, no model download
python -m submission.src.cli audit                           # A.1 catalog audit
python -m submission.src.cli reindex                         # A.3 version-safe (re)index + verification
python -m submission.src.cli evaluate --mode dense  --k 5    # E.2
python -m submission.src.cli evaluate --mode hybrid --k 5    # E.2
python -m submission.src.cli abstention                      # E.2 abstention correctness
python -m submission.src.cli acl-demo                        # C.2
python -m submission.src.cli incident-packet                 # C.3 evidence packet + manifest
python -m submission.src.cli offline-agent                   # D.2 bounded agent trace (no key)
python -m submission.src.cli adversarial                     # E.3 isolated injection test
python -m submission.src.cli chunk-experiment                # B
python -m submission.src.repro_truncation                    # E.4 failure F4 reproduction
# With an approved key: `answer` (D.1) and `agent` (D.2, LLM planner)
```

**Constraint I followed:** the workshop's existing files are **not modified**; `git diff` on
`src/`, `tests/` and `data/` is empty. `submission/src` imports the original `src` package and
wraps it. It uses its own index (`submission/.chroma`) and its own copy of the gold set.

## 1. Design

```text
data/catalog.json ──► original load_catalog ──► loader.py (POSIX path, trust=trusted default)
                                                       │ heading-aware chunks (550/80), id = sha256(doc,version,page,strategy,i,text)
                                                       ▼
                     store.py  upsert (active only) · stale_ids · reindex · verify_index
                                                       │  metadata: tenant, status, role_<r> booleans, doc_type, version, trust
                                                       ▼
   role (from session) ─► retrieve.py: original dense / BM25 / RRF with ACL in Chroma `where`
                                       + enforce_authorized() fail-closed re-check
                                                       ▼
   incident.py: 7 fixed sub-queries (doc_type filtered) ─► section merge ─► packet.py
                 (quarantine untrusted + instruction-like · trust label · drop-not-truncate · ≤1,200 tokens · manifest)
                                                       ▼
   generation (original grounded_answer, needs key) / MANUAL answer  ──► citation + policy guards
   agent.py: LLM or rule planner ─► ToolDispatcher (3 read-only tools, ≤5 calls, ≤3 rounds, role fixed by code)
```

**Version safety (A).** There are three independent controls:
- `upsert_chunks` writes only `status == "active"` records.
- The query filter requires `status == active`.
- `reindex()` makes the store **exactly** match the current catalog.

Chunk IDs hash `doc_id + version + text`, so a new version produces new IDs. `stale_ids()` then
finds:
- every ID that is no longer in the active chunk set, which covers replaced, retired, removed or
  edited content;
- every ID whose stored metadata has drifted from what it should be, which covers an ACL
  revocation where text and version stay the same.

`reindex` deletes those IDs **before** upserting, then runs `verify_index`. That check asserts
that the store IDs equal the active chunk IDs and that no non-active record exists, and it raises
if either fails. Tests cover v1→v2 replacement, retirement to an empty collection, idempotency
and revocation.

In production, I would build into a new collection, verify it, then switch an alias (blue/green),
so a query never sees a half-migrated index.

**Authorisation (C).** The role comes from the caller's session and never from the model or the
query text. The tenant/status/role/doc_type predicate runs **inside Chroma** before ranking, and
for BM25 the authorised set is fetched before scoring. That is the original workshop design, and
I kept it.

On top of it I added `enforce_authorized`, which re-checks every returned record and raises
`PermissionError` instead of serving a leak. It is defence in depth against a filter bug.

The tool dispatcher rejects any argument except `query`, so a model can't smuggle in
`role: security`.

**Evidence assembly (C.3).** One broad query returned four chunks of RUN-PAY-101 and missed the
policies; this is the same effect as failure F1. Instead, `incident.py` runs 7 fixed sub-queries,
one per evidence need, each restricted by `doc_type` in the store. When a hit belongs to a
heading section that was split, its **siblings are fetched through the same ACL filter and
merged**, with overlap removed, so a numbered procedure is never cut in half.

The packet builder **drops rather than truncates**. In failure F4 the original truncation turned
"for at least 15 minutes" into "for at", which removed the safety condition. The result is 7
whole sources, 995 tokens, covering all six ground-truth components.

**Injection controls (E.3).** There are four layers:
1. Catalog **trust rating**: vendor content is `untrusted`.
2. Regex **content scan**: untrusted sources that match are quarantined. Trusted policy text is
   kept even when it says "do not bypass approval".
3. An in-band `trust=UNTRUSTED` label on anything untrusted that does reach the packet.
4. Output guards: citation whitelist, approval-bypass phrasing and a canary leak check.

The primary guarantee isn't the regex. The restricted document is **unretrievable** for
`engineer` at the store, so no prompt trick can make the model reveal text it never received.

## 2. Chunking decision (B)

Full table: RESULTS §3. On this corpus every strategy reaches dense doc-recall@5 = 0.938. The
only miss is q10, caused by the postmortem crowding out other documents, not by chunking. So
recall alone **doesn't separate** the strategies, and the boundary analysis decides.

**Choice: heading-aware chunking (550 chars, overlap 80, heading-path prefix), plus section
merge at retrieval time.**
- **It keeps condition and boundary together.** "Exceeds 90% for five minutes … not authority to
  restart the database" (RUN-PAY-101) and "greater than 90% … not definitive root cause"
  (RUN-DB-201) each stay in one chunk. Semantic chunking separated the RUN-PAY-101 pair: the two
  sentences differ enough in embedding space (similarity < 0.72) that the threshold split them.
  For an operations assistant, that is the worst failure: the model gets the trigger without the
  prohibition.
- **The prefix travels with every chunk.** Each chunk carries
  `Section: Database Connection Pool Saturation Runbook > Triage sequence`. That helps BM25 and
  dense retrieval, and it lets a reviewer place a citation.
- **Its weakness is fixable and visible.** Long numbered lists split across chunks. Instead of
  making chunks bigger (worse precision) or using fixed parents (parent–child: ~3× larger units
  and duplicate children), I merge siblings of the **same section only**. That is a
  structure-defined parent.
- Fixed-overlap chunking also kept both boundaries, but only by luck of offsets: a different size
  would cut either one. It has no section context, and its overlap duplicates evidence.

**Viva Q3 (overlap=100).** Overlap copies text from the end of one chunk to the start of the
next. That raises recall, because a fact near a boundary appears whole in at least one chunk. It
also creates duplicate evidence: two hits carry the same sentence, which wastes budget and can
look like two corroborating sources. That is exactly what pushed the packet over budget in F4.
Merging with overlap removed fixes both problems.

## 3. Grounded baseline and agent (D)

**D.1.** There was no approved model key, so ANSWER.md is a **manual, model-free answer** written
only from the packet. It passes `citation_issues` (all `[S#]` are in S1–S7) and
`answer_policy_violations` (no bypass claim, no canary). It claims no approval has happened and
authorises nothing. With a key, `python -m submission.src.cli answer` runs the original
`grounded_answer` on the same packet and applies both guards.

**D.2.** `agent.py` has one `ToolDispatcher` that both planners use: the LLM planner (`run_agent`,
the original Responses-API loop) and a rule-based offline planner.
- **Allowlist:** `search_runbook`, `search_policy`, `search_postmortem`. These are the original
  read-only tools; no deploy, email, shell, SQL or ticket-write tool exists.
- **Bounds:** ≤ 3 rounds and ≤ 5 calls.
- **Trace:** RESULTS §5. Five searches succeeded. `deploy_rollback` was **DENIED** (not on the
  allowlist), and the 6th call was **DENIED** (budget).

**D.3. When the agent wins, and when deterministic wins:**
1. An agent beats deterministic RAG when the evidence needs are **not known in advance**: an
   unfamiliar symptom, or a first result that points somewhere new (e.g. RUN-PAY-101 says "read
   RUN-DB-201"), so a follow-up query can be planned from what was found.
2. It also helps with cross-source questions whose split isn't obvious. Choosing runbook vs
   policy tools per sub-question avoided the q10 crowding failure that one similarity query
   suffered.
3. For a **known, recurring, high-stakes question** like this P1 template, a fixed set of
   sub-queries is preferable: it is reproducible, testable (`test_incident_packet_*`), cheaper,
   and it can't skip the approval-policy search on a bad sampling day.
4. Deterministic is also safer under attack, because retrieved text can't change which tools run
   next, while an agent's plan is influenced by the untrusted content it reads.
5. In practice I would use the deterministic packet as the guaranteed floor and let a bounded
   agent add optional follow-up searches, never replace the mandatory policy retrieval.

## 4. Evaluation summary (E)

There are four new gold questions:
- q09: exact policy ID.
- q10: cross-document.
- q11: unanswerable.
- q12: role-denied for `manager`, with SEC-FRAUD-009 forbidden.

Results:
- **Dense:** hit@5 1.000 · recall@5 0.938 · MRR 1.000.
- **Hybrid:** hit@5 1.000 · recall@5 0.938 · MRR 0.771.
- **Leaks:** 0 forbidden-document leaks in either mode.
- **Abstention:** 4/4 correct, 0/8 false abstentions at a dense ≥ 0.40 gate. The threshold was
  tuned on the same questions (thin 0.318 / 0.475 margin), so the report does not count this as
  validated.

**Hybrid is worse than dense here.** That is a real finding (F2): equal-weight RRF lets BM25's
term-frequency favourite overtake dense's correct first result. Hybrid should earn its place on
the exact-ID and rare-term questions where dense is weak, and on this corpus the exact-ID question
q09 is already solved by dense. I'd keep hybrid behind a weighted RRF plus a reranker rather than
use it by default.

## 5. Limitations

- **No model generation ran.** The adversarial test shows the restricted source can't reach the
  model and that the attack is labelled or quarantined. It does **not** show how an LLM behaves
  given the unscreened packet. That must run with an approved key before a pilot.
- **The evaluation is tiny.** There are 12 questions and 6 documents, so metrics saturate and one
  question decides every comparison. Thresholds (abstention 0.40, semantic 0.72) are tuned, not
  validated.
- **The regex injection scan is easy to evade** (paraphrase, encoding, other languages). It is one
  layer only. The real controls are trust ratings, store ACLs, read-only tools and human approval.
- **Citation checking is not entailment checking.** A valid `[S5]` can still be attached to a
  claim S5 doesn't support. Answer-level entailment review is the next control to add.
- **The fixed sub-queries are tuned to this incident template** (F3 showed how query wording
  interacts with RRF ties). New templates need their own coverage tests.
- **Boolean role flags are a teaching ACL.** Production needs authoritative entitlements bound to
  a verified identity (e.g. pgvector + row-level security). It also needs re-validation at query
  time: an index built before a revocation is only safe if `reindex` runs.
- **One original workshop test fails on Windows** (backslash `source_path`). I documented it and
  did not edit the original.

## 6. Viva questions

1. **Why can't similarity authorise a source or guarantee correctness?** Similarity measures
   topical closeness. It knows nothing about entitlement, status or truth. The retired
   RUN-PAY-OLD is *very* similar to rollback questions, and q11 still gets a 0.306 nearest
   neighbour with no answer present. Authorisation must come from metadata filters bound to
   identity, and correctness from source status plus citation review.
2. **What if versions change but old vectors stay?** Retrieval can return the superseded
   instruction (e.g. "restart the database without approval") next to the current one, as an
   equally cited source. The model may follow it or blend the two. Revoked ACLs also keep working
   until the old record is rewritten. This is why `stale_ids` checks metadata drift as well as IDs.
3. **Why does overlap=100 raise both recall and duplicates?** See §2: boundary facts appear whole
   at least once, but they also appear twice, which wastes budget and fakes corroboration.
4. **When does a deterministic two-query retriever beat a free agent?** When the evidence needs
   are known and mandatory (runbook + approval policy here). It's reproducible, cheaper, can't
   skip the policy search, and can't be steered by injected text. See §3.
5. **What if evidence is missing or contradicts current policy?** Abstain or say explicitly what
   is missing (the dense gate, and the original `ABSTAIN` text). Prefer the active, latest-version
   source, never a retired one. Surface the conflict, with both source IDs and versions, to the
   incident commander instead of resolving it silently. Never invent the missing approval or
   threshold.
