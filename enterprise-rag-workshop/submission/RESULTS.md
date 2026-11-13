# RESULTS — benchmarks, test outputs and failures

**Environment:**
- Windows 11, Python 3.13.14, chromadb 1.5.9, sentence-transformers 5.7.0.
- Embedding model: `all-MiniLM-L6-v2`, run locally on CPU.
- No hosted LLM key, so no generation was run.

Raw outputs are in [`outputs/`](outputs/). Every number below is copied from those files.

## 1. Required commands

### `python -m unittest discover -s tests -v` (original workshop tests, unmodified code)
```
Ran 10 tests ... FAILED (failures=1)
FAIL: test_catalog_has_roles_and_retired_document
    self.assertTrue(all(d.metadata["source_path"].startswith("data/") for d in docs))
AssertionError: False is not true
```
This is a bug in the workshop code that shows up on Windows. The original
`src/loading.py` builds `source_path` with `str(Path)`, which produces `data\knowledge\...`. I
did **not** edit the original file. `submission/src/loader.py` normalises paths to POSIX form,
and `test_loader_wrapper_gives_portable_paths_and_trust` covers that. Full output:
`outputs/r1_original_unittest.txt`.

### Submission tests: `python -m unittest discover -s submission/tests -t . -v`
```
Ran 17 tests in 4.964s
OK
```
Full output: `outputs/00_submission_unittest.txt`. The tests include an **unauthorised-access**
case (`test_engineer_cannot_but_security_can_retrieve_sec_fraud`) and a **version** case
(`test_retired_run_pay_old_never_indexed_or_retrieved`,
`test_reindex_removes_replaced_version_and_retirement`).

### `python -m src.cli evaluate --mode dense|hybrid --k 5` (original code, original 8 questions)
| Mode | hit@5 | doc recall@5 | MRR@5 |
|---|---:|---:|---:|
| dense | 1.000 | 1.000 | 1.000 |
| hybrid | 1.000 | 1.000 | **0.778** |

Full output: `outputs/r2_*.json` and `outputs/r3_*.json`.

## 2. Retrieval benchmark on the extended gold set (Task E.2)

Command: `python -m submission.src.cli evaluate --mode dense|hybrid --k 5`. Both modes use the
same gold labels (`submission/data/eval.jsonl`) and the same index (28 heading chunks). Scores
cover the 8 questions that have expected sources.

| Mode | hit@5 | doc recall@5 | MRR@5 | Forbidden-doc leaks | Median latency |
|---|---:|---:|---:|---:|---:|
| **dense** | **1.000** | 0.938 | **1.000** | **0** | 49 ms |
| hybrid (RRF k=60) | 1.000 | 0.938 | 0.771 | **0** | 63 ms |

Per question (dense recall / RR, then hybrid recall / RR):

| ID | Category | Role | Dense R / RR | Hybrid R / RR | Note |
|---|---|---|---|---|---|
| q01 | seed | engineer | 1.0 / 1.0 | 1.0 / 1.0 | |
| q02 | seed | engineer | 1.0 / 1.0 | 1.0 / **0.333** | BM25 ranks RUN-PAY-101 first (F2) |
| q03 | seed | engineer | 1.0 / 1.0 | 1.0 / 1.0 | |
| q04 | seed | operator | 1.0 / 1.0 | 1.0 / **0.333** | BM25 ranks RUN-PAY-101 first (F2) |
| q05 | seed | manager | 1.0 / 1.0 | 1.0 / 1.0 | |
| q06 | seed | security | 1.0 / 1.0 | 1.0 / 1.0 | security role can see SEC-FRAUD-009 |
| q09 | **exact policy ID** | engineer | 1.0 / 1.0 | 1.0 / 1.0 | |
| q10 | **cross-document** | engineer | **0.5** / 1.0 | **0.5** / 0.5 | POL-CHG-010 missing (F1) |
| q07, q08, q11 | unanswerable | engineer | — | — | scored by the abstention gate below |
| q12 | **role-denied** | manager | — | — | SEC-FRAUD-009 never returned |

`forbidden_leak_count = 0` in both modes. Across all 12 questions, no non-security role ever
received SEC-FRAUD-009, and no role received RUN-PAY-OLD.

### Abstention correctness (separate, Task E.2)

Command: `python -m submission.src.cli abstention`. The gate abstains unless the best
**authorised** chunk has cosine similarity ≥ 0.40.

| Gate | Correct abstentions (should abstain) | False abstentions (answerable) |
|---|---:|---:|
| v1: dense ≥ 0.45 **and** ≥ 50% content-word overlap | 4/4 | **3/8** (q02, q04, q10) |
| **v2: dense ≥ 0.40** | **4/4** | **0/8** |

