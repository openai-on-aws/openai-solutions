---
id: run-discovery-agent
title: Run The Discovery Agent
summary: Produce the canonical source profile from repository and runtime evidence.
phase: Migration Analysis
---

Use the discovery agent to turn repository and runtime evidence into a canonical source profile. Keeping discovery separate prevents an AWS preference from shaping what the agent claims to have found.

- Inventory runtimes, frameworks, commands, interfaces, and state.
- Detect Azure services and Azure OpenAI Chat Completions usage.
- Record identity, networking, deployment, and data dependencies.
- Validate the resulting profile before architecture selection.

```text
Analyze the selected source application and create its validated source profile.

Create a validated source profile covering the application stack, public interfaces, data and state, Azure service dependencies, and Azure OpenAI Chat Completions implementation.

Show me the discovered application shape, the behaviors the migration must preserve, evidence gaps or unknowns, and any blocker that prevents reliable AWS architecture design.
```

Continue when the source profile validates and every material claim cites source evidence.
