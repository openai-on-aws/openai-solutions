# Codex Project Guidance

This repository is the Vercel task-card hub for an Azure OpenAI to AWS migration workshop.

## Scope

- Keep this repo focused on the hub: Next.js pages, task cards, docs, and downloadable starter ZIP.
- Keep the participant starter source-only. The generated Amazon Bedrock OpenAI target app belongs in the participant workspace during the lab, not in this hub repo.
- Do not commit secrets, local environment files, generated artifacts, build output, or dependency folders.
- Keep task cards participant-facing and copyable into Codex Desktop.
- Ground model decisions in Amazon Bedrock Mantle Responses, the GPT-5.4 and GPT-5.5 model cards, API compatibility, and model listing documentation.
- Keep source paths, target paths, AWS architecture, Region, and model selection configurable and evidence-driven.
- Enforce `APPROVE MIGRATION`, `DEPLOY`, and `DESTROY` as separate explicit gates.

## Hub Constructs

- Task markdown lives under `data/tasks/en`.
- Ordered task IDs live in `src/app/lib/taskOrder.ts`.
- `/` and `/preview` present the same workshop journey.
- Task completion is stored only in the participant's browser.
- `public/downloads/azure-bedrock-workshop-main.zip` is generated from the clean participant starter repo.

## Verification

Run these checks after changing the hub:

```bash
npm run lint
npm run build
```

Before publishing, unzip the downloadable starter into `/tmp` and confirm `apps/aws-target-app` contains only `.gitkeep`.
