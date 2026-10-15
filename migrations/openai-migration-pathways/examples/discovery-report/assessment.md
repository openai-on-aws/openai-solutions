# Fictional document-assistant discovery assessment

## Decision and target-model recommendations

**Native migration is blocked.** The saved evaluation finds no compatible candidate for the original hosted-file-search requirement. GPT-6.1 Sol is the requested model to assess, not a verified production selection. Review the application-retrieval proposal before evaluating any changed target contract.

## Scope, evidence and execution provenance

This is a fictional discovery example created from `summary.txt`. No repository commit is applicable. Provider claims come from the bundled October 14, 2026 snapshots; the offline evaluation does not prove account access or runtime behavior.

<!-- report:scope:begin -->
Mode: discovery. Scope: Fictional internal document assistant: model calls, retrieval, hosting and document storage.

Limitations: Description only. No repository, Azure inventory, AWS account, model invocation or deployment inspected. Source model and retention/residency details remain unconfirmed.

| Workload | Scope status | Description | Evidence |
| --- | --- | --- | --- |
| assistant / Assistant | confirmed | Return tenant-authorized answers and citations from uploaded documents | summary |

| Evidence ID | Basis | Description | Saved artifact |
| --- | --- | --- | --- |
| summary | user_description | Synthetic supplied requirements | summary.txt |
| native-evaluation | validation | Offline evaluator output, not a live model test | compatibility/evaluation.json |
| registry | official_documentation | Dated compatibility registry with hash-pinned provider snapshots | compatibility/data/capabilities.json |
<!-- report:scope:end -->

## Workload and route inventory

The generation route covers the described answer flow. No HTTP endpoint, worker, tool implementation or hidden application component is claimed to have been discovered. A code assessment would add actual triggers, wrappers, files and call-site evidence here.

<!-- report:routes:begin -->
| Route / workload | Source interface | Selected target configuration | Compatibility | Rationale | Candidate counts | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| generate / assistant | Azure OpenAI Responses with hosted file_search; source model unconfirmed | No selected candidate | NO | Native hosted file search is required in this evaluation. No compatible candidate is selected; application retrieval is a separate unaccepted redesign. | {'YES': 0, 'ORCHESTRATED': 0, 'VERIFY': 0, 'NO': 10} | summary |
<!-- report:routes:end -->

## Source AI contracts

The supplied source contract names Responses, hosted file search, JSON output, tenant isolation and citations. The exact model, request fields, streaming behavior, token limits, caching, stored history, retention and error behavior still need confirmation. Native tool behavior is a migration requirement until a redesign is explicitly accepted.

## Bedrock feature mapping and API migration

Hosted file search remains a native incompatibility in the saved evaluation. The design below moves retrieval into the application; it is **proposed / design_only**. It does not change the native result. Embedding/index support and the retrieval service configuration require a separate assessment.

<!-- report:orchestrations:begin -->
### Existing and proposed orchestration

| ID / name | Routes / services / gaps | Control flow | State / permissions | Failures / behavior changes | Origin / acceptance / implementation | Required tests |
| --- | --- | --- | --- | --- | --- | --- |
| retrieval / Application-managed document retrieval | generate; model-service; retrieval-service; document-storage; native-file-search; retrieval-implementation | Authenticate the caller and resolve tenant/document grants; Retrieve only permitted document chunks from a separately provisioned retrieval tier; Pass bounded context to the model and collect structured output; Validate citation identifiers against the authorized retrieval set; Return an answer or an explicit no-evidence result | Application owns document ingestion/index state, tool transcript and citation identifiers; retention is unresolved / Enforce tenant and document grants before retrieval and again when resolving citations; scope service IAM independently | Fail closed on authorization errors. Bound retries and timeouts. Do not invent citations or use unrelated documents. / Ranking, chunking, file ingestion, citations and conversation state will differ from hosted file search; parity is unverified | proposed / proposed / design_only | Reject cross-tenant and revoked-document access; Verify citations resolve to permitted source documents; Measure retrieval/answer quality against an agreed dataset; Exercise empty, stale, timeout and duplicate-request cases |
<!-- report:orchestrations:end -->

## Azure-to-AWS service mapping

