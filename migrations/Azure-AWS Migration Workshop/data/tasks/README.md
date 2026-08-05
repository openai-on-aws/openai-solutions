# Task Content

Task cards live under `data/tasks/en/*.md`.

Each task file must:

- Use YAML frontmatter with `id`, `title`, `summary`, and `phase`.
- Use a filename that exactly matches the `id`.
- Open with a short paragraph that explains why the step matters.
- Include three to five participant-facing actions or observations.
- Include exactly one fenced `text` prompt rendered as **Copy To Codex**.
- End with a short statement describing what must be true before continuing.
- State the participant's desired outcome and the result the participant should review. Explain specialist ownership in the card prose, not as a command the participant must issue.
- Keep artifact inventories, schema wiring, sequencing, and agent handoffs in the starter's orchestration rules rather than the participant prompt.
- Keep credentials terminal-only and stop with a factual blocker when required evidence is missing.

Prompts must be concise, outcome-focused requests a participant can understand without knowing the internal artifact graph or selecting an agent. They should normally identify the action, important review concerns, and the human-readable result. The lead Codex session selects the specialist from the starter's orchestration contract and announces that delegation. Preserve safety, credential, and approval boundaries in repository rules; expose them in a task prompt only when the participant must take an action.

Do not add separate shell fences or repeat worksheet headings such as `Goal`, `Intent`, `Evidence`, or `Completion Criteria`. Use readable paragraphs and short lists rather than dense runbook prose.

Tasks render only when their IDs are listed in `src/app/lib/taskOrder.ts`. Files that are not listed there are ignored by the hub.

Two cards intentionally have no fenced prompt or **Copy To Codex** button:

- `understand-migration-journey.md` is the uncounted introduction and has no checkbox.
- `download-starter-workspace.md` is a counted manual setup task completed by opening the extracted starter folder in Codex Desktop.
