---
id: test-migrated-app-live
title: Test The Migrated Application Live
summary: Compare live Bedrock-backed target behavior with the source acceptance profile.
phase: Live Bedrock Validation
---

Run the generated target locally against the approved live Amazon Bedrock Responses endpoint. This is the first point where the migration is proven as an application, not only as code and configuration.

- Start every required target component with terminal-only credentials.
- Exercise representative APIs and browser workflows from the source baseline.
- Confirm real Bedrock inference, the selected model, and no mock fallback.
- Capture only redacted acceptance evidence under `/tmp`.

```text
Run the generated target locally against the approved live Amazon Bedrock Responses endpoint.

Ask me to enter the Amazon Bedrock API key securely in the target terminal, start the application, and repeat the representative API and browser workflows from the source baseline.

Show me the source-to-target parity result, confirmed model and inference path, observed errors, and any blocker. Clear the credential from the terminal after validation.
```

Continue when the local target preserves the source acceptance contract and live Bedrock-backed workflows pass without fallback.
