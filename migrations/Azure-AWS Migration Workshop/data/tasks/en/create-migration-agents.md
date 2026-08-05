---
id: create-migration-agents
title: Create The Four Migration Agents
summary: Configure exactly four named specialists for the sequential flow.
phase: Agent Setup
---

Create the four project-scoped specialists used by the rest of the workshop. Their definitions use the checked-in team protocol so every agent has an explicit mission, inputs, procedure, outputs, authority, restrictions, and completion criteria.

- Create discovery, architecture, validation, and deployment agent definitions.
- Implement the complete role contract for each specialist; do not create generic reviewer prompts.
- Keep shared operating safeguards consistent across all four definitions.
- Validate the filenames, names, instructions, outputs, and role boundaries before invoking any agent.

```text
Create the four project-scoped agents defined in rules/agent-team-protocol.md.

Read that protocol and docs/architecture.md, then create exactly these TOML files under .codex/agents:
- migration-discovery.toml with name = "migration-discovery";
- migration-architect.toml with name = "migration-architect";
- migration-validation.toml with name = "migration-validation";
- aws-deployment-engineer.toml with name = "aws-deployment-engineer".

Each file must define name, description, developer_instructions, and nickname_candidates. In developer_instructions, implement the complete shared operating contract and the complete role-specific contract from the protocol. Preserve the role's required inputs, ordered procedure, exact outputs, authority, restrictions, completion report, factual blocker behavior, and human approval gates. Configure the agents to read migration-context.json only when they are invoked after the next task creates it.

Run python3 tools/validate_codex_agents.py --agents-dir .codex/agents. Fix only agent-definition issues and report the four validated files. Do not generate target application code.
```

Continue when all four TOML definitions validate and no migration agent has been invoked yet.
