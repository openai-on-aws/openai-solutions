# Security

This repository is a public training hub, not a production application.

## Secrets

- Do not commit credentials, API keys, `.env.local`, screenshots containing secrets, or generated secrets.
- The downloadable starter must not contain generated target code or generated artifacts.
- Participants provide Bedrock Mantle credentials through terminal environment variables only.

## Workshop Progress

- `/` and `/preview` store task completion only in the participant's browser.
- The hub has no participant accounts or server-side progress storage.

## Model And API Claims

- Treat Azure OpenAI as deployment-name and model agnostic on the source side.
- Select only an available, Responses-compatible `openai.gpt-5.4` or `openai.gpt-5.5` tuple supported by its model card.
- Record the complete authoritative inference URL; do not derive it from a generic Mantle example.
- Treat Azure parameters as source evidence and omit unsupported target parameters.
- Never deploy without `DEPLOY` or tear down without `DESTROY`.

## Reporting Security Issues

Do not disclose sensitive security details in public issues. Use the private disclosure process for the organization that hosts this workshop.
