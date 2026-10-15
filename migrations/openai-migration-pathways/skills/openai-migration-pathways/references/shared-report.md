# Shared discovery and code-assessment reports

Use this standard for full saved reports. Brief advisory answers stay proportionate
to the question. Both modes write `assessment.md` and `report-contract.json`.
Code mode also uses assessment-contract.json revision 3 and its existing checks.
Historical revisions 1 and 2 remain readable.

## Main sections

Use these exact level-two headings in order. Each needs substantive findings or
an explanation of why it does not apply, beyond the generated tables.

1. `Decision and target-model recommendations`: exact candidate, alternatives,
   rationale, tradeoffs and open approvals; separate documentation from live results.
2. `Scope, evidence and execution provenance`: requirements, assumptions, scope,
   confidence, omissions and actual work. Discovery uses supplied descriptions;
   code mode records commits, inspected files and nested-source provenance.
3. `Workload and route inventory`: application routes and AI roles, source
   interfaces, target configurations, compatibility and evidence.
4. `Source AI contracts`: inputs, outputs, parameters, tools, history, streaming,
   identity, errors and retention. Label unconfirmed behavior.
5. `Bedrock feature mapping and API migration`: feature/API changes and a
   linked table of **existing and proposed orchestration designs**.
6. `Azure-to-AWS service mapping`: source capabilities/services, evidence state,
   AWS targets, migration approaches, changes and dependencies.
7. `Unified architecture and data flows`: processing, retrieval, history,
   caching, safety, logs and backups; actual versus proposed boundaries.
8. `Deployment implementation and gaps`: the **central gap and blocker register**,
   concrete mismatches, impact, priority, owners and implementation status.
9. `Validation, readiness and next actions`: component readiness, open decisions,
   migration stages, acceptance tests, costs, rollout and rollback.

Every report requires four linked tables: routes (section 3), orchestration
(section 5), service mappings (section 6), and gaps/blockers (section 8).
Reference central gap IDs elsewhere instead of maintaining conflicting findings.
A gap describes a difference or missing work; its `blocks` list identifies
which stages cannot proceed. Unknown information is not evidence of absence.

Retain the original native-feature blocker when proposing a workaround.
Evaluate revised requirements separately and record acceptance. Acceptance of
a design neither implements it nor authorizes deployment. Route compatibility,
implementation status and deployment readiness are separate claims.

Code reports also compare **application expects → deployment supplies → mismatch
→ required change → test** where configuration/build/health contracts matter.
Check business meaning and input sufficiency as well as JSON validity.
Distinguish confirmed scope from confidence in evidence. Missing Azure
information stays unresolved; direct OpenAI workloads need no invented Azure service.

## JSON contract: migration-report-v1

Root fields: `contract`, `mode` (`discovery` or `code_assessment`), `source_commit`
(null in discovery; matching code commit otherwise), `scope`, `limitations`,
and all six arrays below. IDs are unique within each array. Evidence references
are IDs; file references stay inside the report output directory.

| Collection | Required fields |
|---|---|
| `evidence` | `id`, `kind`, `description`, `path` to saved evidence |
| `workloads` | `id`, `name`, `description`, `scope_status`, `evidence` |
| `routes` | `id`, `workload_id`, `ai` boolean, `source_interface`, `purpose`, `rationale`, `evidence`, `evaluation` |
| `blockers` | `id`, `finding`, `kind`, `priority`, `status`, `route_ids`, `service_mapping_ids`, `impact`, `owner`, `resolution`, `blocks`, `required_tests`, `evidence` |
| `orchestrations` | `id`, `name`, `origin`, `acceptance`, `implementation_status`, `route_ids`, `service_mapping_ids`, `blocker_ids`, ordered `control_flow` strings, `state`, `permissions`, `failure_handling`, `behavior_difference`, `required_tests`, `evidence` |
| `service_mappings` | `id`, `workload_ids`, `route_ids`, `source_service`, `source_evidence_state`, `target_service`, `pattern`, `decision`, `rationale`, `required_changes`, `dependencies` (mapping IDs), `evidence` |

