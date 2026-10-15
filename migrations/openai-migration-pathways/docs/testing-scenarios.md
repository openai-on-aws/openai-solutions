# Release 0.4.1 acceptance scenarios

Run `python3 -B -m unittest discover -s scripts -p 'test_*.py'` from the plugin root. Tests separate synthetic engine rules from assertions about the reviewed catalog. They perform no cloud/model calls.

## Discovery

- Request US processing, explicit prompt caching and streaming. Compare the nine approved targets without forcing one API. Ask about single-Region versus geographic processing and data boundaries.
- Add inline Guardrails. Evaluate model-specific combinations; do not carry forward the old universal cache/inline conflict.
- Require streaming structured outputs. Distinguish the exact GPT-6.1 Sol contract from cards documenting only non-streaming output.
- Request GPT-5.5 with explicit caching. Preserve the rejected requirement; implicit caching is a different alternative requiring acceptance.
- Require ZDR, stored continuation and background execution. Identify independent conflicts and account checks; store=false is not full ZDR.
- Request an excluded target. Explain the nine-model policy without substituting GPT-OSS or Daybreak.
- Change to EU-only or Ohio-only processing. Reevaluate the existing ledger. A European entry endpoint or a US profile label does not establish the requested data boundary.

## Repository assessment

Trace an HTTP trigger through a shared wrapper to model calls, including optional workers/tools. Map all twelve source-contract categories. For every gap, record affected code, evidence, control flow, state, failures, semantic differences and acceptance tests. Assessment work remains design_only unless actual implementation is supplied.

Save a pinned registry/evidence copy, requirements and evaluation per role, plus revision-3 route decisions, gap designs and the shared report contract. Verify the main report, assessment JSON and deployment exports agree. Missing gap designs, excluded targets, edited evaluations and unsupported selected candidates must fail validation.

## Shared report checks

Run `python3 -B scripts/verify_report.py examples/discovery-report --historical` to replay the fictional saved example. Both modes must include all nine sections and linked routes, central gaps, orchestration designs and service mappings. Discovery must reject invented repository commits. Code reports must cover all source routes and feature gaps; deployment mappings must agree with their canonical matrix. A proposed workaround must leave native incompatibility visible. Resolved gaps and implemented/verified designs require corresponding evidence. Changed tables and edited evaluations must fail.

## Generated artifacts and release

Run `python3 -B scripts/export_catalog.py --check`. Verify the workbook's route/capability/pricing/evidence rows against the registry, including late rows and all nine models. Rebuild it after changing any registry content. Inspect model-specific cache read/write prices and preserve unavailable rates as unknown.

A passing suite proves the tested rules and artifact consistency. Account quotas, IAM, request behavior, quality, production safety and customer application builds remain separate validation work.