Top-1 dense scores: unanswerable and role-denied questions max out at **0.318** (q12);
answerable questions start at **0.475** (q04). The margin is thin, and the 0.40 threshold was
**chosen on these same 12 questions**. Treat it as tuned, not validated. It needs a held-out
calibration set before any pilot. Outputs: `outputs/08a_*` (v1) and `outputs/08_abstention.json`
(v2).

## 3. Chunking experiment (Task B)

Command: `python -m submission.src.cli chunk-experiment`.
- Same 6 active documents, same 8 answerable questions, k=5.
- Each strategy gets its own in-memory collection.
- Token counts use `o200k_base`.

| Strategy | Parameters | Chunks | Mean tok | Max tok | Dense doc-R@5 | Hybrid doc-R@5 | ">90% for 5 min" kept with its boundary? | Observed failure mode |
|---|---|---:|---:|---:|---:|---:|---|---|
| Fixed overlap | 550 chars, overlap 80 | 17 | 76.1 | 119 | 0.938 | 0.938 | Yes / Yes | Chunks start mid-sentence with no section context, and the overlap repeats ~20 tokens per boundary; q10 misses POL-CHG-010 |
| **Heading-aware** | ≤550 chars, overlap 80, heading-path prefix | 28 | 54.0 | 107 | 0.938 | 0.938 | Yes / Yes | Long numbered lists ("First ten minutes", "Triage sequence") split into 2 chunks, so a retrieved chunk can carry half a procedure; q10 misses POL-CHG-010 |
| Parent–child | child 350 (indexed), parent 1400 (returned) | 22 | 51.4 (parents 163.3) | 71 | 0.938 | **1.000** | Yes / Yes | The returned unit is ~3× larger, and several children of one parent fill the top-k with duplicates |
| Semantic | MiniLM sentence similarity < 0.72 starts a new chunk, ≤550 | 70 | 16.4 | 45 | 0.938 | **1.000** | RUN-PAY-101: **No** / RUN-DB-201: Yes | Sentence-sized fragments; RUN-PAY-101's "exceeds 90% for five minutes" lands in a different chunk from "not authority to restart the database" |
| Table-aware | ≤550 chars, tables atomic | 47 | 23.8 | 90 | 0.938 | 0.938 | Yes / Yes | The corpus has no tables, so it behaves like a paragraph splitter |

The boundary column checks whether one chunk contains **both** the condition **and** its action
boundary:
- RUN-PAY-101: "exceeds 90% for five minutes" + "not authority to restart the database".
- RUN-DB-201: "greater than 90% utilization for five minutes" + "not definitive root cause".

The corpus is only 6 documents, so recall saturates. One question (q10) accounts for every
difference.

## 4. Version safety and ACL evidence (Tasks A, C.2)

- **Audit** (`outputs/01_audit.txt`): 7 page records. Only `RUN-PAY-OLD` (retired) has
  `indexed=False`.
- **Reindex** (`outputs/02_*.txt`): a clean build gives `{"deleted": 0, "added": 28}`. Running it
  again gives `{"deleted": 0, "added": 0, "unchanged": 28}`, which shows it is idempotent. Both
  runs end with `verify_index` passing.
- **Replaced or retired versions** (unit tests):
  - When v1→v2 changes, exactly the v1 IDs are deleted and only `version == "2.0"` remains.
  - Retiring v2 leaves the collection at count 0.
  - When `allowed_roles` is revoked with the same text and version, the record is detected as
    metadata drift and rewritten, and `engineer` immediately loses access. This covers the
    "entitlement revoked" stretch challenge.
- **ACL demo** (`outputs/05_acl_demo.txt`): 3 probes × 4 roles × 3 modes = 36 checks.
  - `SEC-FRAUD-009` is RETRIEVED only for `security`, in all 3 modes and for both probes.
  - It is blocked for `engineer`, `operator` and `manager`.
  - `RUN-PAY-OLD` is blocked for **every** role in every mode.

## 5. Agent trace (Task D.2)

Command: `python -m submission.src.cli offline-agent` (`outputs/07_offline_agent.txt`). The
planner is rule-based because there is no key. The dispatcher is the same code the LLM agent
uses.

| Round | Tool | Status | Docs returned |
|---|---|---|---|
| 1 | search_runbook ("P1 … first ten minutes checks") | ok | RUN-PAY-101 ×4 |
| 1 | search_runbook ("pool >90% five minutes triage") | ok | RUN-DB-201 ×3, RUN-PAY-101 |
| 1 | search_policy ("emergency rollback approval …") | ok | POL-CHG-010 ×3, POL-SLO-020 |
| 2 | search_runbook ("verify <75% <1% 15 minutes") | ok | RUN-DB-201 ×2, RUN-PAY-101 ×2 |
| 2 | search_policy ("customer update every 30 minutes") | ok | POL-SLO-020 ×3, POL-CHG-010 |
| 2 | **deploy_rollback** | **DENIED: not on read-only allowlist** | — |
| 3 | search_postmortem | **DENIED: call budget 5 exceeded** | — |

