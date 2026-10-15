# Deployment package

Create a portable output directory in the authorized workspace. Do not write generated artifacts into the installed plugin. Use paths relative to the output root and include the resolved repository commit. Do not copy credentials or secret-bearing environment files.

Suggested layout (omit genuinely inapplicable sections and explain why):

```text
assessment.md
assessment-contract.json
report-contract.json
evidence.json
service-mapping.json
service-mapping.md
architecture/
  architecture.json
  migration-deployment-architecture.drawio
  migration-deployment-architecture.svg
  icon-notices/
deployment/
  README.md
  ai-routes.json
  terraform/
  application/
  tests/
migration-waves.md
validation.json
checksums.sha256
```

## Evidence and assessment

Follow [assessment-report.md](assessment-report.md) for the mandatory main report
and complete route/model/API contract. Before sealing a deployment package, run
`python3 -B scripts/verify_assessment.py OUTPUT_DIRECTORY --package --render`
from the plugin root. This renders the model and API analysis into assessment.md,
exports deployment/ai-routes.json and checks route links to services, graph nodes
and implementation capabilities. The package checker now requires this contract;
an old package needs an explicit assessment upgrade before it can pass.

Record repository URL, requested ref, resolved commit, assessed scope, relevant file paths/lines, and discovery source/time. Keep Azure resource IDs in the customer's local artifacts; sanitize any shared example. Separate observed resources, repository-inferred intent, target decisions, and unknowns.

Cover application entry points and dependencies, repository-to-resource bindings, source-to-target mapping, data and identity changes, availability and recovery requirements, known gaps, and cost drivers. Do not call estimates quotes. Highlight missing inventory or requirements where they affect decisions, without making unrelated output contingent on them.

Create `service-mapping.json` using contract `azure-aws-service-mapping-v1` and render the customer-readable `service-mapping.md` with `scripts/render_service_mapping.py`. Each entry must identify Azure source node IDs, AWS target node IDs, capability, migration pattern, decision state, substantive rationale, required application or operational changes, and package-relative evidence. Do not imply one-to-one equivalence: record refactoring, retained services, unresolved targets, and alternatives honestly. The package checker validates graph references, evidence paths, and exact JSON/Markdown parity.

## Deployment source

When the user requests a deployment button or interactive deployment, read `../../../docs/deployment-page.md`. Include `deployment/target.json` before sealing, and link the final report to the customer-operated deployment page. Use **Prepare AWS deployment** until required builds and ports are verified; the runner enforces preflight and saved-plan approval. Start `scripts/deployment_portal.py` only in the customer's approved execution environment. Generating this page does not authorize applying its Terraform.

For a live deployment handoff, run `scripts/deployment_portal.py PACKAGE --run-directory NEW_PRIVATE_DIRECTORY --launch` on the customer's browser host, verify the returned session, and give the user its live report link. The report button enters that authenticated session directly. Do not hand off the offline export as a live deployment experience. If Codex runs remotely, explain the need for an approved connection to the customer runner; never link the publisher's localhost as if it were reachable by the customer. Starting the runner makes no cloud calls; cloud checks and apply still require the page's separate approvals.

Supply coherent Terraform or the user's chosen IaC for the proposed target, with declared versions, input variables, outputs, and sample non-secret inputs. Reuse repository conventions where reasonable. Account/Region, artifact digests, domains, model routes, and secret references must be explicit inputs, not developer-specific defaults.

For an ALB/private-Fargate target, read [fargate-hosting.md](fargate-hosting.md) and adapt the bundled hosting source where it fits. It supplies network, service and optional Redis resources, not a completed application migration. Use another implementation when the workload needs a different hosting model.

Include the application changes or patches required for the design. Inventory each workload's build context, startup command, configuration, health/readiness behavior, exposed ports, dependency services, and supported CPU architecture. Do not ship an unported Azure application behind AWS infrastructure and call it migrated.

Include `implementation-ledger.json` linking every material workload/capability to source evidence, target component IDs, the actual implementation/patch paths provided, required tests, and a status (`implemented`, `architecture_only`, `blocked`, or `verified`). Record absent linked repositories as source gaps. Infrastructure foundations and standalone transport helpers cannot satisfy an application-port entry. Preserve actual protocols: Redis pub/sub and task queues are not interchangeable with SQS, and local stdio MCP servers do not acquire an HTTP deployment contract by moving to AWS.

Ledger shape: `{"capabilities": [...]}`. Each entry has `id`, `component_id` (from validation.json), `source_evidence` (references), `target_node_ids` (from the graph), `status`, `implementation_paths` (package-relative files), and `required_tests` (acceptance criteria). Cover every required component. Implemented/verified entries need actual source files. A verified entry needs at least build-level component evidence; unresolved required capabilities prevent build/deployment promotion. The checker enforces linkage, not whether an implementation faithfully meets its requirements.

For container workloads, include a build recipe and portable commands. Registry publishing, remote builders, and CI service integration are optional execution choices, not prerequisites for using this plugin. If images have not been built, do not fabricate image digests or claim the build has passed.

Check the actual build context, not only the Dockerfile directory: secret/cache exclusion rules must apply to that context. Match the application's real environment-variable names, listening port and health route to the image and task definition. A declared EXPOSE port does not set the process port. Remove interactive login only as part of an explicit target credential/configuration change. Check generated files and caches against the read-only filesystem and scratch-volume contract, including cleanup during concurrent operations.

Include least-privilege runtime roles, secret injection by reference, network boundaries, storage encryption, logs/alarms, and health checks as applicable. IAM policy changes and networking choices need application-specific justification rather than wildcard boilerplate. Prevent accidental application of incomplete critical inputs through validation or a clearly non-deployable example configuration.

