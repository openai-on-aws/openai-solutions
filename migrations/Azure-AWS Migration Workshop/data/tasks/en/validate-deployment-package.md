---
id: validate-deployment-package
title: Validate The Deployment Package
summary: Build the target, synthesize CDK, and validate the manifest without deployment.
phase: Deployment Packaging
---

Have the validation agent challenge the generated package without creating AWS resources. This pass proves that application artifacts, container platforms, IAM, networking, and synthesized CloudFormation agree with the manifest.

- Build the application and any selected deployment artifacts.
- Type-check and synthesize the manifest-driven CDK package.
- Inspect IAM, networking, secrets, health, rollback, and cost drivers.
- Verify teardown coverage and conditional AgentCore behavior.

```text
Validate the generated deployment package without creating AWS resources.

Build the relevant application artifacts, type-check and synthesize the CDK package, and review the resulting infrastructure for manifest consistency, IAM scope, networking, secrets, health, rollback, cost drivers, AgentCore usage, and complete teardown coverage.

Show me the validation result, synthesized architecture, security or operational findings, and every blocker that must be resolved before AWS preflight.
```

Continue when application builds and CDK synthesis pass with no unresolved package, security, or teardown blocker.
