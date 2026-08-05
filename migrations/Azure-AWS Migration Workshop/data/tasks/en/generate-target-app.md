---
id: generate-target-app
title: Generate The Target Application
summary: Implement the approved migration contract under the configured target root.
phase: Target Implementation
---

Generate the target application only after the migration contract is approved. The main Codex session owns implementation so it can coordinate changes across the whole application while preserving the source as a reference.

- Verify that approval matches the current decision artifacts.
- Generate under the configurable target root without changing the source.
- Preserve approved APIs, UI behavior, state, and error contracts.
- Isolate the Bedrock Responses adapter and keep AgentCore conditional.

```text
Generate the target application from the approved migration contract.

Preserve the approved interfaces and user workflows while implementing the selected AWS architecture and Amazon Bedrock OpenAI Responses integration. Keep provider-specific code isolated and apply the approved decisions for state, errors, retries, health, logging, credentials, and AgentCore.

Build and inspect the generated application, then show me the implementation changes, preserved contracts, validation result, and any blocker.
```

Continue when the generated target builds successfully and Codex reports the implementation result.