For Python applications using Application Insights wrappers, read [python-telemetry.md](python-telemetry.md). The bundled adapter removes that telemetry credential dependency, preserves the sample logger interfaces, and supports container logs plus explicitly configured OTLP traces. It does not port unrelated Azure clients or provision a trace collector.

For background queue workers, read [python-workers.md](python-workers.md). Retain task ownership and test shutdown ordering; changing the hosting service does not make a queue durable or clean up untracked listeners.

For a text-only, no-tool analysis agent, inspect `../../../assets/python-bedrock/README.md` and its `bedrock_json_agent.py` source. The adapter provides application-owned history, explicit Runtime/Mantle routes and local schema validation with bounded repair. Adapt it only after confirming the actual consumer contract. It does not port Foundry-hosted tools, streaming or distributed thread storage. Keep endpoint, inference geography and credentials explicit; never reject `bedrock-runtime` merely because an older helper implemented only Mantle.

The deployment README must distinguish:

- Required customer inputs and access prerequisites.
- Local/static validation and expected outputs.
- Build and registry publication steps, if needed.
- Planning, approval, and deployment steps with potential costs.
- Smoke tests, data reconciliation, rollback, and cleanup responsibilities.

Do not run Terraform apply/destroy, push images, create CI resources, or mutate either cloud while merely preparing the package. Terraform planning that refreshes cloud state also requires approved cloud access. If dependency downloads are needed for validation, stay within the configured permissions.

## Migration and validation

When implementation or execution is requested, read [application-checks.md](application-checks.md) to choose checks that exercise the changed application, not only copied helpers. Repository assessment alone does not authorize executing customer code.

Migration waves reference the same component IDs, AI routes, and target decisions as the architecture. Include coexistence, cutover criteria, reconciliation, rollback limits, and decommission approval. Waves belong in the migration document, not as the architecture's primary shapes.

Record validation checks as `passed`, `failed`, `blocked`, or `not_run`, with command/tool, scope, evidence, and reason. Summarize package readiness separately:

- `source_only`: source generated, execution not demonstrated.
- `statically_checked`: relevant syntax/schema checks passed; runtime behavior unproven.
- `build_verified`: actual builds passed for specified workloads/platforms.
- `deployment_verified`: an explicitly approved deployment and defined smoke tests passed in the named environment.

For mixed results, list per-component status and do not promote the whole package beyond its least-verified required component. A fixture build verifies the fixture, not a customer application. Missing builders affect the build claim, not whether an assessment can be delivered.

Check that report, IaC, application configuration, diagram, and waves agree on resources, protocols, model routes, and Region. Generate a SHA-256 manifest of final artifacts (excluding itself); it supports integrity checking, not publisher authentication. Package output only after removing secrets, temporary checkouts, caches, and unrelated files.

## Bundled consistency check

The helper is `../../../scripts/verify_package.py` relative to this reference. From the plugin root, after finalizing all artifacts:

```bash
python3 -B scripts/verify_package.py /absolute/path/package --seal
python3 -B scripts/verify_package.py /absolute/path/package
```

The first command creates `checksums.sha256` only if it does not already exist. The second rechecks every file and detects changed, added, or removed artifacts. Keep the archive outside the package directory. It also requires that both architecture renderings exactly match the graph and that `source_commit` in `evidence.json` matches the graph's commit.

Use this `validation.json` structure:

```json
{
  "readiness": "source_only",
  "components": [{"id": "app", "readiness": "source_only", "required": true}],
  "checks": [{
    "id": "app-build",
    "category": "build",
    "status": "not_run",
    "scope": ["app"],
    "evidence": [],
    "reason": "No application image has been built"
  }],
  "blockers": []
}
```

Check categories are `static`, `build`, `deployment`, `smoke`, `visual`, and `coverage`. Evidence entries are existing package-relative files; passed checks need saved evidence. Scope contains component IDs. Each claimed readiness level needs matching passed checks for that component (static; static plus build; or static plus build plus deployment and smoke). A failed, blocked, or unrun check in a claimed stage prevents promotion. Record the narrow subject of each check: a source scan is not an application test.

The helper verifies declared consistency, not evidence authenticity, credential safety in arbitrary file content, cloud access, service feature parity, or Terraform correctness. Review those separately. It rejects obvious credential/state filenames and caches, but that is not a complete secret scanner. A source-only package can pass the consistency check while still listing migration blockers.

New application checks should include an `execution` annotation with `subject` (`application`, `helper`, or `fixture`), `mode` (`source`, `fragments`, `import`, `local`, `build`, or `deployed`), a non-secret `environment` description, and a `substitutes` list naming mocked services/transports. The checker rejects contradictory annotations and does not use local, helper, or substituted checks to establish deployment readiness. Older receipts without this annotation remain compatible; their scope still needs review.

## Release 0.4 catalog and assessment binding

New code assessments use revision 3 and pin the exact evaluated registry/evidence. The deployment route export additionally carries the selected candidate ID and gap implementation statuses. Consume those records consistently; design_only gaps are not application implementations. The generated approved-routes.json beside the Responses adapter lists transport configurations, not native schema/tool support or account access. Copy both files if adapting that helper.

The target policy includes only the nine approved core models. GPT-OSS and Daybreak are excluded. The deployment portal's generic foundation-model availability query cannot validate inference profiles or Mantle-only routes and now blocks them explicitly. Supply a scoped account-specific verifier before claiming those routes are deployment-ready.
