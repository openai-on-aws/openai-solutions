# Versioned runtime configuration

Adapt `runtime_config_store.py` only for applications already storing complete, resolved configuration documents at `orchestrator/<version>` in Redis. It accepts a caller-owned async client and performs a single GET. Reuse the TLS/named-user connection settings; do not create a second unauthenticated connection.

No version means an isolated copy of the supplied default dictionary. An explicit version must exist. Missing, malformed, oversized or duplicate-key documents produce an error rather than a default. The caller must validate the returned dictionary with its application schema and cross-reference checks before constructing an agent. This generic reader does not decide model or endpoint policy.

Provision the resolved JSON through a trusted deployment identity before enabling a version. Give workers GET access to their own configuration namespace; keep SET permission on a separate provisioning identity. Treat published versions as immutable: create a new version when changing a document. This reader does not enforce immutability or authorize which end user may select a version. Namespace and tenant isolation must match the actual deployment.

The sample application patch uses its existing `orchestrator/` namespace and preserves the no-override default path. It no longer invokes the legacy configuration-service cache adapter. That service, older evaluation clients and mutable-version refresh are not covered by this reader.

Run `test_runtime_config_store.py` for parser/default/error tests. Set `MIGRATION_RUN_LOCAL_REDIS_TESTS=1` to include a loopback-only TLS Redis test with separate reader/writer ACLs. These developer tests need Redis tooling; customers do not need it to install the Codex plugin.
