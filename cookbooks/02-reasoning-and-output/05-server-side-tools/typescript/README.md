# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `serverSideTools.ts` with its own `package.json` and
`tsconfig.json`. The MCP tool declaration is identical in the Node SDK. The tool server
itself is language-independent — it is a Lambda speaking JSON-RPC, so a TypeScript port of
the recipe could reuse the Python function or ship a Node handler beside it.

The recipe's narrative lives once in [`cookbooks/02-reasoning-and-output/05-server-side-tools/README.md`](../README.md) and applies to both
languages.
