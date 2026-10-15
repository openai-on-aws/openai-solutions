# Separate conversation-registry credentials

Customer Assist uses three permission roles on its TLS Redis service: queue access, ingress grant/document publication, and worker grant/document reads. The session and worker each own a registry client distinct from their queue clients. Closing a worker waits for active processing before closing either client.

`authorization_registry_options` uses the deployment's Redis host/port but requires `AUTHORIZATION_REDIS_USERNAME` and `AUTHORIZATION_REDIS_PASSWORD`. There is no fallback to `REDIS_PASSWORD`; the registry username must differ from `REDIS_USERNAME` and cannot be `default`. TLS certificate and hostname verification remain enabled. These checks prevent accidental credential reuse; the deployed Redis ACL determines actual privileges.

For `DOCUMENT_REGISTRY_NAMESPACE = "customer-assist"`, provision these key and command scopes in the deployment's ACL user group:

| Role | Key patterns | Allowed commands |
| --- | --- | --- |
| Ingress registry writer | `customer-assist:conversation:*`, `customer-assist:document:*` | `GET`, `SET`, `DEL`, `PING` |
| Worker registry reader | Same two patterns | `GET`, `PING` |
| Queue client | Only the application's queue/config keys and channels | Only commands needed by that queue/config adapter; no registry access |

Start from no command, key or channel permissions. Do not grant broad command categories, all keys, scripting, ACL administration or general CLIENT commands. Grant writes use `SET NX EX`; this does not need a separate EXPIRE permission. Disable the default user. Namespace must match exactly across both services. Provision separate queue identities per service where their command requirements differ. If a newer Redis client requires connection metadata commands, review the exact subcommands instead of allowing every CLIENT operation. Redis documents command, key and channel restrictions separately in its [ACL reference](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/).

In each workload's hosting configuration, put its registry username in `environment.AUTHORIZATION_REDIS_USERNAME` and its existing whole-secret Secrets Manager ARN in `secrets.AUTHORIZATION_REDIS_PASSWORD`. Use a writer secret only for ingress and a reader secret only for workers. Put queue credentials under their existing `REDIS_USERNAME`/`REDIS_PASSWORD` settings. Secret values do not belong in the package or tfvars. The hosting execution role injects the named secrets; task roles do not need permission to read those values themselves. Password rotation requires task replacement with this static-injection adapter.

The local regression test uses real TLS Redis with a disabled default user. It proves that the writer can issue and revoke a grant, the worker can consume but cannot replace/revoke/issue it, queue credentials cannot read or change document records, and registry credentials cannot access queues, other namespaces or administrative client/ACL listings. It does not create or verify the customer's ElastiCache users/group.
