---
id: package-migration-plugin
title: Package The Migration Workflow As A Plugin
summary: Turn the completed workshop workflow into reusable Codex automation for another application folder.
phase: Reusable Automation
---

Package the validated migration method as a reusable Codex plugin before removing the workshop environment. This replaces repeated task-card orchestration with one folder-based request while preserving the same specialist separation, evidence contracts, validation, and human approval gates.

- Accept an application folder instead of assuming the bundled sample.
- Coordinate discovery, architecture, validation, implementation, and AWS deployment automatically.
- Include the workshop's rules, schemas, validators, AWS guidance, and deployment archetypes.
- Preserve secure credential handling and the `APPROVE MIGRATION`, `DEPLOY`, and `DESTROY` gates.
- Validate the package with a safe discovery-only run before installation.

```text
Package the validated migration workflow as a reusable Codex plugin named `azure-bedrock-migration`.

Make it accept an application folder and automatically coordinate source discovery, architecture selection, API migration, validation, target generation, deployment packaging, preflight, deployment, and teardown.

Include the workshop's specialist contracts, orchestration, schemas, validators, AWS guidance, and deployment archetypes. Preserve the approval and credential boundaries, and exclude sample-specific code, secrets, account data, and generated evidence.

Validate the plugin, run a safe discovery-only dry run against the bundled source, and show me its package structure, installation steps, example request, and validation result.
```

Continue when the plugin validates, the discovery-only dry run succeeds without changing either application, and another user can point it at a folder using the documented example request.
