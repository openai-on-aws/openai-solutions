# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `piiMasking.ts` with its own `package.json` and
`tsconfig.json`. It needs two SDKs, as the Python version needs `openai` plus `boto3`: the
OpenAI Node SDK for the summary, and `@aws-sdk/client-bedrock-runtime` for `ApplyGuardrail`
plus `@aws-sdk/client-bedrock` to create and delete the guardrail.

The recipe's narrative — the per-direction configuration, the missing date entity type, the
verification step — lives once in [`cookbooks/05-production/02-pii-masking/README.md`](../README.md) and applies to both
languages.
