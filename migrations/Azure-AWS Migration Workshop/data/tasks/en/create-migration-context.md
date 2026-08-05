---
id: create-migration-context
title: Create The Migration Context
summary: Give the four agents one validated migration assignment before they are invoked.
phase: Migration Setup
---

Create the canonical migration assignment that every agent will read when invoked. It fixes the workshop boundaries while keeping discovery findings and architecture decisions in their own later artifacts.

- Record the fixed source and target roots.
- Apply the workshop constraints and documented commercial Region candidates.
- Reference the source architecture created in Task 2.
- Keep discovery, architecture, service, and model decisions explicitly unresolved.
- Validate the context against its checked-in JSON schema.

```text
Create the shared migration assignment without invoking an agent.

Confirm these inputs:
- source_root: apps/azure-ai-shopping-cart-app
- target_root: apps/aws-target-app
- source architecture: /tmp/workshop-artifacts/source-architecture.md
- workshop rules: AGENTS.md and rules/agent-team-protocol.md
- architecture constraints: docs/architecture.md

Write /tmp/workshop-artifacts/migration-context.json using schemas/migration-context.schema.json. Set status to discovery and source_profile to /tmp/workshop-artifacts/source-profile.json as a future artifact.

Define the objective as preserving the selected application's observed interfaces and user workflows while migrating Azure OpenAI Chat Completions to Amazon Bedrock OpenAI Responses. Include the selected source and the repository files needed for analysis. Exclude .git, dependency folders, build output, generated artifacts, credentials, and the target implementation until migration approval.

Record these constraints without adding unsupported requirements:
- preserve observed public behavior;
- keep credentials out of source and artifacts;
- do not move production data;
- do not modify the source application;
- do not populate the target before APPROVE MIGRATION;
- use only a compatible, live-verified openai.gpt-5.4 or openai.gpt-5.5 tuple with no silent fallback;
- keep AgentCore and every AWS service choice conditional on later evidence.

Copy the permitted commercial Region candidates from docs/architecture.md. Do not select a Region, model, AWS archetype, service mapping, or endpoint in this task. Record only evidence-backed assumptions and open questions; leave unknown discovery findings unresolved. Add evidence entries for the source root, Task 2 architecture, workshop rules, and architecture constraints.

Validate the file against schemas/migration-context.schema.json. Stop with a clear blocker on a schema error, missing source architecture, conflicting roots, missing source, or a target containing anything other than .gitkeep. Report the validated assignment and unresolved questions without modifying either application.
```

Continue when `/tmp/workshop-artifacts/migration-context.json` passes schema validation and identifies one source and one target root.
