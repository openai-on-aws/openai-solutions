---
id: preflight-aws-account
title: Preflight The AWS Account
summary: Run read-only account, Region, permission, quota, and model checks.
phase: Deployment Preflight
---

Inspect the participant-owned AWS sandbox before requesting deployment approval. Preflight is read-only and should surface identity, Region, model, permission, quota, capacity, cost, and cleanup blockers before resources are created.

- Confirm the active AWS identity and approved Region in redacted form.
- Check required services, permissions, quotas, and container tooling.
- Reconfirm the selected model and architecture-specific prerequisites.
- Produce a complete preflight report without changing the account.

```text
Run a read-only preflight against my AWS sandbox.

Check the active identity and Region, required services and permissions, CDK bootstrap state, quotas, container requirements, selected-model visibility, expected billable resources, cost drivers, rollback readiness, teardown prerequisites, and the proposed CDK changes.

Show me the redacted account summary, planned impact, cost drivers, readiness status, and every blocker that must be resolved before deployment approval.
```

Continue when the preflight report is complete and no unresolved blocker prevents presenting the deployment gate.