Limits: 3 rounds, 5 successful calls, 15 unique sources, no generated advice. The tool
allowlist is `search_runbook`, `search_policy` and `search_postmortem` only.

## 6. Adversarial test (Task E.3)

Command: `python -m submission.src.cli adversarial` (`outputs/09_adversarial.json`). It uses an
isolated in-memory collection. The temporary catalog copies the trusted corpus and adds
`VENDOR-TKT-001` with `status=active`, `trust=untrusted` and `allowed_roles=[engineer]`. The
primary catalog is untouched, and the temporary directory is deleted after the run.

| Check | Q1 "pool exhausted, what should the engineer do?" | Q2 "what does the vendor ticket say …?" |
|---|---|---|
| Vendor ticket retrieved | yes (rank 2) | yes (rank 1) |
| SEC-FRAUD-009 retrieved for engineer | **no** | **no** |
| Canary `violet-sparrow-47` present in packet | **no** | **no** |
| Injection patterns found | ignore-instructions, disclose-restricted, bypass-approval | same |
| Vendor ticket labelled `trust=UNTRUSTED` (unscreened packet) | yes | yes |
| Screened packet | vendor **quarantined**; RUN-PAY-101, RUN-DB-201, PM-2026-071 kept | vendor **quarantined** |

**Honest limit:** no model generation ran, because there was no key. The test proves two things:
the restricted source **cannot** reach the model, because the store ACL blocks it, and the attack
text is labelled or removed before prompting. It does **not** prove how a model would behave when
shown the unscreened packet. With a key, the same command passes the **unscreened** worst-case
packet to `grounded_answer` and checks the answer with `answer_policy_violations` (canary leak and
approval-bypass claims). The manual answer in ANSWER.md passes that guard.

## 7. Failures: reproducible case, root cause, mitigation (Task E.4)

| # | Failure | Reproduce | Root cause | Mitigation | Status |
|---|---|---|---|---|---|
| **F1** | Cross-document q10: doc recall@5 = **0.5** (POL-CHG-010 missing) in dense **and** hybrid | `python -m submission.src.cli evaluate --mode dense` → row q10 | One query, top-k by similarity only. The postmortem PM-2026-071 tells the same story (concurrency change, pool, rollback, approval) and takes 2–3 of the 5 slots | Separate sub-queries filtered by doc_type inside the store (`incident.py`), or per-document diversity (MMR / max 2 chunks per doc) | **Mitigated** in the incident packet; still open for single-query search |
| **F2** | Hybrid MRR 0.771 vs dense 1.000 (q02, q04 drop to RR 0.333) | `… evaluate --mode hybrid` → q02, q04 | Equal-weight RRF lets BM25's term-frequency favourite (RUN-PAY-101 repeats "P1", "database", "connection") outrank dense's correct #1 | Weighted RRF (dense-weighted), a cross-encoder reranker, field-boosted BM25 | Open, documented |
| **F3** | RRF tie (0.032 = 0.032) settled by chunk-hash ID, so "First ten minutes" was dropped from the packet | earlier `immediate_checks` query that included pool terms (see the comment in `incident.py`) | `reciprocal_rank_fusion` sorts ties by `id`, which is effectively random with respect to relevance | Remove confounding terms from the sub-query; break ties on dense score; detect ties and log them | Mitigated by the query fix; tie-break still open |
| **F4** | Packet **truncated** the recovery rule to "…below 1% for at", **losing "15 minutes"** | `python -m submission.src.repro_truncation` → `outputs/06b_truncation_repro.txt`; `test_packet_drops_rather_than_truncates` | The original `build_packet` cuts the last source to fit the budget (10 sources, 1,195 tokens); 80-char overlaps and per-chunk headers wasted ~200 tokens | **Drop, never truncate** (`truncate=False`). On its own that drops RUN-DB-201 recovery entirely (repro line 2), so section siblings are also merged with overlap removed (`merge_section`) | **Fixed**: 7 sources, 995 tokens, all whole |
| F5 | Abstention v1 refused 3/8 answerable questions | `outputs/08a_*` | The word-overlap requirement penalises paraphrases ("diagnose" vs "inspect") | Dense-only gate; calibrate on held-out data | Fixed on this set; overfitting risk noted |
| F6 | Original `test_core` fails on Windows | `python -m unittest discover -s tests` | `str(Path)` gives backslashes | POSIX normalisation in `submission/src/loader.py` | Worked around; original not edited |
| F7 | BM25 returns nothing on a 1-document corpus | `test_entitlement_revoked_between_index_and_query` (filler docs) | Okapi IDF ≤ 0 when a term appears in every document | Don't use BM25 alone on tiny filtered subsets; fall back to dense | Documented |
