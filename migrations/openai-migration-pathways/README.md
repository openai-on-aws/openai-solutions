# OpenAI Migration Pathways

OpenAI Migration Pathways is a Codex plugin that helps teams assess and plan migrations from Azure OpenAI or direct OpenAI integrations to Amazon Bedrock. Starting from customer requirements or a code repository, it identifies workloads and dependencies, evaluates model, API, and Region combinations against an evidence-based compatibility catalog, and checks requirements such as residency, caching, streaming, structured outputs, and tool use. It generates a standardized migration report with route recommendations, gaps and blockers, proposed orchestration, Azure-to-AWS service mappings, and validation steps. When requested, it also prepares architecture diagrams, application changes, and deployment artifacts, while recording assumptions, implementation status, and readiness for deployment.

See [installation](INSTALL.md), [the catalog](docs/compatibility-catalog.md), [release notes](docs/release-0.4.2.md), and [refresh procedure](docs/refreshing-evidence.md).

## How to use it

Use the plugin through a normal conversation in Codex. Provide your requirements or a repository, and Codex uses the plugin's instructions, compatibility catalog and evaluation scripts to produce the assessment.

### 1. Install it once

For the shared release folder, extract the complete package and run:

```bash
codex plugin marketplace add /absolute/path/to/extracted-package
codex plugin add openai-migration-pathways@openai-solutions
```

Keep the entire extracted folder, including the hidden `.agents` directory. Start a new Codex chat after installation. See [installation instructions](INSTALL.md) for prerequisites, installing from a repository checkout, and the GitHub installation option once this contribution is merged.

### 2. Choose how to start

Select the plugin in Codex or name it in your message. Start with the scope you need:

**Discovery — requirements without code**

> Use $openai-migration-pathways. We have an Azure OpenAI document assistant using hosted file search, streaming and conversation history. We need US data residency, authorized citations and strict JSON answers. Produce a full discovery assessment with routes, blockers, orchestration proposals and Azure-to-AWS mappings. Do not inspect a repository.

**Code assessment — a repository or local folder**

> Use $openai-migration-pathways. Assess this repository: [repository URL or local path]. Target AWS Region: us-east-1. Identify application routes, AI features, migration gaps, required orchestration and Azure-to-AWS service mappings. Produce the full assessment. Do not deploy.

**Implementation — after reviewing the assessment**

> Use $openai-migration-pathways. Use the assessment to prepare the application changes, AWS infrastructure source, unified architecture and validation plan. Keep unresolved decisions visible. Do not deploy.

### 3. Answer the important follow-up questions

The plugin clarifies information that affects the route, including:

- Required models, APIs and features.
- Allowed processing locations and data-retention requirements.
- Whether application-managed retrieval or conversation history is acceptable.
- Performance, cost and operational constraints.

You do not need to edit the compatibility JSON or run evaluation scripts yourself. Discovery and offline assessment do not require cloud credentials; repository access is needed for code assessment.

### 4. Review the results and continue in the same chat

The report identifies recommended and rejected routes, blockers, orchestration designs, service mappings and next validation steps. With code, it adds file references and concrete implementation findings.

Continue with requests such as:

> Explain G03, compare the two proposed routes, and show what code must change before migration.

Use the gap IDs and route names from your own report. An assessment describes required orchestration; implementing and validating it is a separate step.

## What the customer receives

Every full saved assessment includes readable Markdown and a shared JSON contract:

1. Decision and target-model recommendations.

2. Scope, evidence and execution provenance.

3. Workload and route inventory.

4. Source AI contracts.

5. Bedrock feature mapping and API migration, including orchestration designs.

6. Azure-to-AWS service mapping.

7. Unified architecture and data flows.

8. Deployment implementation and gaps, including the central gap and blocker register.

9. Validation, readiness and next actions.

## How the plugin builds a migration plan

The plugin combines **Codex analysis with a deterministic compatibility evaluator**. Codex gathers requirements and, when a repository is supplied, traces application entry points, AI SDK calls, configuration and dependencies. It turns each AI workload into explicit constraints covering features, APIs, geography, retention and operational needs.

The evaluator checks those constraints against `data/capabilities.json`, which contains model capabilities backed by dated AWS and OpenAI documentation. It evaluates each exact **model + endpoint + API + Region + routing configuration** against the complete feature combination. Results are classified as **YES** (documented compatibility), **NO** (incompatible), **VERIFY** (unresolved evidence), or **ORCHESTRATED** (requires an accepted application workaround).

Codex uses these results, customer preferences and documented tradeoffs to propose a route and migration plan. Gaps become concrete application changes, orchestration designs, Azure-to-AWS mappings and validation tasks, while original incompatibilities remain visible. Report validators check consistency between the recommendations, saved evaluations and evidence. Account access, model quality, performance and deployment readiness require separate verification.

## Example scenarios

Paste any of these into the OpenAI Migration Pathways agent to exercise discovery mode.

### Scenario 1 — EU residency vs. US-only model

> Migrate our Azure OpenAI customer-support assistant to Bedrock. It uses streaming and client-side tools, and we rely on prompt caching for a long shared system prompt. Hard requirement: all inference and cached data must stay within the EU — this is a regulated banking customer. Which Bedrock pathway supports this, and if none does, what are our options?

### Scenario 2 — Structured outputs for a data-extraction pipeline

> We have a direct OpenAI document-extraction service moving to Bedrock. It needs strict structured JSON outputs (a fixed schema), plus streaming and client tools. No prompt caching, no guardrails. US geography is fine, any US Region works. Which model and API should we use, and is strict structured output actually native or does it need verification?

### Scenario 3 — Zero-retention vs. background + stored state

> Our Azure OpenAI agent runs long background jobs and keeps stored conversation state across turns. We're migrating to Bedrock under a strict zero-data-retention policy for a healthcare client. We also want streaming. Can we keep background execution and stored state under ZDR, and what exactly has to change if not?

## Licensing and publication

Original code follows MIT-0 and original documentation follows CC-BY-SA-4.0, matching the repository. Third-party artwork and captured provider documentation retain their own terms; see [LICENSING.md](LICENSING.md) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Authors: EB Khiyami.

See [publishing and release checks](docs/publishing.md) for the marketplace layout, CI, release tags and archive verification.
