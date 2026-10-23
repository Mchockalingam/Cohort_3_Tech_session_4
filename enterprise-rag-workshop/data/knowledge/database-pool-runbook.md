# Database Connection Pool Saturation Runbook

## Detect and verify

On `payments-api`, inspect pool active/idle/pending connections, database max connections, queue wait time and timeouts. Treat **greater than 90% utilization for five minutes** with increasing timeouts as evidence of pool saturation, not definitive root cause.

## Triage sequence

1. Check for recent changes to connection pool size, request concurrency, database proxy or retry configuration.
2. Review approved dashboards for slow queries and connection leaks; correlate with deployment time.
3. Use read-only database diagnostics to identify long-running transactions. Do not run ad hoc destructive SQL.
4. If the problem followed an approved configuration release, propose rollback through POL-CHG-010. An engineer does not self-approve an emergency rollback.
5. When uncertainty remains, escalate to the database on-call and incident commander. Avoid blind restart loops that can worsen retry storms.

## After mitigation

Verify pool utilization falls below **75%** and payment error rate below **1%** for at least **15 minutes**. Record the change ID, evidence and observed effect. Use a staged rollback if one is approved and supported by the release procedure.
