"""Load an injected TLS key pair without retaining private-key files."""
import os
from pathlib import Path
import ssl
import tempfile


def server_tls_context(host, environment=None):
    values = dict(os.environ if environment is None else environment)
    mode = values.get("SERVICE_TLS", "required")
    if mode == "disabled" and host in {"localhost", "127.0.0.1", "::1"}:
        return None
    if mode != "required":
        raise ValueError("Plain HTTP is allowed only on explicit loopback development listeners")
    cert, key = values.get("TLS_CERTIFICATE_PEM"), values.get("TLS_PRIVATE_KEY_PEM")
    if any(not isinstance(value, str) or not value or len(value) > 131072 for value in (cert, key)):
        raise ValueError("Provide the injected backend TLS certificate and key")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        # SSLContext loads both into memory. The private directory and its files
        # disappear before the listener starts, including on load failure.
        with tempfile.TemporaryDirectory(prefix="migration-tls-") as temporary:
            certificate, private_key = Path(temporary) / "certificate.pem", Path(temporary) / "private-key.pem"
            for path, value in ((certificate, cert), (private_key, key)):
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="ascii") as output:
                    output.write(value)
            context.load_cert_chain(certificate, private_key)
    except Exception:
        raise ValueError("Backend TLS certificate/key could not be loaded") from None
    return context
