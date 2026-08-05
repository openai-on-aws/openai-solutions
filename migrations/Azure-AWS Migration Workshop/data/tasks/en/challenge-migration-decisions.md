---
id: challenge-migration-decisions
title: Challenge The Migration Decisions
summary: Have validation independently attack architecture, API, parity, and rollback assumptions.
phase: Migration Review
---

Use an independent validation pass before approving the migration. The validation agent should challenge unsupported assumptions and contract drift without quietly rewriting the architect's decisions.

- Verify source claims against repository and runtime evidence.
- Challenge AWS service choices, model eligibility, and endpoint handling.
- Examine security, state, observability, cost, and rollback assumptions.
- Record actionable findings with evidence and severity.

```text
Independently challenge the proposed migration.

Check the source evidence, preserved contracts, AWS service choices, model and Region eligibility, API transformation, security, state, observability, cost, rollback, and AgentCore decision.

Show me the findings by severity, the evidence behind each blocking concern, and the remediation owner. Keep the architect's decisions unchanged until the findings are reviewed.
```

Continue when the independent findings are documented and every blocking concern has an assigned remediation.
