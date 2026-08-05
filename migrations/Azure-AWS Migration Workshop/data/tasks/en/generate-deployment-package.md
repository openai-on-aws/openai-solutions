---
id: generate-deployment-package
title: Generate The Deployment Package
summary: Have the deployment engineer write the manifest and generate CDK from it.
phase: Deployment Packaging
---

Convert the approved architecture into an explicit deployment manifest and AWS CDK package. Infrastructure should follow the selected workload archetype and discovered dependencies rather than defaulting every application to containers, RDS, NAT, or AgentCore.

- Describe compute, data, integration, network, secrets, and observability resources.
- Generate the smallest CDK package supported by the approved decisions.
- Keep AgentCore and stateful services conditional on evidence.
- Generate sandbox schema and seed assets without moving production data.

```text
Turn the approved architecture and validated target into a deployable AWS package.

Create the smallest manifest-driven CDK implementation that supports the selected architecture, including only the required compute, data, integration, network, secrets, observability, health, and teardown resources. Keep AgentCore and stateful services conditional on the approved decisions.

Show me the deployment architecture, generated package, data-migration plan when applicable, expected resources, and any blocker that prevents package validation.
```

Continue when the deployment manifest validates and the CDK package represents only the approved architecture.
