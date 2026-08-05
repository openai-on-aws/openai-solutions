---
id: validate-source-app
title: Validate The Source Application
summary: Capture source acceptance evidence before migration decisions begin.
phase: Source Baseline
---

Have the validation agent establish the source acceptance contract before architecture work begins. Later target checks will compare against this evidence instead of relying on assumptions.

- Validate repository-supported builds and static checks.
- Exercise representative APIs, browser workflows, persistence, and errors.
- Capture Azure OpenAI behavior without exposing credentials.
- Record preserved contracts and factual blockers.

```text
Establish the source application's acceptance baseline.

Validate the supported build, representative APIs, browser workflows, persistence, errors, health behavior, and the Azure OpenAI integration features the application actually uses.

Show me the behaviors the migration must preserve, the checks that passed, material unknowns, and any blocker that would make later parity testing unreliable.
```

Continue when the validation agent confirms an evidence-backed source acceptance baseline.
