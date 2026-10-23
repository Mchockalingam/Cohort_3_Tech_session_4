# July 2026 Database Pool Incident Review

## Summary

On 9 July 2026, a concurrency configuration change increased pending database requests on Payments API. An application-level retry surge amplified database connection pool exhaustion. The incident was declared P1 after sustained checkout 5xx failures.

## What helped

Read-only telemetry identified pool wait time and a change correlation. The team rolled back the concurrency configuration after incident commander and independent on-call change approval, then observed recovery for 15 minutes.

## What failed

Early responders proposed a full database restart without adequate evidence. The incident commander rejected the restart because it could amplify retry storms. The service also had inadequate alerts for pending pool waiters.

## Follow-up actions

Add alerts on pending connection waiters, test retry budgets during load tests, document the approval chain in the change record, and update the runbook with the pool utilization threshold.
