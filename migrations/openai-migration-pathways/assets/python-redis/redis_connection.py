"""TLS/password-ACL connection options shared by sync and async redis-py clients.

No network calls. This variant uses a named Redis user and a password injected
by the deployment platform; it is not an ElastiCache IAM-token provider.
"""
import os


def redis_connection_options(host, port, password, ssl=True, *, username=None, ca_file=None):
    if ssl is not True:
        raise ValueError("The target Redis connection requires TLS")
    if not isinstance(host, str) or not host or any(c.isspace() for c in host) or "/" in host:
        raise ValueError("REDIS_HOST must be a hostname or IP address")
    if isinstance(port, bool) or not isinstance(port, (str, int)):
        raise ValueError("REDIS_PORT must be an integer from 1 to 65535")
    try:
        port = int(port)
    except ValueError:
        raise ValueError("REDIS_PORT must be an integer from 1 to 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("REDIS_PORT must be an integer from 1 to 65535")
    if username is None:
        username = os.environ.get("REDIS_USERNAME")
    if not isinstance(username, str) or not username.strip():
        raise ValueError("REDIS_USERNAME must identify the configured ACL user")
    if not isinstance(password, str) or not password:
        raise ValueError("REDIS_PASSWORD must be injected by the deployment platform")
    options = {
        "host": host, "port": port, "username": username, "password": password,
        "ssl": True, "ssl_cert_reqs": "required", "ssl_check_hostname": True,
        "socket_connect_timeout": 5, "socket_timeout": 10, "health_check_interval": 30,
    }
    if ca_file is not None:
        options["ssl_ca_certs"] = os.fspath(ca_file)
    return options


def read_environment_setting(name):
    """Read an injected setting, accepting legacy hyphenated aliases without cloud fallback."""
    canonical = name.replace("-", "_")
    legacy = os.environ.get(name)
    value = os.environ.get(canonical)
    if legacy and value and legacy != value:
        raise ValueError(f"Conflicting environment aliases for {canonical}")
    value = value or legacy
    if value is None or value == "":
        raise ValueError(f"Missing injected configuration: {canonical}")
    return value


def authorization_registry_options(host, port, *, environment=None, ca_file=None):
    """Use a separate ACL identity for grants/documents, never queue credentials."""
    values = dict(os.environ if environment is None else environment)
    username = values.get("AUTHORIZATION_REDIS_USERNAME")
    password = values.get("AUTHORIZATION_REDIS_PASSWORD")
    queue_username = values.get("REDIS_USERNAME")
    if (not isinstance(username, str) or not 1 <= len(username) <= 64
            or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in username)
            or username == "default" or not queue_username or username == queue_username):
        raise ValueError("AUTHORIZATION_REDIS_USERNAME must be a distinct named ACL identity, not the queue or default user")
    if not isinstance(password, str) or not password:
        raise ValueError("AUTHORIZATION_REDIS_PASSWORD must be injected separately")
    return redis_connection_options(host, port, password, username=username, ca_file=ca_file)
