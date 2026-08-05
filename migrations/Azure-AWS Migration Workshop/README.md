# Azure OpenAI To AWS Migration Workshop

This Vercel-ready Next.js workshop guides participants through migrating an Azure OpenAI Chat Completions application to Amazon Bedrock OpenAI Responses with Codex Desktop agents.

The workshop includes the task-card experience, migration documentation, architecture guidance, and a downloadable participant starter. Progress is stored in each participant's browser with `localStorage`; the application has no server-side participant identity or progress storage.

## Run Locally

Requirements:

- Node.js 22
- npm 10

```bash
cd "migrations/Azure-AWS Migration Workshop"
npm ci
npm run dev
```

Open `http://localhost:3000`. The same workshop is also available at `http://localhost:3000/preview`.

## Workshop Flow

The ordered cards guide Codex Desktop through:

1. source selection and baseline capture;
2. creation of discovery, architecture, validation, and deployment agents;
3. schema-backed source, architecture, model/API, and deployment decisions;
4. explicit `APPROVE MIGRATION`, `DEPLOY`, and `DESTROY` gates;
5. local live Amazon Bedrock Responses validation;
6. manifest-driven CDK generation, preflight, deployment, observation, and teardown.

The bundled shopping cart is the release fixture, not a hardcoded migration target.

## Deploy On Vercel

Import `openai-on-aws/openai-solutions` as a Next.js project and set the Vercel **Root Directory** to:

```text
migrations/Azure-AWS Migration Workshop
```

The checked-in `vercel.json` uses:

- install command: `npm ci --no-audit --no-fund`
- build command: `npm run build`

No database or application environment variables are required for the workshop hub. The participant supplies cloud credentials only inside Codex Desktop during the relevant migration tasks; credentials must never be entered into this web application or committed to the repository.

## Task Content

Task Markdown lives under `data/tasks/en/`. Every file has `id`, `title`, `summary`, and `phase` frontmatter. `src/app/lib/taskOrder.ts` is authoritative; unlisted tasks are ignored.

## Validate

```bash
npm ci
npm run lint
npm run build
```

Before release, scrub the repository and participant ZIP for credentials, local paths, generated targets, caches, and build output.
