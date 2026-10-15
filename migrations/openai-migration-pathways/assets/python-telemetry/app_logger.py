"""Application logging to stderr; compatible with the agent sample interfaces.

Messages remain caller-controlled. The metadata allowlist is not a sanitizer for
secrets or personal data interpolated into messages by application code.
"""
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import math
import os
import sys
from threading import RLock


class LogEvent(Enum):
    REQUEST_RECEIVED = "Request.Received"
    REQUEST_SUCCESS = "Request.Success"
    REQUEST_FAILED = "Request.Failed"


_FIELDS = frozenset({"ApplicationName", "application_name", "duration_ms", "status_code", "method"})
_LOCK = RLock()


def _properties(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        value = value.model_dump()
    return {key: item for key, item in value.items()
            if key in _FIELDS and isinstance(item, (str, int, float, bool))
            and not (isinstance(item, float) and not math.isfinite(item))}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": os.getenv("OTEL_SERVICE_NAME", "migration-application"),
            "message": record.getMessage(),
            "properties": _properties(getattr(record, "migration_properties", None)),
        }
        event = getattr(record, "migration_event", None)
        if event:
            result["event"] = event.value if isinstance(event, LogEvent) else str(event)
        if record.exc_info and record.exc_info[0]:
            result["exception_type"] = record.exc_info[0].__name__
        try:
            from opentelemetry.trace import get_current_span
        except ImportError:
            pass
        else:
            context = get_current_span().get_span_context()
            if context.is_valid:
                result["trace_id"] = format(context.trace_id, "032x")
                result["span_id"] = format(context.span_id, "016x")
        return json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def get_application_logger():
    with _LOCK:
        logger = logging.getLogger("migration.application")
        logger.propagate = False
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        logger.setLevel(level)
        if not any(getattr(handler, "_migration_handler", False) for handler in logger.handlers):
            handler = logging.StreamHandler(sys.stderr)
            handler._migration_handler = True
            handler.setFormatter(JsonFormatter())
            logger.addHandler(handler)
        return logger


class AppLogger:
    def __init__(self, connection_string=None, *, custom_logger=None):
        # Legacy arguments accepted, but never configure an Azure exporter.
        if custom_logger is not None and not isinstance(custom_logger, logging.LoggerAdapter):
            raise TypeError("custom_logger must be a logging.LoggerAdapter")
        self.logger = custom_logger if custom_logger is not None else get_application_logger()
        self._base = ContextVar("migration_log_properties", default=None)

    def set_base_properties(self, base_properties):
        self._base.set(_properties(base_properties))

    def _log(self, level, message, properties=None, event=None, exc_info=False):
        merged = {**(self._base.get() or {}), **_properties(properties)}
        self.logger.log(level, message, extra={"migration_properties": merged, "migration_event": event}, exc_info=exc_info)

    def info(self, message, properties=None):
        self._log(logging.INFO, message, properties)

    def debug(self, msg, properties=None):
        self._log(logging.DEBUG, msg, properties)

    def warning(self, msg, properties=None):
        self._log(logging.WARNING, msg, properties)

    def error(self, msg, event=None, properties=None):
        self._log(logging.ERROR, msg, properties, event)

    def exception(self, msg, properties=None, event=None):
        self._log(logging.ERROR, msg, properties, event, exc_info=True)

    def critical(self, msg, properties=None):
        self._log(logging.CRITICAL, msg, properties)

    def log_request_received(self, msg, properties=None):
        self._log(logging.INFO, msg, properties, LogEvent.REQUEST_RECEIVED)

    def log_request_success(self, msg, properties=None):
        self._log(logging.INFO, msg, properties, LogEvent.REQUEST_SUCCESS)

    def log_request_failed(self, msg, properties=None):
        self._log(logging.ERROR, msg, properties, LogEvent.REQUEST_FAILED)
