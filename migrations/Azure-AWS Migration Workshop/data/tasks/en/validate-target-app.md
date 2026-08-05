---
id: validate-target-app
title: Validate The Generated Target
summary: Prove build integrity, contract parity, provider replacement, and decision compliance.
phase: Target Validation
---

Have the validation agent inspect the generated target before any live credential is supplied. This pass catches build failures, stale Azure dependencies, hidden mock behavior, and contract drift without contacting Amazon Bedrock.

- Build and inspect the target using repository-supported tools.
- Compare public contracts with the source acceptance baseline.
- Check provider isolation, endpoint handling, secrets, and fallback behavior.
- Prepare browser and API checks for the later live run.

```text
Inspect the generated target before live credentials are supplied.

Verify that it builds, preserves the approved public contracts, removes stale Azure provider dependencies, has no hidden mock fallback or secret leakage, and implements the approved Responses request, output parsing, endpoint, model, and AgentCore decision.

Show me the checks performed, failures, residual risks, and whether the target is ready for live local testing.
```

Continue when the validation agent confirms that all credential-free acceptance checks pass.
