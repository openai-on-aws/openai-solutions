---
id: start-source-app
title: Start The Source Application
summary: Launch the selected source with repository-supported local commands.
phase: Source Baseline
---

Run the selected application before making migration decisions. A reproducible local baseline gives the agents real startup, API, browser, and persistence behavior to preserve.

- Let Codex discover build and startup commands from the selected source.
- Prefer an existing credential-free profile, mock, or emulator.
- Start every required local component and wait for readiness.
- Record commands, ports, and process identifiers as redacted evidence.

```text
Start the selected source application locally using its repository-supported setup.

Discover and run every required component in Codex Desktop terminals. Prefer the application's existing credential-free local profile, mock, emulator, or local database, and wait until the application is ready.

Show me the running components, local URLs, readiness result, and any limitation that could affect the migration baseline. If the application cannot start reproducibly, explain the blocker instead of inventing a workaround.
```

Continue when the selected source is running and Codex confirms that its startup baseline is reproducible.
