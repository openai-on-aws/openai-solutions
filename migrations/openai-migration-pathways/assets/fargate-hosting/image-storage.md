# Managed session-image storage

Use this option only for services ported to the S3 image adapter. Set `image_storage.bucket_name` to a new, customer-approved bucket name, and set `uses_image_storage = true` on each uploading workload. For browser JavaScript retrieval, set `image_storage.browser_origins` to the exact HTTPS frontend origins. Origins are not user authentication.

This template creates a shared-namespace general purpose bucket with a non-dotted name. AWS-reserved names are rejected, including the account-regional `-an` suffix; account-regional bucket creation is not implemented here. Name availability is established only when creating the bucket. See [AWS bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html).

The template creates a private, versioned bucket and a rotating customer-managed KMS key. It injects `S3_IMAGE_BUCKET`, `S3_IMAGE_PREFIX` and `S3_IMAGE_KMS_KEY_ID` into enabled tasks; `AWS_REGION` and `AWS_ACCOUNT_ID` are also generated. Each writer prefix is `<deployment-name>/<workload-key>/images`. Do not manually supply these names in an enabled workload's environment or secrets.

A separate task-role policy grants PutObject/GetObject/GetObjectVersion for the writer's prefix and GenerateDataKey/Decrypt for the image key through S3 in the configured account/Region. A worker with `uses_image_storage = true` and `image_storage_owner = "session"` uses the named session service's prefix and gets only GetObject/GetObjectVersion. It cannot create objects through this policy. KMS GenerateDataKey remains available to support checksum-enabled HeadObject alongside Decrypt. S3 Bucket Keys are disabled so the KMS encryption context remains object-scoped. Existing `task_policy_json` is preserved; review it and all other attached policies for broader grants. Adding a narrow policy does not constrain another policy that already grants more access.

The bucket requires TLS, explicit SSE-KMS and this exact key ARN for writes, matching the adapter's generated settings. It has Block Public Access, BucketOwnerEnforced ownership and no public ACLs. ECS service startup depends on these controls and the image task-role policy. The existing S3 gateway endpoint covers the application route tables; signed browser GETs are not restricted to that VPC endpoint.

`image_storage_bindings` exposes each enabled task role and its generated environment. Use it to verify deployed values against the application configuration. Cross-service sharing requires an explicit owner binding; missing owners, self-references and chains of readers are rejected. The document registry namespace must also match across the session service and worker, with distinct Redis permissions; sharing an S3 prefix alone is not conversation authorization.

With `image_storage = null` and `uses_image_storage = false`, no image resources or grants are added. Existing externally managed buckets remain supported through manual environment and task-policy bindings. Do not select the managed option merely because the repository contains an unused storage helper.

No object expiration is enabled automatically. Versioning and `force_destroy = false` help preserve data, but do not replace backup, legal retention or recovery requirements. Review orphan-image cleanup, URL refresh and KMS-key deletion before production use. Changing workload/deployment names changes object prefixes; plan data and authorization transitions rather than assuming old URLs or objects move.

Tests evaluate Terraform inputs, prefix computation and the actual IAM expression with synthetic provider identifiers, and inspect resource structure. They do not establish AWS provider acceptance, IAM/KMS enforcement, CORS behavior or deployed application readiness.

Sources: [SSE-KMS permissions and encryption context](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html), [S3 Bucket Key policy implications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html), [Terraform encryption resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration).