Save the supplied summary as evidence even when no repository exists.
Evidence `kind`: `user_description`, `repository`, `cloud_inventory`,
`official_documentation`, `assumption`, `validation`. Discovery cannot claim
repository inspection. Workload `scope_status`: `confirmed`, `conditional`, `excluded`.

AI route `evaluation` contains local `registry`, `requirements`, `evaluation`
paths and nullable `selected_candidate_id`. Pin the registry and snapshots.
Unknown requirements can still be evaluated conditionally. When evaluation
cannot run, use null plus a substantive `not_run_reason`; this remains VERIFY.
Non-AI routes use null and never select a model. Explain alternatives in section 1;
the evaluation preserves every candidate and reason.

Blocker `kind`: `incompatibility`, `missing_information`, `implementation`,
`conflict`. `priority`: `high`, `medium`, `low`. `status`: `open`, `deferred`,
`resolved`. `blocks` is a list drawn from `route_selection`, `implementation`,
`validation`, `cutover`, and can be empty for a non-gating gap. An unknown owner
is explicitly "Unassigned—owner decision required." Resolved findings need
`resolution_evidence` IDs. NO/VERIFY routes require an open or deferred entry.
The central register includes infrastructure and non-AI findings.

Orchestration `origin`: `existing`, `proposed`. `acceptance`: `proposed`,
`accepted`, `rejected`, or `not_required` for existing flows only.
`implementation_status`: `design_only`, `implemented`, `verified`, `blocked`.
Accepted flows need `acceptance_evidence` IDs for the real decision.
Implemented/verified flows need existing `implementation_paths`; verified flows
also need `validation_evidence` IDs. New implemented designs must be accepted.
ORCHESTRATED evaluations require a linked accepted design.

Mapping `source_evidence_state`: `reported`, `repository_inferred`,
`cloud_confirmed`, `not_reported`, `not_applicable`. Cloud confirmation requires
inventory evidence; repository inference requires inspected code evidence.
`pattern`: `rehost`, `replatform`, `refactor`, `replace`, `retain`, `retire`,
`unresolved`. `decision`: `confirmed`, `recommended`, `conditional`, `unresolved`.
Use an explicit unknown target string when unresolved. `required_changes` is a
nonempty list, including the next investigation when the target is unknown.

`empty_reasons` supplies a substantive explanation for each empty collection:
`workloads`, `routes`, `blockers`, `orchestrations`, `service_mappings`.
Optional `source_artifacts` entries have `id`, `origin`, `revision` (or explicit
unknown), nullable `sha256`, `inspected_scope`, `omissions`, `evidence`. Archive
comments and upstream references do not independently prove byte identity.

## Code and deployment integration

Code reports reuse every assessment route ID and AI classification. Evaluation
paths match compatibility/index.json; the candidate matches route_selection.
An unevaluated code AI route uses only the existing repository-only exception.

Every code feature gap appears in the central register through
`assessment_gap_refs: ["route-id:gap-id"]`; related gaps may share one entry.
Each gap of kind `orchestration` also links to an orchestration entry using
those references. Every recorded route and gap must be accounted for.

Deployment packages reuse service-mapping.json IDs and matching source/target
service, pattern, decision, rationale and changes. Existing graph and
implementation-ledger checks remain applicable.

## Render and verify

Create the nine headings and explanatory prose first. For discovery:

```sh
python3 -B scripts/verify_report.py OUTPUT_DIRECTORY --render
python3 -B scripts/verify_report.py OUTPUT_DIRECTORY
```

For code assessment, these commands also handle the shared tables:

```sh
python3 -B scripts/verify_assessment.py OUTPUT_DIRECTORY --render
python3 -B scripts/verify_advisor_assessment.py OUTPUT_DIRECTORY
```

Use `--package` on the assessment check for deployment bindings. `--historical`
replays saved dates only; normal checks detect stale evidence. Edit canonical
JSON and rerender instead of changing generated tables. Validators check
declared consistency, not source completeness, genuine approvals or runtime success.
