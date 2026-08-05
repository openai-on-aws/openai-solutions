---
id: destroy-workshop-environment
title: Destroy The AWS Environment
summary: Present teardown impact, wait for DESTROY, and verify cleanup.
phase: AWS Teardown
---

Remove the workshop environment only after reviewing the complete resource inventory. `DESTROY` is independent from deployment approval because teardown can remove databases, logs, endpoints, and other state created during the lab.

- Review every resource that will be deleted or intentionally retained.
- Confirm irreversible effects and post-destroy verification checks.
- Enter `DESTROY` only after preserving required workshop evidence.
- Verify that no unintended billable workshop resource remains.

```text
Present the complete workshop resource inventory and teardown impact for my approval.

Show me what will be deleted, what will be retained, affected data or logs, irreversible effects, reusable bootstrap resources, and how cleanup will be verified.

Ask me to type exactly `DESTROY`. After I approve, remove only the recorded workshop resources and verify their absence. Report deleted, retained, failed-delete, and still-billable resources.
```

The workshop is complete when teardown evidence proves that all intended resources are removed and any retained shared resource is explicitly documented.
