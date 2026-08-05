---
id: deploy-aws-environment
title: Deploy The AWS Environment
summary: Present impact, wait for DEPLOY, and create only the validated resources.
phase: AWS Deployment
---

Review exactly what the workshop will create before authorizing AWS deployment. `DEPLOY` is a separate human gate and applies only to the validated account, Region, manifest, and CDK diff presented in this task.

- Review resources, IAM changes, network exposure, and cost drivers.
- Confirm rollout, rollback, observability, and teardown plans.
- Enter `DEPLOY` only when the presented scope is acceptable.
- Let the deployment agent create only the approved resources.

```text
Present the validated AWS deployment for my approval.

Show me the redacted account and Region, resources, IAM changes, network exposure, selected model, AgentCore mode, cost drivers, CDK changes, rollout, rollback, observability, and teardown plan.

Ask me to type exactly `DEPLOY`. After I approve, deploy the presented package and wait for readiness. Report the resulting application endpoint, created resources, operational status, rollback information, cleanup inventory, or deployment blocker.
```

Continue when the approved AWS environment is ready and every created resource is recorded for validation and teardown.
