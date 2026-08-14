# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `projects.ts` with its own `package.json` and
`tsconfig.json`. Note that the Projects API is not part of the OpenAI SDK in any language, so
a port needs an AWS SigV4 signer — `@aws-sdk/signature-v4` with `@aws-crypto/sha256-js` — the
same shape as the Python version's use of botocore. Associating a call with a project is
supported directly: `new OpenAI({ project })` or the `OpenAI-Project` header.

The recipe's narrative lives once in [`../README.md`](../README.md) and applies to both
languages.
