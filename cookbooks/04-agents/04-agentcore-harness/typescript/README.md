# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `agentcoreHarness.ts` with its own `package.json` and
`tsconfig.json`. It needs the AWS SDK v3 rather than the OpenAI SDK — the harness is
declared and invoked through `@aws-sdk/client-bedrock-agentcore-control` and
`@aws-sdk/client-bedrock-agentcore`, and the model is named in the declaration rather than
called directly. That is the point of the recipe: the OpenAI-compatible call happens inside
the harness.

The recipe's narrative lives once in [`cookbooks/04-agents/04-agentcore-harness/README.md`](../README.md) and applies to both
languages.
