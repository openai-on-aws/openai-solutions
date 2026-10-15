# Authenticated frontend and API routing

For a concrete three-service configuration, see [Customer Assist wiring](customer-assist.md) and `customer-assist.tfvars.json.example`.

This opt-in configuration connects an existing Cognito user pool/app client to the HTTPS load balancer. It does not create users, an identity provider or customer credentials. The app client needs a client secret, authorization-code flow, the `openid` scope and the lowercase callback URL `https://<application-host>/oauth2/idpresponse`. This module passes the pool/client identifiers to ALB without reading the client secret into Terraform.

Set `cognito_auth` with `user_pool_arn`, `user_pool_client_id`, `user_pool_domain` (domain prefix or custom domain, not a URL) and an optional `session_seconds` from 60 to 3600. Pool account and Region must match the deployment. Use one module per independent application identity boundary.

Configure the frontend and session workloads under the same hostname:

| Workload | Path patterns | Priority | Authentication mode |
| --- | --- | --- | --- |
| session | `/api/*`, `/content/*`, `/get-speech-token` | 100 | `deny` |
| frontend | `/*` | 200 | `authenticate` |

These values are workload fields: `path_patterns`, `listener_priority`, `authentication_mode`. More-specific paths must precede wildcard fallbacks. DNS is created once per hostname. The shared session cookie lets the page's sign-in authorize its subsequent identity and WebSocket requests. Unauthenticated API requests are not forwarded to the service. If an expired session redirects a fetch, the browser helper rejects it and requests sign-in; it does not follow the redirect with application data.

Both workloads must implement HTTPS on their declared backend ports (`backend_protocol = "HTTPS"`). Do not set this flag on an HTTP-only image. The load balancer encrypts backend traffic but does not validate target certificates; task ingress is restricted to the load balancer's security group and the application independently verifies the signed ALB claims. The module rejects additional direct callers for authenticated workloads. See [AWS authentication guidance](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-authenticate-users.html).

The generated task environment and `authentication_bindings` output provide `ALB_SIGNER_ARN`, `OIDC_ISSUER`, `OIDC_CLIENT_ID` and `APPLICATION_ORIGINS`. These values cannot be overridden in a workload's environment or secrets. `AWS_ACCOUNT_ID` and `AWS_REGION` are generated for all workloads. Customer Assist can omit `VITE_BACKEND_URI` to use the page's origin; do not bake a publisher's hostname into its frontend image.

The load balancer gets HTTPS egress to identity-provider endpoints. Internal load balancers use private application subnets with NAT routes; public load balancers use public subnets. DNS, certificate coverage, OAuth callback registration and provider connectivity still need deployment verification.

For document processing, give the session workload `uses_image_storage = true`. Give the worker `uses_image_storage = true` and `image_storage_owner` equal to the session workload key. This produces a shared object prefix with version-read permissions for the worker. See [storage bindings](image-storage.md).

Set `DOCUMENT_REGISTRY_NAMESPACE` identically on session and worker. Both now construct a separate registry client using `AUTHORIZATION_REDIS_USERNAME` and `AUTHORIZATION_REDIS_PASSWORD`; missing settings never fall back to queue credentials. The session service uses a grant/document writer identity; the worker uses a read-only identity. See [registry credentials and ACLs](../python-redis/authorization-registry.md) for the tested command/key boundary and secret injection. The worker also needs `LOAN_POLICY_KNOWLEDGE_BASE_ARN`, `LOAN_POLICY_CORPUS`, Bedrock credentials and scoped service permissions. These are application dependencies, not requirements to install the plugin.

Current checks evaluate the exact Terraform input/local expressions and inspect resource definitions without an AWS provider or cloud calls. They do not demonstrate frontend TLS startup, a completed login, deployed IAM enforcement or a working customer deployment.
