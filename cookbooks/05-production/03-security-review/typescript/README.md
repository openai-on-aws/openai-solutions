# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `securityReview.ts` with its own `package.json` and
`tsconfig.json`. It needs the AWS SDK v3 clients alongside the OpenAI Node SDK —
`@aws-sdk/client-ec2`, `@aws-sdk/client-cloudwatch` and
`@aws-sdk/client-service-quotas` — mirroring the Python version's use of boto3.

The recipe's narrative lives once in [`cookbooks/05-production/03-security-review/README.md`](../README.md) and applies to both
languages.
