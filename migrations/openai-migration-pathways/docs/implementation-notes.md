# Implementation notes

These notes describe the bundled implementation helpers. They are optional application source, not services that must be installed to use the plugin. All asset paths below are relative to the plugin root.

Start with:

> Use $openai-migration-pathways to assess this GitHub repository: <URL>. Prepare the AWS deployment package and one unified Azure-to-AWS architecture. Do not deploy cloud resources.

You can provide a branch or tag; Codex resolves it to a commit. A local checkout is not required. Private repository access and live Azure discovery use your configured tools and permissions. Without Azure access, the assessment distinguishes repository-inferred architecture from verified inventory.

Outputs include an assessment, migration waves, deployment source, application changes, validation results, and one architecture in JSON, Draw.io, and SVG. Each package records missing requirements and unverified builds.

This plugin runs through Codex. It does not require a custom signed runtime, root-owned trust key, Docker, GitHub Actions, or a publisher's Mac. A builder is needed only to actually verify container builds; cloud deployment requires separate authorization. It does not guarantee arbitrary applications can be automatically ported or deployed without customer-specific work.

Standard-library Python helpers render diagrams and service mappings, verify package hashes, and export reports. Rendering and package checks make no cloud calls. The optional evidence refresher fetches official public documentation into a candidate directory. It never promotes claims automatically. The optional deployment runner makes AWS calls only after approval. Offline regression tests are included in scripts/test_*.py.

The plugin also includes adaptable two-AZ Fargate hosting source: private services, HTTPS ingress, separate service roles, explicit dependency connections and optional TLS Redis. Codex uses it only when that hosting pattern matches the repository. Its developer tests additionally use Terraform and `python-hcl2==7.3.1`; neither is needed simply to load the plugin. Those tests evaluate configuration inputs without downloading an AWS provider or contacting a cloud.

The hosting source supports opt-in Cognito authentication, frontend/API routing under one hostname, generated identity settings and explicit read-only sharing of versioned documents between a session service and worker. See `assets/fargate-hosting/authentication.md`. Applications must implement the matching HTTPS and authorization contracts; template validation is not deployment verification.

The optional standard-library HTTPS helper loads injected backend certificates and removes temporary key files before listening. It is application deployment support, not a signed runtime or trust-key requirement for the plugin. See `assets/python-server/README.md`.

The architecture assets include 36 pinned Azure/AWS icons with source and license metadata. Services without a matching icon use labeled shapes.

Optional Python telemetry source replaces Application Insights wrappers with structured stderr logs and configurable OpenTelemetry traces. Its focused tests include real local OTLP delivery; AWS collector integration and application-specific log privacy still need verification. These application dependencies are not plugin installation requirements.

Optional async worker, Redis subscription and request-tracking helpers add task ownership, cleanup and per-attempt reply matching. Tests include local TLS Redis and timeout/delivery handling. Application-specific queue durability and backend state isolation still need testing; these helpers do not create a hosted runtime.

The optional conversation cache scopes reused state by session, thread, user, credential and configuration, and serializes initialization and invocation on the same remote thread within one worker process. It does not authenticate users, refresh credentials, persist history or coordinate replicas. Its entries live for the process lifetime; application-specific SDK cleanup and cache capacity remain separate work. Use it only as a local state guard, not proof of a production-ready state store.

The optional Redis configuration reader uses explicit versioned keys with a caller-owned async client. Requested versions must exist and pass application validation; they do not silently fall back to defaults. Local TLS tests use separate read-only and provisioning identities. Provisioning, version authorization and model-policy enforcement remain application responsibilities.

Optional S3 image-upload source includes scoped object keys, signed GET URLs and owned SDK cleanup. Its tests exercise actual SDK request validation and offline signing, not a deployed bucket. Application IAM/KMS bindings, URL refresh, other Blob paths and full deployment tests remain separate work.

For ported image services, the hosting template can now generate private S3/KMS resources, per-service permissions and upload settings together. This option is off by default and preserves external storage configurations. Provider and deployed-behavior checks still determine readiness.

This is a separate lightweight package, not a release of the earlier experimental `azure-to-aws-migration` runtime. No runtime signing or deployment-verification claims carry over from that project.

Optional Bedrock JSON-agent source supports explicit `bedrock-runtime` or `bedrock-mantle` routes, local conversation history, schema validation and bounded repair for no-tool analysis tasks. It does not replace Foundry-hosted tools or create a distributed state service. The example Customer Assist port uses it for sentiment and post-call analysis; full application migration remains separate work.
