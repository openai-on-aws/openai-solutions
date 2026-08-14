# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `claimsIntake.ts` with its own `package.json` and
`tsconfig.json` — which is why each language gets a directory rather than sitting beside
the README. Structured output in the Node SDK works the same way: `text.format` with a
`json_schema`, and `client.responses.parse()` with a [Zod](https://zod.dev/) schema in
place of the Pydantic model.

The recipe's narrative — the problem, the schema-design lesson, the production notes —
lives once in [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/README.md`](../README.md) and applies to both languages.