These mappings use reported services, not a discovered Azure inventory. The alternatives are conditional recommendations. In particular, choosing Bedrock for generation does not automatically choose or validate a retrieval tier, hosting platform or object authorization model.

<!-- report:service_mappings:begin -->
| ID / workloads / routes | Azure source / evidence state | AWS target | Pattern / decision | Rationale | Changes / dependencies | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| model-service / assistant, generate | Azure OpenAI / reported | Amazon Bedrock; exact compatible route unresolved | replace / conditional | Fictional reported source; target requires workload validation and an accepted design. | Confirm source model/API and accepted target feature contract; Port authentication, requests, response parsing and error handling | summary |
| retrieval-service / assistant, generate | Azure OpenAI hosted file search and uploaded files / reported | Application retrieval using a separately evaluated Bedrock Knowledge Base / search tier | refactor / conditional | Fictional reported source; target requires workload validation and an accepted design. | Select and evaluate retrieval/index/embedding configuration; Implement authorization, ingestion and citation contracts; document-storage | summary |
| hosting-service / assistant, generate | Azure App Service / reported | Amazon ECS on Fargate, conditional on packaging and runtime needs | replatform / conditional | Fictional reported source; target requires workload validation and an accepted design. | Inspect application build/startup, identity, networking and health checks | summary |
| document-storage / assistant, generate | Azure Blob Storage / reported | Amazon S3 | replace / conditional | Fictional reported source; target requires workload validation and an accepted design. | Map object keys and access grants; Plan encryption, retention and data transfer | summary |
<!-- report:service_mappings:end -->

## Unified architecture and data flows

Proposed flow: caller → authenticated application → authorized retrieval over migrated documents → Bedrock generation → schema and citation checks → answer. Document ingestion, retrieval state and operational logs need their own retention/residency boundaries. This is a design outline; no deployment diagram or infrastructure implementation is claimed.

## Deployment implementation and gaps

**No application or infrastructure changes have been implemented.** The table below is the central register. A gap describes missing parity, information or work; its blocked-stages column states which decisions or milestones it prevents. Native compatibility and implementation readiness remain distinct.

<!-- report:blockers:begin -->
### Central gap and blocker register

| ID / finding | Affected routes / services | Kind / priority / status | Impact / blocked stages | Owner / resolution | Acceptance tests | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| native-file-search / Required native hosted file search is unavailable on the evaluated Bedrock routes | generate; model-service; retrieval-service | incompatibility / high / open | The source request cannot be ported unchanged / route_selection, cutover | Application owner / Accept and separately evaluate an application retrieval design, or retain the source route | Replay original native requirements without deleting the unsupported feature; Evaluate an explicitly accepted target contract separately | summary; native-evaluation |
| retrieval-implementation / Replacement retrieval flow is a proposal with no implementation or approval | generate; retrieval-service | implementation / high / open | Tenant isolation, citations and failure semantics are not established / implementation, validation, cutover | Application and security owners / Review the proposal, record any acceptance, implement it and run semantic/authorization tests | Cross-tenant and deleted-document isolation; Citation fidelity and no-result behavior; Timeout, retry and duplicate-request behavior | summary |
| source-and-account-details / Exact source contract, deployed Azure resources and AWS route access are unconfirmed | generate; model-service; hosting-service; document-storage | missing_information / high / open | Scope, account availability, retention and whole-system data boundaries cannot be finalized / validation, cutover | Cloud and application owners / Provide exact source configuration and authorize scoped read-only account checks when needed | Confirm actual model/API and request features; Verify AWS permissions, route access and quotas; Trace document, log and state residency | summary |
<!-- report:blockers:end -->

## Validation, readiness and next actions

Offline evaluation replay and shared-table consistency pass. Overall readiness remains blocked by the open gaps. Next: confirm source requirements and account constraints; review the proposed redesign; evaluate the accepted target contract; implement; run authorization, citation, quality, failure and operational tests; then seek cutover approval. The generic deployment portal still lacks an account-availability verifier for profile/Mantle routes.

Reproduce this saved example from the plugin root with `python3 -B scripts/verify_report.py examples/discovery-report --historical`. Omit `--historical` to require current evidence freshness.
