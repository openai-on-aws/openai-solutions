"""Scoped W3C trace propagation; always restore the previous task context."""
from contextlib import contextmanager
from opentelemetry import context
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import StatusCode


def inject_trace_context(context_dict):
    inject(context_dict)


@contextmanager
def attached_trace_context(carrier):
    if not isinstance(carrier, dict):
        raise ValueError("Trace carrier must be a dictionary")
    # Start from an empty context, not the previous queue item's context.
    token = context.attach(extract(carrier, context=context.Context()))
    try:
        yield
    finally:
        context.detach(token)


@contextmanager
def application_span(tracer, name):
    """Record operation status without exporting exception text or stack traces."""
    with tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False) as span:
        try:
            yield span
        except BaseException:
            span.set_status(StatusCode.ERROR)
            raise
