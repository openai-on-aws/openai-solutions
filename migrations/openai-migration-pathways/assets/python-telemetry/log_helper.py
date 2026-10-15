"""Legacy logger adapter without Azure credentials or exporters."""
import logging
from common.telemetry.app_logger import get_application_logger, _properties


class CustomLogger(logging.LoggerAdapter):
    def __init__(self, app_insights_cnx_str=None):
        super().__init__(get_application_logger(), {})

    def process(self, msg, kwargs):
        extra = kwargs.get("extra") or {}
        properties = _properties(extra.get("custom_dimensions"))
        properties.update(_properties(extra.get("migration_properties")))
        kwargs["extra"] = {"migration_properties": properties,
                           "migration_event": extra.get("migration_event")}
        return msg, kwargs
