"""Read provisioned runtime configuration using a caller-owned async Redis client.

Keys use the existing orchestrator/<version> namespace. This reader does not
provision configuration, resolve references, authenticate request principals or
refresh an already-cached orchestrator. Give workers GET-only configuration ACLs;
configuration writers need a separate, trusted provisioning identity.
"""
from copy import deepcopy
import json


class RuntimeConfigurationError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeConfigurationError("Duplicate configuration field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise RuntimeConfigurationError("Non-finite configuration value")


async def read_runtime_configuration(default, client, version=None):
    if version is None:
        if not isinstance(default, dict):
            raise RuntimeConfigurationError("Default configuration must be an object")
        return deepcopy(default)
    if not isinstance(version, str) or not version or len(version) > 256 or any(
        character.isspace() or ord(character) < 32 or character in "/\\" for character in version
    ):
        raise RuntimeConfigurationError("Invalid configuration version")
    try:
        raw = await client.get("orchestrator/" + version)
    except Exception:
        raise RuntimeConfigurationError("Configuration read failed") from None
    if raw is None:
        raise RuntimeConfigurationError("Requested configuration version is unavailable")
    if not isinstance(raw, (str, bytes)) or len(raw) > 1024 * 1024:
        raise RuntimeConfigurationError("Invalid configuration document")
    try:
        document = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise RuntimeConfigurationError("Invalid configuration document") from None
    if not isinstance(document, dict):
        raise RuntimeConfigurationError("Configuration document must be an object")
    return document
