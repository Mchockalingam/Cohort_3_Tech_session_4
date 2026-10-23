# Incident Severity and Communication Policy

## P1 definition

For customer-facing payment processing, a sustained 5xx error rate above **5% for five minutes** with checkout impact is P1. The customer impact assessment takes precedence over isolated alarms.

## Operating targets

P1 on-call acknowledgement target: **10 minutes**. The incident commander owns coordination. Provide an approved customer-facing update at least **every 30 minutes** while the P1 remains open. Updates must not include credentials or personally identifiable information.

## Resolution

Do not declare full recovery until the service runbook's post-mitigation observation period has passed. Incident commander owns severity downgrade and closure, supported by evidence from dashboards.
