# Emergency Production Change Policy

## Applicability

This policy governs emergency production changes for active P1 and P2 incidents, including feature-flag changes and rollback of a recent configuration release.

## Approval and evidence

An emergency rollback requires approval from **the incident commander and an independent on-call change approver** before execution. The change record must identify the incident, affected service, proposed rollback version, risk assessment, verification metrics, executor and approvers. The executor cannot act as the independent approver.

If an immediate life/safety issue prevents the normal path, contact the designated executive duty officer; the workshop does not define or automate an exception.

## Execution and closure

Use the approved deployment platform and documented rollback procedure. Maintain an audit trail of actual commands and timestamps. Verify health metrics after the change. Complete the permanent change record and retrospective **within 24 hours**. Do not confuse the post-change record requirement with permission to defer pre-execution approval.
