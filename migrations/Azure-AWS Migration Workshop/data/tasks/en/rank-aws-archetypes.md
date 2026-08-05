---
id: rank-aws-archetypes
title: Rank AWS Architecture Archetypes
summary: Have the architect compare two or three viable target shapes before selecting one.
phase: Migration Analysis
---

Ask the architecture agent to compare viable AWS workload shapes before selecting one. The recommendation should be the simplest architecture that preserves the discovered contracts, not a fixed App Runner, database, or AgentCore design.

- Rank two or three evidence-backed AWS archetypes.
- Map discovered Azure services only when the target needs them.
- Compare security, operations, cost, migration effort, and rollback.
- Treat AgentCore as conditional rather than a default requirement.

```text
Compare viable AWS target architectures for the discovered application.

Recommend the simplest option that preserves the source contracts. Compare credible alternatives across migration effort, reliability, security, networking, operations, cost drivers, and rollback, and include only AWS services justified by source evidence.

Show me the recommended architecture, rejected alternatives, Azure-to-AWS service mapping, confidence, AgentCore decision, and any unresolved blocker.
```

Continue when the architecture decision validates, compares credible alternatives, and explains every selected AWS service.
