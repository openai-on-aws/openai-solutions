# Python telemetry port

Use `../../../assets/python-telemetry/` from this reference directory for applications matching the `common.telemetry` interfaces. Copy/adapt the four Python files into the generated application's `common/telemetry/` package; retain upstream attribution when replacing source. Reconcile the supplied requirements with the application's dependency set instead of adding a second conflicting SDK version.

Remove Application Insights reads from configuration initializers, and inspect entrypoints for direct `configure_azure_monitor` calls. Remove obsolete exporters from requirements only after checking all consumers. This is a source transformation, not a fallback that runs the Azure application with missing credentials.

## Runtime contract

- Logging uses one structured JSON handler on stderr, not the root logger. This preserves stdout for stdio MCP. Fargate's existing `awslogs` driver can collect stderr; the application does not need CloudWatch credentials merely to write a log.
- Set `OTEL_SERVICE_NAME` per workload and `LOG_LEVEL` as needed (default INFO). Root and third-party loggers are not automatically captured by this adapter.
- The default `OTEL_TRACES_EXPORTER=console` emits span summaries to stderr, without attributes/events/exception descriptions. These are logs, not proof of trace ingestion into X-Ray or another backend. Span names remain application-supplied; do not put user data in them.
- For a separately configured collector, use `OTEL_TRACES_EXPORTER=otlp` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://collector.example/v1/traces`. The adapter uses OTLP HTTP/protobuf. HTTP is accepted only for a loopback collector. A sidecar collector on loopback is possible but is not provisioned by these assets. Configure collector routing, network access, authentication, task roles and shutdown ordering in the deployment package when selected.
- Exporter authentication headers and certificates use the pinned SDK's environment settings; inject sensitive values by secret reference. They must not be committed. SDK request timeout is five seconds; its batch retries can last longer. Account for drain/flush time in application shutdown; graceful delivery on forced termination is not guaranteed.
- `OTEL_TRACES_EXPORTER=none` explicitly disables export. Do not mark distributed tracing verified in that mode. Repeated setup uses the same provider; changed settings or a provider installed by another component raise an error rather than silently replacing it.
- Call `force_flush()` during graceful shutdown before terminating a configured collector, then `shutdown()` at final process teardown. Do not call shutdown after each request or try to restart the singleton provider.
- For queued jobs, `attached_trace_context(carrier)` attaches a context only for that job and restores the prior context on success, failure or cancellation. `application_span(tracer, name)` records error status without exception text/events. Other SDK instrumentation and manually added span attributes remain outside that protection.

## Privacy and compatibility

Legacy connection-string constructor arguments are accepted but not used. The logger supports dict/`LogProperties` inputs, request events, `exception(..., event=...)`, `CustomLogger()` and `AppLogger(custom_logger=...)`. Per-context base properties prevent concurrent request metadata from overwriting each other.

Only application name, duration, status and method properties are serialized. User IDs, conversation IDs, paths, request bodies and response bodies are not included from metadata. Trace/span IDs provide correlation when an OpenTelemetry context exists. Exception logging includes its class, not exception text or stack locals. **Message strings remain caller-controlled**: inspect and replace payload-bearing log call sites. This adapter is not a general secret/PII sanitizer. OTLP export retains normal SDK span data; review attributes, events and instrumentation before enabling an external collector.

Inspect browser console calls and diagnostic `print` statements too. Replace payloads, signed URLs, configuration objects and raw exception text with stable event messages while preserving request/response and UI behavior. Do not route MCP diagnostics to stdout. Standard-library `logging.exception` can expose exception text even when its message is constant; the portable formatter's behavior does not automatically apply to other handlers.

## Verification

`tests/test_telemetry.py` runs the complete modules in isolated processes. Logging-only tests also run without site packages. SDK tests require the application's pinned OpenTelemetry 1.29.0 packages; `MIGRATION_RUN_LOCAL_TELEMETRY_TESTS=1` additionally tests real HTTP/protobuf delivery to a temporary loopback receiver. Use `--telemetry-dir /path/to/application/common/telemetry` to test the delivered copy. This verifies the adapter, not full application startup or AWS ingestion.

The HTTP exporter contract was checked against the [pinned upstream implementation](https://github.com/open-telemetry/opentelemetry-python/blob/v1.29.0/exporter/opentelemetry-exporter-otlp-proto-http/src/opentelemetry/exporter/otlp/proto/http/trace_exporter/__init__.py). Revalidate compatible versions and service configuration for the target application; these dependencies are not required just to install the Codex plugin.
