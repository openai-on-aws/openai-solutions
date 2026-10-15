# Exact-route compatibility, release 0.4

Use `data/capabilities.json` from the plugin root. It is a dated registry, schema version 2, covering nine approved OpenAI targets. GPT-OSS and Daybreak are excluded. Other source models can be assessed without adding them as targets. Missing target entries are outside the evaluated policy, not proof of global unavailability.

## Evidence and scope

Every feature claim has a status, explanation, evidence IDs and review date. Source records contain the official URL, retrieved URL, scope, retrieval time, snapshot path and hash. OpenAI direct-model facts describe the source API; AWS model cards establish Bedrock identifiers, APIs, Regions and limits. OpenAI's Bedrock integration guide supplies explicitly Bedrock-scoped migration gaps. Never copy direct OpenAI support into a Bedrock claim.

Resolve model-specific documentation before generic examples. Record unresolved conflicts as VERIFY. Treat a new page fetch as a candidate snapshot, not a review of every claim. Recheck decisive evidence before a final recommendation, even within the registry's 30-day maintainer freshness threshold. Model/API/account support and measured runtime behavior are distinct evidence levels.

## Evaluate

From the plugin root:

```sh
python3 -B scripts/evaluate_routes.py requirements.json --output evaluation.json
```

Use `--registry assessment-local/data/capabilities.json` for a reviewed, pinned copy. `--as-of YYYY-MM-DD` reproduces historical results; it does not establish current support. The evaluator is offline and makes no cloud or model calls.

Requirements retain `id`, `source_model`, `source_api`, `required_features`, `models`, `endpoints`, `apis`, `entry_regions`, `geography`, `single_region`, `residency_scopes`, `retention_mode`, `store`, `cache`, `allow_orchestration`, `external_web_access`, and `assumptions`.

New fields: `partition` (`aws` by default or `aws-us-gov`), `service_tier` (`standard` by default), `context_tokens`, `max_output_tokens`, and optional lists `preferred_features`, `preferred_models`, `preferred_apis`, `preferred_endpoints`. Preferences never override mandatory incompatibilities. The list order of preferences is not a weighting system. Unknown keys, features, invalid types and nonfinite numbers fail validation.

`geography` accepts US, IN, EU, UK, CA, APAC or unrestricted. Omit unresolved geography to retain VERIFY. `single_region` is an exact Region string. Entry Region does not establish processing geography. Canadian entries to US-labeled profiles remain conditional where destination routing requires verification. GovCloud is a separate partition and is never implicitly included by a commercial default.

`residency_scopes`: processing, cache, stored_responses, logs, abuse_retention, tools, backups. Nonprocessing boundaries require end-to-end configuration evidence. `retention_mode`: unknown, none, default, aws_review, provider_data_share. `store=false` is not ZDR. Account/model ZDR eligibility is separately verified.

`cache` accepts `mode` (either, implicit, explicit, application_response), `prefix_tokens`, `breakpoints`, `max_retention_minutes`. Prompt cache controls require prompt_caching in required_features. Limits and supported modes are route-specific. A TTL is not an upper deletion guarantee. Cache writes and reads are distinct costs; hit rates require measurement. Whole-response caching needs a separate authorization/invalidation design.

## Results and route choice

Evaluate the complete required subset on each exact route. Priority: NO, VERIFY, ORCHESTRATED, YES. Never union features across models or APIs. A YES is documented compatibility for the supplied requirements, not account access, residency certification, model quality or a successful execution.

Within each status, explicit preference matches order candidates; remaining ties use route IDs for deterministic output. This is not a cost/quality score. Codex records a selected candidate, rationale, alternatives, tradeoffs and next validation in the assessment. Pricing is preserved as dated model-card rows with context/tier/routing labels. Match the relevant row and measure workload volumes; never apply a single universal cache discount or invent a missing rate.

The catalog now distinguishes native feature gaps including asynchronous tool calls, model WebSockets, mid-turn steering, hosted file search, hosted multi-agent execution, remote MCP, shell tools and image-generation tools. Client tools and provider-hosted execution are different contracts. Workarounds belong in a repository-specific gap design; they do not turn the native feature to YES.

Model-specific interactions matter. GPT-6.1 Sol documents schema output with streaming; several other cards only document non-streaming schema output. Newer model cards document cache/Guardrails combinations that older APIs lack. Use the records, not a blanket rule that caching always requires Responses or always conflicts with inline Guardrails.

## Assessment integration

For each AI role, save requirements and evaluation JSON, and pin the evaluated registry plus its evidence under compatibility/. Record `registry`, `requirements` and `evaluation` paths with `ai_role_id` in compatibility/index.json. New code assessments use revision 3, retaining the route-selection and gap-design fields from revision 2. Both full report modes also follow shared-report.md and bind their route table to saved evaluations.

```sh
python3 -B scripts/verify_advisor_assessment.py OUTPUT_DIRECTORY
python3 -B scripts/verify_advisor_assessment.py OUTPUT_DIRECTORY --historical
```

The default reproduces the recorded result and checks current compatibility. Historical mode checks the saved date only. Hashes bind a result to its exact registry. A repository-only exception still permits an index entry with a substantive not_run_reason and unverified target decisions; it does not permit fabricated evaluations.
