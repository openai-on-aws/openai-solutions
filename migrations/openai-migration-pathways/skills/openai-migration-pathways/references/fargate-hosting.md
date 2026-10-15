# Fargate hosting source

Use `../../../assets/fargate-hosting/` relative to this reference for a target that actually calls for Linux Fargate services with at least one HTTP service, a shared ALB, two AZs, private task subnets, and optional Redis. Copy and adapt it into the output package; do not edit the installed asset. This is one hosting pattern, not a mandatory architecture for every repository. Local stdio tools, notebooks, static sites, and non-container workloads need their own deployment contracts.

## Inputs and application mapping

`variables.tf` declares inputs. `workloads` has one entry per independently deployed service. Populate it from actual entrypoints, CPU support, exposed ports, health checks, dependencies, and built image digests. Use an existing ACM certificate and Route53 zone that cover the service names. The account guard and image checks currently support the standard AWS partition, not GovCloud/China. Supply two existing standard AZ names in the selected Region. The template creates a new VPC; adapting an existing VPC requires different network resources.

Use `hostname` plus a stable `listener_priority` for HTTP services; omit both for private workers. All required services still need a working in-container health command. Set `allowed_callers` on the destination service to admit named peer services on its declared port. The application must use the Cloud Map DNS name and port in its actual dependency configuration; infrastructure does not rewrite client URLs.

Images must be same-account/Region ECR references with actual SHA-256 digests. Never fabricate digests to pass validation. Secret values are not inputs: `secrets` maps environment names to existing whole-secret Secrets Manager ARNs. Supply KMS key ARNs only for keys those secrets use. `task_policy_json` is the workload's reviewed runtime policy, distinct from the execution role used to pull its image and inject secrets. Application and secret environment names must not overlap.

Map each output resource to the architecture and implementation ledger, including Cloud Map and the S3 gateway endpoint. This source does not provide application ports, model access, end-user authentication, database migration, or verified production operations by itself.

For a confirmed session-image upload path, read `../../../assets/python-s3/README.md` before adapting its image store. If the accepted deployment calls for a new managed image bucket, read `../../../assets/fargate-hosting/image-storage.md`: `image_storage` plus per-workload `uses_image_storage` generates private storage, task-role grants and adapter environment together. External storage remains supported without this option. Neither route completes other Blob paths, model migration, URL refresh or end-user authorization.

## Writable filesystem contract

The task runs with a numeric non-root UID and a read-only root filesystem. Its ephemeral scratch volume is mounted at `/tmp`. Merge `Dockerfile.scratch.fragment` into the final image stage, retaining the application's real startup command and matching its UID. The matching image `VOLUME` directive and directory permissions matter: an empty ECS bind volume otherwise defaults to root ownership with mode 0755. See [AWS bind-mount documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/bind-mounts.html).

Image acceptance must exercise creation/read/removal of a temporary file as the configured UID with read-only root and the scratch volume mounted, then run real startup and health checks. Merely inspecting the Dockerfile does not verify the mounted permissions. Adapt caches and upload paths to `/tmp` or explicitly designed persistent stores; scratch disappears when the task stops. Do not solve a write failure by making the application root or disabling read-only root globally. The fragment does not remove interactive Azure login or port Azure SDK calls; those require actual application changes.

## Connections and request lifetimes

Outbound TCP443 supports API/image/secret access through a per-AZ NAT gateway; it is not hostname-filtered. Other TCP dependencies use per-workload `egress` entries with a port, purpose, and exactly one destination CIDR or security-group ID. Destination groups must be referenceable from this VPC, with matching destination ingress. A CIDR rule alone does not create routing. Private Azure connectivity, peering, transit gateways, destination firewalls, DNS forwarding, and return routes must be designed and added separately when needed. Never represent the NAT gateway as private cross-cloud connectivity.

For optional Redis, supply an existing ACL user group and compatible engine/node versions. Port every relevant client for TLS, certificate verification, named-user authentication and appropriate credential refresh. Use distinct key/channel permissions and protect or disable the default user. Attaching an arbitrary ACL group is not proof of authenticated isolation. Redis lists/pubsub do not become acknowledged durable queues automatically.

For Python redis-py password-ACL clients, `../../../assets/python-redis/redis_connection.py` supplies shared sync/async connection options with certificate and hostname verification, named-user credentials and bounded socket waits. Copy it into the application and wire every actual constructor; adding the file alone changes nothing. Supply `REDIS_USERNAME` and an injected password. Its environment reader accepts underscore/hyphen aliases and never falls back to Azure Key Vault. That environment-only behavior is an explicit target-port choice, not a change to silently apply to an application retaining Key Vault. Static secret injection requires task replacement after rotation; this helper is not an IAM-token provider or automatic secret refresh mechanism. Preserve queue/pubsub semantics and test failure recovery separately.

The plugin's opt-in Redis tests use a temporary loopback-only Redis server, test-generated certificates and a restricted test user. They verify sync/async queues, pubsub, bad-password rejection, certificate/hostname verification and key/channel ACL rejection. Enable them only for development verification with `MIGRATION_RUN_LOCAL_REDIS_TESTS=1`; they need redis-py, redis-server and OpenSSL, not cloud credentials. They do not verify ElastiCache failover or a full application port.

`idle_timeout_seconds` defaults to 600 and is configurable; align it with response timing and WebSocket heartbeats. Per-service `deregistration_delay` controls ALB draining, but Fargate shutdown is still limited to 120 seconds here. Use durable/checkpointed jobs, reconnect handling and cancellation for work that can outlive termination. A longer ALB timeout does not preserve in-memory session state.

Autoscaling, scale-in and AZ rebalancing are individually opt-in. Enable them after the workload supports restarts, drain, reconnect and replay. The default fixed task count is not a durability guarantee: failures and deployments still restart tasks. Sticky sessions only affect routing, not state recovery.

The capacity target is registered for every service, but without autoscaling its minimum and maximum both equal `min_tasks` and no scaling policy exists. This keeps later fixed-count changes effective while Terraform leaves the service's live desired count to the capacity controller. Changing capacity bounds is an explicit deployment change and can stop tasks.

## Validation and operation

The source has offline Terraform-core tests for input validation and resolved defaults, plus parsed-resource checks. These do not load the AWS provider. Provider schema validation, image acceptance and live smoke tests must retain their actual status in the package; do not promote them based on these tests.

For a completed customer configuration, provide commands for `terraform fmt -check`, approved dependency initialization, `terraform validate`, reviewed planning, and separately authorized application. Keep backend/state credentials outside the package. Retain the generated provider lockfile after successful approved initialization. Do not bypass a configured provider mirror when it fails.

The template's alarms cover unhealthy ALB targets only. Add workload-specific signals for missing capacity, private workers, queue age/backlog, job loss, Redis, model errors and credential expiry. Choose notification destinations explicitly. HTTPS and network filtering are not end-user authentication; implement the accepted application/OIDC design before exposure. NAT, ALB, ECS, Redis and logs incur costs. Document cutover/rollback and data retention; deletion protection defaults on.
