# Publishing and maintaining this plugin

The canonical source is `migrations/openai-migration-pathways/` in `openai-on-aws/openai-solutions`. The repository-level `.agents/plugins/marketplace.json` exposes it as `openai-migration-pathways@openai-solutions`. The standalone ZIP uses the same marketplace identity and a self-contained `plugins/` layout.

## Contribution checks

Discuss significant additions in an issue and submit a focused pull request against `main`. Preserve author credits, evidence dates, third-party notices and the distinction between offline checks and live verification. Review the [license inventory](../LICENSING.md), including redistribution of captured provider documentation.

The scoped `migration-plugin.yml` workflow runs on plugin/catalog/workflow changes. It checks Python 3.10 and 3.13, runs the offline regression suite, verifies generated exports and the pinned sample, validates manifest/catalog paths and local documentation links, and creates a shareable archive. It needs no cloud/model credentials. A fork pull request may need maintainer approval before GitHub runs its checks.

Local commands, from the plugin directory:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/export_catalog.py --check
python3 -B scripts/verify_plugin.py --repository-root ../..
python3 -B scripts/package_plugin.py /path/to/new-release-directory --marketplace-name openai-solutions
```

Install the local repository using the instructions in [INSTALL.md](../INSTALL.md). Check the installed manifest and file hashes. Use a requirements-only scenario and a synthetic repository assessment to verify both report flows. These checks do not invoke a model or prove the quality of a generated customer assessment.

## Release after review

1. Bump both plugin manifests and update release notes, installation examples and recorded validation. A catalog update also requires the evidence review/regeneration procedure.
2. Merge the reviewed pull request after the required checks and licensing review.
3. Create a tag named `openai-migration-pathways-v<VERSION>` on the reviewed commit in the canonical repository. For this candidate, the tag is `openai-migration-pathways-v0.4.2`.
4. The workflow verifies that the tag matches the manifest version and its commit belongs to `main`, reruns checks, and creates the GitHub Release with the ZIP and `.zip.sha256`. Only the release job has repository write permission; fork runs never publish a canonical release.
5. Test a fresh installation using the published tag and the bundled example. Record the installed version and compare its files with the release archive.

The archive's `CHECKSUMS.sha256` covers all other extracted files. Its external `.zip.sha256` identifies the complete archive. ZIPs are generated release artifacts and are not committed to the source tree. CI artifacts from a pull request are test packages, not approved releases.

## Refresh and rollback

Follow [refreshing-evidence.md](refreshing-evidence.md) when changing provider claims. Automated fetching never promotes a new capability claim by itself. Historical reports retain their pinned evidence. For rollback, repoint the marketplace at the previous reviewed tag, reinstall, verify the loaded version, and start a new chat. Do not rewrite existing release tags or archives.
