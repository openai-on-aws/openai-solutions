# Install OpenAI Migration Pathways

Requires a current Codex desktop app or CLI with plugin support. Python 3.10 or later runs the offline report and compatibility helpers. Installation does not require model or cloud credentials.

## Install from GitHub

After this contribution has merged into the repository's main branch:

```bash
codex plugin marketplace add openai-on-aws/openai-solutions
codex plugin add openai-migration-pathways@openai-solutions
```

For a reproducible installation, pin a published release tag:

```bash
codex plugin marketplace add openai-on-aws/openai-solutions --ref openai-migration-pathways-v0.4.2
codex plugin add openai-migration-pathways@openai-solutions
```

The tag must exist before using that command. Start a new chat and invoke `$openai-migration-pathways`. Restart the app if the updated plugin is not visible. The app's Plugins directory can also install from the registered marketplace.

## Test a checkout or install a release ZIP

For a checkout, register the repository root containing `.agents/plugins/marketplace.json`:

```bash
codex plugin marketplace add /absolute/path/to/openai-solutions
codex plugin add openai-migration-pathways@openai-solutions
```

For a published ZIP, extract it and register its extracted top-level folder instead:

```bash
codex plugin marketplace add /absolute/path/to/openai-migration-pathways-0.4.2
codex plugin add openai-migration-pathways@openai-solutions
```

Keep the entire folder, including the hidden `.agents` directory. Its catalog points at `plugins/openai-migration-pathways`; the Git repository catalog points at `migrations/openai-migration-pathways`. Both identify the plugin in the `openai-solutions` marketplace. Custom archives built without `--marketplace-name openai-solutions` use the marketplace name printed in their README.

Use a separate Codex home directory for installation smoke tests so existing sources and settings remain isolated. Local plugins are cached; editing their source alone does not prove the loaded copy changed.

## Verify the contents

The release ZIP has a sibling `.zip.sha256` file. Check that hash before extracting. `CHECKSUMS.sha256` inside the folder covers its other files. From the plugin directory, run:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/export_catalog.py --check
python3 -B scripts/verify_report.py examples/discovery-report --historical
python3 -B scripts/verify_plugin.py
```

Historical replay reproduces the example's saved evidence date. Omit `--historical` when checking a current assessment; changed freshness results require reviewed evidence updates. Passing offline checks does not establish live model access or application behavior.

## Try the plugin

> Use $openai-migration-pathways in discovery mode. Our Azure OpenAI document assistant uses hosted file search and conversation history. We need US processing, citations and structured output. Produce a full report with routes, gaps/blockers, orchestration proposals and Azure-to-AWS service mappings. Do not inspect a repository, access cloud accounts or deploy resources.

For code assessment, supply a repository or authorized local checkout and ask for the full assessment. Explain scope restrictions and whether read-only cloud inventory is permitted. Use synthetic inputs for initial testing.

## Update or remove

Preserve the previous release for rollback. Refresh the marketplace using `codex plugin marketplace upgrade openai-solutions`, install the selected version, and start a new chat. A marketplace pinned to a release tag stays on that tag until its tracked ref is changed. Disable or uninstall the plugin from the app's Plugins directory when no longer needed. Installation creates no AWS resources.

See [official installation guidance](https://developers.openai.com/plugins/build/plugins) and [the publication workflow](docs/publishing.md).
