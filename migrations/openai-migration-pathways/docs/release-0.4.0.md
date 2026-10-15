# OpenAI Migration Pathways 0.4.0

Evidence reviewed October 14, 2026. Authors: Sudeesh and EB Khiyami.

## Scope

Nine Bedrock targets: GPT-6 Astra, GPT-6.1 Sol, GPT-6 Sol, GPT-6 Luna, GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna, GPT-5.5 and GPT-5.4. GPT-OSS and Daybreak are excluded. Other source models can still be inventoried as migration inputs.

The catalog contains 90 model/API/routing definitions, covering 1,050 route/entry-Region combinations, 34 features, 48 captured official documents and 63 model-card pricing rows. Region candidates with unresolved availability or geography are marked conditional; counts are not a count of production-verified routes.

## Changes

- Replaced the September three-model seed with hash-pinned AWS and OpenAI snapshots. Markdown preserves support indicators and table structure. Source records distinguish direct OpenAI facts from Bedrock claims. Fetching a page never promotes capabilities automatically.
- Registry schema 2 records per-route caching modes, limits, service tiers, schema/streaming interactions, partitions, Region qualifications, dated prices and source-model context.
- Evaluations bind to the exact registry hash and date. Hard requirements precede explicit preferences; deterministic ties are not quality rankings. No cloud calls or model calls are made.
- New assessments use revision 2: exact selected candidate, rationale, alternatives, tradeoffs and per-feature gap designs. Gap designs require affected files, control flow, state, failures, semantic differences and tests. Implemented/verified labels require corresponding artifacts.
- Historical assessments pin their registry and evidence. Historical replay and current freshness checks are separate operations. Revision-1 assessment structure remains readable; registry-v1 evaluations use the preserved prior plugin release.
- Updated generated catalog, six-sheet workbook, examples and adapter route export. The workbook now exposes exact routes, feature claims and qualification rules rather than the old 13-feature full mesh, which cannot represent 34 features and model-specific interactions faithfully. The Python evaluator remains the combination authority.
- The Responses helper uses documented exact routes, adds the approved model slugs and removes the obsolete Terra Runtime rejection. Legacy sol/terra/luna aliases retain their GPT-5.6 meaning. Copy approved-routes.json with the adapter.
- The deployment portal explicitly blocks unsupported profile/Mantle account-availability verification rather than implying its foundation-model query can verify those routes.

## Important reviewed differences

GPT-6.1 Sol documents caching on Responses, Chat Completions and native Runtime APIs, with explicit caching unavailable on Converse. It documents streaming JSON-schema output and a different cache-read rate from GPT-6 Sol. GPT-6 Sol/Luna cards document broader inline Guardrails support, while Astra/5.6/5.5/5.4 have narrower documented combinations. GPT-5.5/5.4 support implicit caching; explicit caching is a separate unsupported requirement in the reviewed routes.

AWS GPT-6.1 Sol limits differ from the direct OpenAI model card. They are stored separately, not silently equated. Some US-profile destination tables include Canadian locations for Canadian ingress; those entries remain conditional for US residency. The GPT-6.1 Sol card does not enumerate Global ingress Regions, so included Global entry candidates remain VERIFY. Astra Runtime caching and several schema/streaming/tool contracts need more specific evidence and remain VERIFY.

Mantle custom Projects include Chat Completions. AWS documents PrivateLink services for both Runtime and Mantle; actual network configuration is separately verified.

## Validation and boundaries

See validation-report.json for test results and scenario summaries. Offline regression tests cover evaluator rules, catalog policy, evidence hashes, historical replay, revision-2 assessment contracts, the actual adapter Route class and saved-XLSX parity. Syntax, skill structure, generated exports and visual workbook checks were performed.

These checks do not establish AWS account access, quotas, model quality, production latency, deployed networking or a migrated customer application. Application-specific non-model helpers retain their earlier dated verification scope. The portal needs an account-specific verifier for the catalog's profile/Mantle routes before offering deployment.

One supplemental guessed Guardrails documentation URL was unavailable; the reviewed model cards and existing official API documentation provide the cited support evidence. No claim depends on that unavailable page. Its attempt is retained in data/refresh-receipt.json and removed from the maintained fetch manifest.

## Refresh and rollback

Follow refreshing-evidence.md for candidate collection, review, regeneration and validation. Retain the previous source/archive for rollback. Existing assessments are not rewritten when installing this release. Start a new Codex chat and select the updated plugin after installation.
