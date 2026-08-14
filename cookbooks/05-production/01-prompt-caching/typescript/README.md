# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `promptCaching.ts` with its own `package.json` and
`tsconfig.json`. The mechanics are identical in the Node SDK: `prompt_cache_breakpoint` on a
content part, `prompt_cache_key` at the top level, and `prompt_cache_options` passed through
the request body. The write-then-read behaviour has been observed to reproduce identically
in both languages.

The recipe's narrative — the boundary, the key-as-partition finding, the `instructions`
trap — lives once in [`cookbooks/05-production/01-prompt-caching/README.md`](../README.md) and applies to both languages.
