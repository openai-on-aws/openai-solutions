# Complete assessment and AI route contracts

Use this reporting contract for every new assessment. It addresses coverage and
presentation consistency; it does not authorize customer-code execution or cloud
access. Preserve an explicitly requested alternative format by retaining all
required content and the machine-readable inventory.

Release 0.4.1 code assessments use `assessment_revision: 3` and also follow
[shared-report.md](shared-report.md). Its linked routes, central gaps/blockers,
orchestrations and Azure-to-AWS mappings are mandatory even without a deployment
package. The nine main headings below remain unchanged.

## Evidence boundaries and provenance

Use repository evidence to establish source behavior. Use current official
AWS/OpenAI (and Azure where relevant) documentation to establish target service
semantics, exact model IDs, endpoint/API combinations, features and inference
geography. Repository-only discovery with no cloud inventory does not itself
prohibit public documentation. If the user explicitly restricts **all evidence**
to the repository, honor that restriction: list the target decision as unresolved
or provisional, state which verification is missing, and do not invent availability.

Record the actual loaded skill path, plugin manifest version and SHA-256 of the
loaded SKILL.md, the source commit, and evidence policy. If a requested skill is
unavailable, name the actual fallback; do not claim the requested plugin ran.
Never freeze a model catalog or example model name into this workflow. Preserve
the user's provider/model policy; OpenAI-only excludes other providers and must
not silently become a GPT-OSS substitution.

## Main assessment

Write `assessment.md` with these level-two headings in this order. Additional
subsections are welcome. Each section needs substantive findings, or a reason it
does not apply. A link to another artifact alone is insufficient.

1. `Decision and target-model recommendations`: name the proposed model for each
   AI role, exact ID/profile where verified, rationale, Region, endpoint/API,
   alternatives or fallback policy and evaluation criteria. Label unverified
   candidates and absent decisions prominently. For no-AI workloads, explain why
   no model is recommended.
2. `Scope, evidence and execution provenance`: source commit, scoped/shared
   dependencies, inspected coverage, omissions, actual skill/version, evidence
   restrictions, and what was not executed.
3. `Workload and route inventory`: all in-scope HTTP APIs, WebSockets, workers,
   scheduled/local tools and outbound calls; distinguish runtime and optional
   development workloads. Trace indirect AI callers to their concrete AI calls.
4. `Source AI contracts`: call sites, SDK methods, deployment aliases versus
   verified source models, request/response shapes and operational behavior.
5. `Bedrock feature mapping and API migration`: complete route-by-route mapping,
   field translation, representative source/target requests and target responses,
   identity refresh, tool lifecycle, state, streaming events, errors and retention.
6. `Azure-to-AWS service mapping`: readable capability/service decisions,
   rationale and gaps, consistent with the canonical service mapping.
7. `Unified architecture and data flows`: explain paths and boundaries using the
   same route, mapping and graph IDs; link the unified Draw.io/SVG if requested.
8. `Deployment implementation and gaps`: actual supplied changes, missing ports,
   configuration bindings and route acceptance criteria.
9. `Validation, readiness and next actions`: source/documentation/static/build/
   runtime evidence separately; migration, rollback and unresolved decisions.

Create `assessment-contract.json` using the schema below. Run:

```bash
python3 -B scripts/verify_assessment.py OUTPUT_DIRECTORY --render
python3 -B scripts/verify_assessment.py OUTPUT_DIRECTORY
```

`--render` populates four generated blocks in the existing main assessment:
`models` in section 1, `routes` in section 3, `source-contracts` in section 4,
and `api-mapping` in section 5. It appends a block to its section when absent.
Keep explanatory prose around the tables. The checker compares these blocks to
the JSON so model/API detail cannot drift into a companion file or disappear.
Edit canonical JSON and rerender; do not hand-edit generated blocks.

## Inventory and coverage method

Inventory scoped files first. Inspect framework route registrations, browser
callers, consumers, SDK constructors and invocation sites, shared wrappers,
configuration and local/evaluation tools. Text search is discovery evidence,
not proof of semantic coverage. Record each discovered entry point/call site once
in `discoveries`, including exclusions with reasons; connect included discoveries
to `routes`. A route may group multiple sites only if their contract is identical
and all sites are cited. Do not combine materially different roles, schemas,
parameters or target models into one generic "AI" route.

