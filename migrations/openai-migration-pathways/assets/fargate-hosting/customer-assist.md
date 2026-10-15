# Customer Assist deployment wiring

`customer-assist.tfvars.json.example` connects the three services in the current example port of `Azure-Samples/openai`: frontend, session manager and worker. Use it only with the corresponding application patch, not with the original Azure application. It is a reference configuration, not a completed deployment or an automatic port of another repository.

The example is intentionally not auto-loaded. Replace every `REQUIRED_` value, the example hostname/client CIDR, and the reviewed network/size choices before using it. Choose the CPU architecture from actual image-build evidence. Keep the selected Region consistent with the application agent configuration, Knowledge Base, policies, images, secrets, certificate and Cognito pool. `us-east-1`, two AZs and the node sizes are design assumptions, not discovered customer values.

## Service connections

The frontend and API use one hostname and Cognito session. API paths have priority 100 and reject unauthenticated requests; the wildcard page route at priority 200 initiates sign-in. Both services implement HTTPS. The worker has no hostname or inbound caller rule: requests and replies use Redis, not a direct frontend-to-worker connection. The legacy worker URI setting is supplied for configuration compatibility, not an additional network grant.

Queue names, reply channel base and document-registry namespace match across session and worker. Queue and registry clients use separate credentials; the worker's registry identity is read-only. Provision the actual ACL user group according to [registry permissions](../python-redis/authorization-registry.md), including the queue/config keys and response channels the application uses. The example does not create Redis users or their passwords.

The frontend has no Redis, storage or model credentials. The session publishes versioned images; the worker inherits the session's storage prefix with read permissions. The module generates S3/KMS, AWS account/Region, Redis endpoint/TLS and authenticated ALB identity settings. Do not manually duplicate those reserved values.

Session and worker start with one task each and scaling disabled because their conversation state is process-local. This is not a high-availability solution. The stateless frontend has two tasks. Do not increase worker/session replicas until state coordination, queue loss/replay, rollout overlap and reconnection are tested; even rolling replacement can overlap old and new tasks.

## Credentials and service permissions

All secret entries are references to existing whole Secrets Manager secrets, never values. Add `secrets_kms_key_arns` if those secrets use customer-managed KMS keys. Backend TLS certificates need a `localhost` SAN for the verified local health probes; add a `TLS_HEALTH_CA_PEM` secret reference if the certificate is signed by a separate CA. Register the Cognito callback and app-client settings described in [authentication](authentication.md).

The session policy allows only image moderation. The worker policy allows retrieval from the named Knowledge Base and the two document-analysis operations used by the port. Those synchronous Textract operations do not provide resource-level ARN scoping; their statements use `Resource: "*"` with a Region condition. S3/KMS permissions are generated separately and remain prefix/key scoped. The byte-based Rekognition request does not use a custom model. See the AWS authorization references for [Textract](https://docs.aws.amazon.com/service-authorization/latest/reference/list_textract.html), [Rekognition](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rekognition.html), and [Bedrock](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock.html).

The Bedrock API key's identity must separately permit the selected Responses inference route. A task policy for Knowledge Base retrieval does not grant bearer-key permissions. This example neither creates that key nor broadens its model access. Preserve the approved OpenAI model policy and exact `bedrock-runtime` or `bedrock-mantle` route.

## What the checks establish

Tests resolve the example through the module's real input validation and local expressions using synthetic account/resource identifiers. They check route precedence, shared storage, credential separation, settings, health commands and service-specific permissions. No provider, image build, Cognito login or AWS service request is executed by these tests. Application feature gaps remain in the assessment ledger.
