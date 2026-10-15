# Discovery without a repository

Use this mode to answer a migration question, narrow feasible options, or produce a preliminary migration plan from conversation and supplied architecture/inventory. Do not scan the current directory just because a checkout is available. Code access is useful later to resolve a specific implementation uncertainty.

## Conversation flow

Start from what the customer has already told you. Ask one to three questions whose answers eliminate routes; avoid presenting this entire checklist at once.

1. Establish source and target intent: Azure OpenAI, direct OpenAI, Foundry agents, or another source? Source model/API/SDK? Existing application or new design? Preserve explicit provider/model choices; distinguish migrating the workload from hosting the identical source model.
2. Establish the data boundary before recommending a route. Ask country/geography versus one AWS Region, allowed failover Regions, commercial versus GovCloud partition, and whether the boundary covers inference, prompt caches, stored responses, abuse retention, logs, backups, tools and retrieval. An endpoint in Europe does not prove European processing. PrivateLink does not establish residency.
3. Ask which major features are actually used or planned: prompt versus whole-response caching; implicit/explicit cache controls, reusable-prefix size, maximum permitted retention and expected reuse; strict JSON schema versus merely valid JSON; strict tool arguments versus text output schema; streaming; client tools versus server tools; inline versus separate Guardrails; background execution; stored conversations; custom Projects; invocation payload logs; image inputs. Do not assume every feature is required.
4. Resolve retention and operational constraints: provider-stored history, full ZDR, logging permissions, external web access, IAM/SigV4 versus API keys, private networking, quota/throughput, latency and spend targets. `store=false` is not full ZDR. A 30-minute minimum cache TTL is not an upper deletion guarantee.
5. Narrow routes using the compatibility reference. Present qualifying candidates, excluded candidates with exact blockers, and verification candidates. If no route meets the combination, explain the smallest possible design changes as options and retain the original requirements until the customer accepts a change.
6. Compare plausible models on the customer's evaluation criteria. No automatic model selection, no assumed GPT-4.1 equivalence, and no blanket Responses mandate. Keeping Chat Completions may minimize changes when caching or other requirements do not force another API.
7. Provide a detailed, staged migration path with validation and rollback. Request source access only when it would resolve a specific open question.

## Assumptions and continuity

Maintain a compact ledger with requirement, value, status (confirmed/assumed/unresolved), basis, decision impact, and next question. Reuse it across turns. Explain an assumption immediately when it affects an option. Revise the ledger and route comparison when the customer corrects you.

Reasonable provisional assumptions include an illustrative request volume or an application-managed tool loop when clearly labelled and used only for a conditional estimate. Do not silently assume allowed data locations, ZDR exceptions, permission to log payloads, acceptable providers, acceptable model substitutions or external data disclosure. Unknown privacy requirements keep the recommendation conditional, but do not prevent useful independent analysis.

If the customer asks a narrow factual question, answer it directly with current sources and relevant conditions. Do not force a full intake or write files unless a report/assessment is requested or a small intermediate file is needed to evaluate combinations.

## Preliminary discovery report

For a full saved report, follow [shared-report.md](shared-report.md): use the same nine sections as code assessment, save report-contract.json, and render/check the four linked tables. Section 8 is the central gap/blocker register; section 5 contains orchestration designs and section 6 contains Azure-to-AWS mappings. Explain missing service or route information. Discovery uses no invented repository commit or code-inspection claim.

Within that structure, a migration-path report includes:

- Decision: recommended route if supported, alternatives, and decisive reasons. Label provisional choices and distinguish documentation, account availability and runtime evidence.
- Source workload and business goals; supplied evidence and material omissions.
- Requirement/assumption ledger and unresolved questions.
- Candidate table keyed by exact model/profile ID, endpoint, API/path, entry Region and processing geography. Show feature combination status, excluded routes, orchestration requirements and evidence dates.
- Data-flow boundary for processing, cache, response state, logs, abuse retention, tools, retrieval and backups. Unknown locations remain explicit.
- Migration steps: request/response mapping, history/state migration, tool lifecycle and authorization, structured-output validation, streaming and cancellation, caching configuration, IAM/credential refresh, networking, retries/timeouts, observability, data migration and external integrations as relevant.
- Rollout: representative synthetic evaluation set, quality/tool correctness, schema adherence, p50/p95 latency and TTFT, cache-read/write hit economics, quotas, failure tests, canary criteria and rollback switch. Do not promise equal quality or savings before measurement.
- Costs: distinguish input, output, cache writes/reads, context bands, geography/tier, safety/tool calls and infrastructure. Use current pricing; record workload assumptions.
- Next validation: exact questions, documentation conflicts and optionally approved account checks. Do not run cloud queries or send customer payloads just to answer discovery questions.

For a saved report, store requirements JSON and route evaluation JSON alongside the narrative, and reference the evidence. A discovery report uses no invented repository SHA, fake route scan, or code-coverage claim. The engine's `YES` means the supplied requirements pass recorded documentation checks, not compliance certification or live verification.

## Example progression

For a US-resident workload requiring caching, determine whether multiple US Regions are permitted and whether caching means prompt reuse or whole-answer reuse. Compare exact routes against required features. Current models differ: GPT-6.1 Sol documents Chat/Invoke caching and Guardrails, while older cards have narrower API support. Inspect the current registry and evidence rather than copying an example result.

If requirements later change to one Region, an explicit cache mode, streaming schemas, or ZDR, reevaluate the same ledger. Present rejected routes, conditional routes, and required application changes. Record account and runtime verification as separate work.