Walk each application trigger through queues/tools to its AI calls. A non-model
route gets an explicit non-AI disposition, not a fabricated Bedrock equivalent.
An indirect route lists the AI call IDs it can reach. Account separately for
embeddings, retrieval, speech, moderation, document/image handling, state,
tool execution and event delivery. Each may require an AWS service, application
code, retained integration or explicit gap rather than a model feature.

For every AI call, map all feature categories below, even if the source lacks the
feature. Explain `not_applicable` from source evidence. Do not equate a Responses
HTTP port with migration of managed threads, hosted tools, retrieval or agents.
Keep browser WebSockets and model streaming separate. Never infer feature
support from a model family, another endpoint, or a generic API guide.

## Canonical JSON schema (contract `azure-aws-assessment-v1`)

Fields listed here are required unless explicitly optional. Text values must be
substantive strings; use an explicit unknown with its consequence where source
evidence is missing. Package paths are relative and must identify saved files.
Stable IDs are unique within each collection.

Root:

- `contract`, `source_commit`: resolved repository SHA.
- `provenance`: `plugin_name`, `plugin_version`, `skill_path`, `skill_sha256`.
- `evidence_policy`: `repository_only` or `repository_and_official_docs`.
- `model_policy`: `allowed_providers` (string list, empty if unrestricted; use
  `["openai"]` for OpenAI-only) and `constraint` (user's model/family constraints,
  including the exclusion of GPT-OSS and Daybreak). The checker enforces provider IDs; review
  family/model constraints semantically.
- `coverage`: `status` (`complete` or `partial`), `scope` (text),
  `reviewed_paths` (nonempty string list), `discovery_evidence` (nonempty package
  file list), `omissions` (string list; required nonempty for partial),
  `no_ai_reason` (text; required only when there are no AI calls).
- `discoveries`: objects with `id`, `kind`, `source_location`, `evidence`
  (nonempty package file list), `disposition` (`included` or `excluded`),
  `route_id` (included route ID; null for exclusions), `reason`.
- `models`: model decision objects below; may be empty if unresolved/no AI.
- `routes`: route objects below; may be empty for a library/static data scope
  only when coverage explains no AI and discoveries explain the inspected scope.

Model decision:

- `id`, `provider`, `name`, `model_id` (nullable), `region`, `endpoint`,
  `base_url`, `inference_path` (full HTTP request path, including API prefix),
  `api`, `inference_geography`, `rationale`, `fallback_policy`,
  `evaluation_criteria` (nonempty string list).
- `verification`: `documented`, `unverified`, or `blocked`. Documented requires an
  exact model/profile ID and at least one official source; this is not a claim
  of account access or runtime testing.
- `verification_notes`: feature/document conflicts, constraints and remaining
  checks; do not claim runtime success from documentation.
- `official_evidence`: list of objects with `url` (official HTTPS reference),
  `snapshot_path` (saved package file), `checked_at` (ISO date/time), `supports`
  (nonempty list drawn from `model_id`, `region`, `endpoint`, `api`,
  `inference_geography`). Documented decisions collectively need all five claims.
  Empty for repository-only evidence; decisions then cannot be documented.

Route:

- `id`, `kind` (`http`, `websocket`, `worker`, `scheduled`, `local`, `tool`,
  `external_call`, `ai_call`), `workload`, `runtime_scope` (`runtime` or `optional`),
  `source_location`, `trigger`, `purpose`, `evidence` (nonempty file list).
- `ai_usage`: `direct` for ai_call, `indirect` for AI callers, `none` otherwise.
- `ai_route_ids`: direct has only its own ID; indirect has reachable ai_call IDs;
  none has an empty list and explains no Bedrock mapping in `disposition`.
- `disposition`, `acceptance_criteria` (nonempty string list).
- `service_mapping_ids`, `target_node_ids`, `capability_ids`: lists referencing
  service-mapping.json, architecture JSON and implementation ledger. At least one
  service mapping and capability per route in deployment packages; graph IDs
  may be empty for a documented unresolved target.
- AI calls additionally require `source_contract`, `model_ref` (model decision ID
  or null), `target_gap` (nonempty if no model selected), `feature_mapping`,
  `examples`.
- `source_contract`: text fields `sdk_method`, `source_model`, `instructions`,
  `input`, `output`, `parameters`, `tools`, `history`, `streaming`, `auth`,
  `errors`, `retries`, `retention`, `modalities`.
