# Backend HTTPS startup

`server_tls_context(host)` loads `TLS_CERTIFICATE_PEM` and `TLS_PRIVATE_KEY_PEM` from injected application settings. TLS is required by default, with a minimum of TLS 1.2. `SERVICE_TLS=disabled` is accepted only for an explicit loopback listener. This helper requires no third-party Python package.

The certificate and key are briefly written as mode-0600 files inside a private temporary directory so Python's SSL context can load them. The directory is removed on success or failure before the listener starts. Private key contents are not included in reported errors. See the [Python SSL API](https://docs.python.org/3/library/ssl.html).

Customer Assist's session startup passes this context to aiohttp, and its image sets `SERVICE_TLS=required`. Inject each PEM through a whole-secret Secrets Manager reference in the task definition, not an image layer or build argument. Keep the scratch volume available for startup. Replacing injected certificates requires a task restart.

The local HTTPS health probe validates the certificate and hostname `localhost`; include that DNS name in the backend certificate's SAN. For a CA-issued certificate, inject the trusted root chain as `TLS_HEALTH_CA_PEM`; otherwise the probe uses `TLS_CERTIFICATE_PEM` as its trust material. It does not follow redirects or use HTTP proxy settings. The frontend's Node health probe uses the same names and verification policy.

The load balancer uses the task port with `backend_protocol = "HTTPS"`. Backend TLS encrypts the hop; the application still verifies the ALB's signed identity. ALB does not validate the backend certificate, so task ingress must remain restricted to the load balancer.

These are customer application HTTPS settings—not plugin installation requirements or the old signed-runtime trust-key mechanism. Tests verify a real local TLS handshake, rejected plaintext/public fallback, and temporary-key cleanup; they do not certify the deployed load-balancer path.
