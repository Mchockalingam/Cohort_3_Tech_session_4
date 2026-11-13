# ANSWER — Northstar Payments incident question

> **MANUAL ANSWER — model-free.** No approved hosted-model key was available, so the answer was
> written by hand **only** from the evidence packet below (`outputs/06_incident_packet.txt`),
> as permitted by Task D.1. Every operating instruction cites a packet source `[S#]`.
> **This assistant is advisory and read-only. Nothing here authorises or executes a production change.**

**Question (incident commander):** Checkout failures crossed 5% 5xx for five minutes after a
concurrency configuration deployment; pool utilization is 93%. What immediate checks should the
responder perform, what can be rolled back, who must approve it, how do we verify recovery, and
what customer-update cadence applies?

## Answer

**1. Severity.** This meets the P1 trigger: more than 5% HTTP 5xx for five consecutive minutes,
with material checkout impact. A single failed request would not qualify [S1]. Start the incident
bridge and assign an incident commander [S1].

**2. Immediate checks (first ten minutes)** [S2]:
- Acknowledge the P1 page within ten minutes and record the incident ID.
- On the approved dashboards, check request rate, 5xx rate, p95 latency, database pool
  utilization and error-budget consumption.
- Compare the last deployment and config-change timestamps with when errors first rose. Here,
  that means the concurrency configuration deployment.
- Tell the incident commander whether the evidence points to application saturation, a
  dependency timeout or database connection exhaustion.
- Preserve trace IDs and **sanitized** logs. Never paste customer tokens, card numbers or secrets
  into chat or an LLM.

**3. Pool triage (93% is above the 90% threshold).** Utilization above 90% for five minutes with
increasing timeouts is **evidence** of pool saturation, **not definitive root cause** [S3].
Inspect active, idle and pending connections, max connections, queue wait time and timeouts [S3].
Then follow the triage sequence [S4]:
1. Check recent changes to pool size, request concurrency, DB proxy or retry configuration.
2. Review slow queries and connection leaks, and correlate them with deployment time.
3. Use **read-only** diagnostics to find long-running transactions. No ad hoc destructive SQL.
4. Escalate to the database on-call and the incident commander if uncertainty remains.
5. **Avoid blind restart loops**, which can worsen retry storms. This runbook gives no basis for a
   database restart.

**4. What can be rolled back.** If the problem followed an approved configuration release (here,
the concurrency configuration deployment), the engineer may **propose** a rollback of that
release through POL-CHG-010 [S4]. If a staged rollback is approved and the release procedure
supports it, use it [S7]. **The engineer does not self-approve** [S4].

**5. Who must approve, and when.** Approval is required from **both** the incident commander
**and** an independent on-call change approver, **before execution** [S5]. The change record must
name:
- the incident and affected service,
- the proposed rollback version,
- the risk assessment and verification metrics,
- the executor and the approvers [S5].

The executor cannot act as the independent approver [S5]. If a life/safety issue blocks the
normal path, contact the designated executive duty officer. No exception is defined or automated
here [S5].

**6. Verifying recovery.** Pool utilization must stay **below 75%** and payment error rate
**below 1%** for **at least 15 minutes**. A single good reading is not enough [S7]. Record the
change ID, the evidence and the observed effect [S7].

**7. Customer updates.** While the P1 is open, send an approved customer-facing update **at least
every 30 minutes** [S6]. The incident commander owns coordination [S6]. Updates must not include
credentials or PII [S6].

**What this answer does not do:** it does not claim any approval has happened, it does not
authorise or perform the rollback, and it does not assert a root cause. Those decisions belong to
the incident commander and the independent change approver.

## Evidence manifest

From `python -m submission.src.cli incident-packet --role engineer`: role `engineer`, 7 sources,
**995 / 1,200 tokens**, nothing quarantined, nothing dropped.

| Source | doc_id | Version | Section | Path |
|---|---|---|---|---|
| S1 | RUN-PAY-101 | 3.2 | Trigger and severity | data/knowledge/payments-api-p1-runbook.md |
| S2 | RUN-PAY-101 | 3.2 | First ten minutes (2 chunks merged) | data/knowledge/payments-api-p1-runbook.md |
| S3 | RUN-DB-201 | 2.1 | Detect and verify | data/knowledge/database-pool-runbook.md |
| S4 | RUN-DB-201 | 2.1 | Triage sequence (2 chunks merged) | data/knowledge/database-pool-runbook.md |
| S5 | POL-CHG-010 | 4.0 | Approval and evidence (2 chunks merged) | data/knowledge/emergency-change-policy.md |
| S6 | POL-SLO-020 | 2.3 | Operating targets | data/knowledge/severity-and-slo-policy.md |
| S7 | RUN-DB-201 | 2.1 | After mitigation | data/knowledge/database-pool-runbook.md |

**Excluded by design:**
- `RUN-PAY-OLD` is retired and never indexed.
- `SEC-FRAUD-009` is security-only and filtered out for `engineer`.
- `PM-2026-071` (postmortem) was not needed. It is consistent with the answer: the July incident
  was resolved by rolling back the concurrency config with dual approval and a 15-minute
  observation, after a database restart was rejected.

## Ground-truth check (reviewer table)

| Component | Covered by | Must-not-claim avoided? |
|---|---|---|
| P1 trigger | S1 | ✅ States that one isolated 5xx is not P1 |
| Immediate checks | S2 | ✅ Sanitized traces only; no raw tokens or card data |
| Pool triage | S3, S4 | ✅ Says "not definitive root cause"; no blind restart |
| Emergency rollback | S4, S5 | ✅ IC **and** independent approver, **before** execution; no self-approval |
| Recovery | S7 | ✅ Both thresholds held for 15 min; not closed at the first good reading |
| Communications | S6 | ✅ Every 30 min, coordinated by the IC |

One gap: the expected evidence lists `POL-SLO-020` for the P1 trigger too. The packet's
POL-SLO-020 chunk is "Operating targets", not "P1 definition", so the trigger is cited from S1
only. Retrieval does surface POL-SLO-020 for the trigger (eval q01, rank 2).