- `feature_mapping`: exactly one object for each category `instructions`, `input`,
  `output`, `parameters`, `tools`, `history`, `streaming`, `auth`, `errors`,
  `retries`, `retention`, `modalities`. Each has `feature`, `source_behavior`,
  `target_behavior`, `implementation` (exact Bedrock API/field, application
  adapter, AWS service or unresolved requirement), `status`
  (`supported`, `application_change`, `other_service`, `unsupported`, `unverified`,
  `not_applicable`), `evidence` (package files). Supported claims need official
  evidence files listed by a model decision, not just repository snapshots.
- `examples`: `source_request`, `target_request`, `target_response` strings.
  Use sanitized illustrative snippets, never customer payloads. If the target
  cannot be specified, explain the missing decision in place of invented JSON.
  Show parameter removal, response extraction/schema validation, tool output
  continuation and streaming/event translation where applicable.

## Deployment binding and verification

For deployment packages, export `deployment/ai-routes.json` with `--render`.
It contains `contract: azure-aws-deployment-routes-v1`, the source commit and one
row per AI call: `route_id`, `model_ref`, `model_id`, `region`, `endpoint`,
`base_url`, `inference_path`, `api`, `inference_geography`, `verification`. Unselected decisions use
null fields and `unresolved` verification. It is the canonical proposed route
input, not a working adapter or permission to deploy.

Make generated application/IaC configuration consume this file or document the
exact configuration translation and check it. Mirror no model literal without
an explicit consistency check. Unsupported routes must remain deployment gaps.

`verify_assessment.py` checks declared discovery/route coverage, AI caller links,
complete contracts, documented-model evidence references, main-report parity and,
for packages, service/graph/ledger links and exact deployment export parity.
`verify_package.py` requires these artifacts for newly generated packages.
Legacy packages without this contract must be upgraded before passing the new
checker; their original checker remains appropriate for historical verification.

The checker cannot discover omitted code, authenticate source claims, verify
official documentation content, compare arbitrary IaC semantics, or establish
model quality. Perform those reviews explicitly. Missing decisions may pass as
visible gaps; missing analysis must fail. A partial assessment can be delivered,
but must display its omissions and must not claim complete repository coverage.

## Revision 2: route decisions and gap designs

Release 0.4.0 introduced `assessment_revision: 2`; release 0.4.1 uses revision 3, retaining all revision-2 fields and adding the shared report contract. The base contract name is unchanged. Earlier revision-1 and revision-2 artifacts remain historically readable. Approved targets are the nine models in `data/capabilities.json`; source inventory is not limited to those models.

Each AI route has `route_selection`: `selected_candidate_id` (exact evaluation row ID, nullable if unresolved), `rationale`, `tradeoffs`, `alternatives` (list), and `next_validation`. Rank mandatory compatibility before optional preferences. Do not infer measured quality, latency or total cost from the order of rows. Record why the selected candidate fits the actual source behavior and why alternatives were excluded or deferred.

Each AI route also has `gaps` (a list, empty when genuinely no gaps). Cover every feature mapping whose status is neither supported nor not_applicable. Each gap requires:

- `id`, `feature` (one of the source-contract categories), `kind` (`application`, `service`, `orchestration`, `blocker`, or `investigation`).
- `affected_files` (source paths/call sites), `evidence` (saved assessment paths).
- `proposed_change`, `control_flow`, `state`, `failure_handling`, `behavior_difference`.
- `required_tests` (observable acceptance criteria).
- `implementation_status`: `design_only`, `implemented`, `verified`, or `blocked`. Implemented entries require `implementation_paths`; verified entries additionally require `validation_evidence`, all existing package files.

Assess native gaps separately from architectural alternatives. An application tool loop, queue, local schema repair or separate safety call does not change the original native feature result. Do not weaken strict schema, atomic safety, retention, residency or authorization requirements. Explain consequences and preserve unaccepted changes as conditional designs.

Generated report blocks include route decisions and gap designs. Pin a local registry and evidence under compatibility/ and set each compatibility index entry's `registry` path. This preserves historical reproducibility after plugin updates. `verify_advisor_assessment.py --historical` reproduces the saved evaluation date only; the default also checks whether current evidence changes its result. Neither mode establishes cloud or runtime verification.
