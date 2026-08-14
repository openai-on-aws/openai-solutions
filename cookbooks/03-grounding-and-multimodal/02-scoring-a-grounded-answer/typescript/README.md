# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `scoringAGroundedAnswer.ts` with its own `package.json`
and `tsconfig.json`. Note that it needs two SDKs: the OpenAI Node SDK for the answer, and
`@aws-sdk/client-bedrock-runtime` for `ApplyGuardrail` — guardrails are an AWS API rather
than part of the OpenAI-compatible surface, which is the same split the Python version has
between `openai` and `boto3`.

The recipe's narrative — the two filters, the measured scores, the refusal blind spot —
lives once in [`cookbooks/03-grounding-and-multimodal/02-scoring-a-grounded-answer/README.md`](../README.md) and applies to both languages.
