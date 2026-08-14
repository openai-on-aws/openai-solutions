# TypeScript — not yet ported

The TypeScript implementation of this recipe does not exist yet. Python is the reference
implementation; ports land beside it.

When it does, it will live here as `readingAScannedManual.ts` with its own `package.json`
and `tsconfig.json`. It needs only the OpenAI Node SDK: the two documents are read from
`data/` and inlined as base64 data URLs, which is `readFileSync` plus `Buffer.toString`
in Node, so the port carries no extra dependency either.

The recipe's narrative — the nullable field the model must leave empty, what four scanned
pages cost, and which half of a media request can be cached — lives once in
[`cookbooks/03-grounding-and-multimodal/03-reading-a-scanned-manual/README.md`](../README.md)
and applies to both languages.
