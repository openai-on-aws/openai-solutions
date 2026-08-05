---
id: understand-migration-journey
title: Understand The Migration Journey
summary: See how Codex turns an Azure OpenAI application into a validated, deployable AWS workload.
phase: Start Here
---

This workshop uses Codex Desktop as the participant-controlled migration workspace. You will begin with a working Azure OpenAI application, build a team of specialist agents, approve an evidence-backed migration contract, validate live Amazon Bedrock inference locally, deploy the selected architecture to a participant-owned AWS sandbox after explicit approval, package the workflow as a reusable plugin, and then remove the workshop environment.

![Azure OpenAI to AWS migration journey](/images/migration-journey.svg "w=1200 center")

- Use the bundled shopping cart as the workshop reference, then package the workflow for reuse with another application folder.
- Preserve observed APIs, user workflows, state, errors, and operational behavior.
- Use four Codex agents for discovery, architecture, validation, and AWS deployment.
- Migrate Azure OpenAI Chat Completions to an available Amazon Bedrock OpenAI Responses model.
- Keep target generation, AWS resource creation, and teardown behind separate human approval gates.
- Create a validated Codex plugin that preserves the same orchestration, evidence, and approval controls.

Continue when you can explain the complete journey from source selection through reusable plugin packaging and validated AWS teardown, and identify all three approval gates.
