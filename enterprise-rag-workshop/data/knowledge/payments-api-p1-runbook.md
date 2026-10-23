# Payments API P1 Incident Runbook

## Trigger and severity

Declare a P1 when the Payments API has more than **5% HTTP 5xx responses for five consecutive minutes** and customer checkout is materially affected. Start the incident bridge and assign an incident commander. Do not treat a single failed request as a P1.

## First ten minutes

1. Acknowledge the P1 page within ten minutes and record the incident ID.
2. Check request rate, 5xx error rate, p95 latency, database pool utilization and error-budget consumption on the approved dashboards.
3. Check the last deployment and configuration-change timestamps. Correlate them with the first increase in errors.
4. Tell the incident commander whether the evidence suggests application saturation, dependency timeout or database connection exhaustion.
5. Preserve trace IDs and sanitized logs. Do not paste customer tokens, card numbers or secrets into chat or an LLM.

## Database connection exhaustion path

If connection utilization exceeds **90% for five minutes**, read the Database Connection Pool Saturation Runbook (RUN-DB-201) before mitigation. A connection-pool alarm alone is not authority to restart the database.

## Recovery and communication

Check recovery against the 5xx, latency and utilization dashboards for at least **15 minutes** after mitigation. Communicate externally only through the incident commander using the communications policy POL-SLO-020. Any production rollback must follow emergency change policy POL-CHG-010.
