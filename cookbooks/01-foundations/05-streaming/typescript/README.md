# TypeScript — not implemented yet

This directory is a placeholder. The recipe's narrative, prerequisites and
explanation live one level up in [`cookbooks/01-foundations/05-streaming/README.md`](../README.md); only the
implementation is per language.

When it lands, it will hold the port plus the files a TypeScript project needs of
its own:

```
typescript/
├── package.json
├── tsconfig.json
└── streaming.ts
```

**Why the split exists at all:** those sidecar files are the reason. A Python recipe
is a single script, because its dependencies are declared once in
[`cookbooks/pyproject.toml`](../../../pyproject.toml). A TypeScript recipe carries its
own manifest and compiler config, and putting them at the recipe root would leave it
ambiguous whether they govern the recipe or only the TypeScript. Giving each language
a directory keeps that unambiguous — and means the Python paths never move when
TypeScript arrives.

Python is the reference implementation. A TypeScript port should produce the same
output and teach the same thing, not re-explain it.
