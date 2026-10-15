"""OpenTelemetry tracing: stderr summaries by default, explicit OTLP opt-in."""
import json
import os
import sys
from threading import RLock
from urllib.parse import urlsplit

_LOCK = RLock()
_PROVIDER = None
_CONFIG = None
_STOPPED = False


def _configuration():
    mode = os.getenv("OTEL_TRACES_EXPORTER", "console").strip().lower()
    if mode not in {"console", "otlp", "none"}:
        raise ValueError("OTEL_TRACES_EXPORTER must be console, otlp or none")
    service = os.getenv("OTEL_SERVICE_NAME", "migration-application").strip()
    if not service:
        raise ValueError("OTEL_SERVICE_NAME must not be empty")
    endpoint = ""
    if mode == "otlp":
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
        parsed = urlsplit(endpoint)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path != "/v1/traces"
                or not (parsed.scheme == "https" or
                        (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}))):
            raise ValueError("Set an HTTPS OTLP trace endpoint ending /v1/traces; HTTP is permitted only on loopback")
        # Validate malformed/out-of-range ports before creating a provider.
        parsed.port
        if os.getenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")) != "http/protobuf":
            raise ValueError("This adapter supports OTLP http/protobuf only")
    return mode, service, endpoint


class AppTracerProvider:
    def __init__(self, connection_string=None):
        # Legacy connection strings are intentionally neither stored nor used.
        self.provider = None

    def set_up(self):
        global _PROVIDER, _CONFIG
        configuration = _configuration()
        with _LOCK:
            if _STOPPED:
                raise RuntimeError("Tracing has shut down; start a new process to reinitialize it")
            if _PROVIDER is not None:
                if configuration != _CONFIG:
                    raise RuntimeError("Tracing is already configured differently in this process")
                self.provider = _PROVIDER
                return self.provider
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult,
            )
            if not isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
                raise RuntimeError("A tracing provider is already installed; integrate with its owner")
            mode, service, endpoint = configuration
            exporter = None
            if mode == "otlp":
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=endpoint, timeout=5)
            elif mode == "console":
                class SummaryExporter(SpanExporter):
                    def export(self, spans):
                        for span in spans:
                            row = {"type": "span", "service": service, "name": span.name,
                                   "trace_id": format(span.context.trace_id, "032x"),
                                   "span_id": format(span.context.span_id, "016x"),
                                   "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                                   "start_time_unix_nano": span.start_time,
                                   "end_time_unix_nano": span.end_time,
                                   "status": span.status.status_code.name}
                            sys.stderr.write(json.dumps(row, ensure_ascii=True) + "\n")
                        return SpanExportResult.SUCCESS
                exporter = SummaryExporter()
            provider = TracerProvider(resource=Resource({"service.name": service}))
            try:
                if exporter is not None:
                    processor = BatchSpanProcessor(exporter) if mode == "otlp" else SimpleSpanProcessor(exporter)
                    provider.add_span_processor(processor)
                trace.set_tracer_provider(provider)
                if trace.get_tracer_provider() is not provider:
                    raise RuntimeError("Another component installed tracing concurrently")
            except BaseException:
                provider.shutdown()
                raise
            _PROVIDER, _CONFIG = provider, configuration
            self.provider = provider
            return provider

    def force_flush(self, timeout_millis=5000):
        with _LOCK:
            if _STOPPED:
                return False
            return self.provider.force_flush(timeout_millis) if self.provider else True

    def shutdown(self):
        global _STOPPED
        with _LOCK:
            if self.provider is not None and not _STOPPED:
                _STOPPED = True
                self.provider.shutdown()
