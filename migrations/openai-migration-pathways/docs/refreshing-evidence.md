# Refreshing the plugin evidence

The live registry is a reviewed release, not a web cache. Preserve the previous release and assessments before updating. Source manifests may include wider provider catalogs; only the nine approved targets are promoted. A user-directed scope change is needed to add another target family.

1. Run `python3 scripts/refresh_evidence.py data/source-manifest.json NEW_CANDIDATE_DIRECTORY`. This only fetches official public documentation. Failed, redirected and changed pages need review. Preserve Markdown tables and support icons; flattened HTML can lose supported/unsupported distinctions.
2. Compare candidates with the current snapshots. Review exact model IDs, endpoint/API paths, partition, entry and destination Regions, cache modes/limits, schema and streaming combinations, tool restrictions, retention, service tiers and pricing. Update model-specific mappings in scripts/build_registry.py. Do not promote all fields because a page was retrieved.
3. For approved claims, copy reviewed snapshots into data/evidence, update data/sources.json and data/review-lock.json, and set the reviewed date/version in build_registry.py. Keep direct OpenAI evidence scoped separately from Bedrock evidence. Conflicts stay explicit.
4. Run `python3 -B scripts/build_registry.py`, then `python3 -B scripts/export_catalog.py`. The builder rejects snapshots whose hashes differ from the review lock. Rebuild the workbook with `node scripts/build_workbook.mjs` in an authoring environment with @oai/artifact-tool available. This authoring dependency is not needed to install or run the plugin/evaluator.
5. Run `python3 -B -m unittest discover -s scripts -p 'test_*.py'`, export checks and representative examples. Update prose, fixtures, adapter data, schema/gap designs, release notes and documentation together. Preserve the distinction between synthetic tests, helper tests and a real migrated application.
6. Validate the manifest and skill, bump the release version, create checksums and a shareable package, install, then compare installed file hashes with the reviewed release. Preserve rollback files.

Historical assessment replay uses its pinned registry and snapshots. Current checks must separately assess evidence age. New snapshots never rewrite historical reports.

The optional deployment portal currently cannot verify inference-profile or Mantle-only availability using its foundation-model availability call. These routes remain blocked for live deployment until a scoped account-specific verifier is supplied; catalog support is not deployment readiness.
