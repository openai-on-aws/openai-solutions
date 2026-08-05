---
id: map-chat-completions-to-responses
title: Map Chat Completions To Responses
summary: Define the exact API translation and GPT-5.4 or GPT-5.5 eligibility decision.
phase: Migration Analysis
---

Define the inference migration separately from the infrastructure choice. The architect must translate observed Chat Completions behavior into an explicit Amazon Bedrock Responses contract and leave live model availability unverified until credentials are supplied.

- Map messages, roles, outputs, state, streaming, tools, and errors.
- Review each source parameter instead of copying it automatically.
- Limit candidates to documented GPT-5.4 or GPT-5.5 Responses support.
- Store complete discovery and inference URLs as separate values.

```text
Design the Azure OpenAI Chat Completions to Amazon Bedrock OpenAI Responses migration.

Map every inference behavior the source actually uses, including roles, inputs, outputs, parameters, state, streaming, tools, structured output, retries, timeouts, and errors. Recommend an eligible GPT-5.4 or GPT-5.5 candidate using the workshop's documented model and endpoint rules.

Show me the proposed API transformation, parameter dispositions, provisional model and Region, endpoint decision, behavior risks, and anything that still requires live verification.
```

Continue when the provisional model/API decision validates and every Chat Completions behavior has a documented Responses disposition.
