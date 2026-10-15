# GPT-5.4

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

> A more affordable model for coding and professional work.

Model ID: `gpt-5.4`

GPT-5.4 is a flagship model for complex professional work.
Learn more in our [GPT-5.4 model guidance](/api/docs/guides/latest-model?model=gpt-5.4). Reasoning.effort supports: none (default), low, medium, high and xhigh.

## Model details

- Default snapshot: `gpt-5.4-2026-03-05`
- Input modalities: text, image
- Output modalities: text
- 1,050,000 context window
- 128,000 max output tokens
- Aug 31, 2025 knowledge cutoff
- Reasoning token support

## Pricing

Pricing is based on the number of tokens used, or other metrics based on the model type. For tool-specific models, like search and computer use, there’s a fee per tool call. See details in the [pricing page](/api/docs/pricing).

### Text tokens

| Metric | Price | Unit |
| --- | ---: | --- |
| Input | $2.5 | 1M tokens |
| Cached input | $0.25 | 1M tokens |
| Output | $15 | 1M tokens |

- For models with a 1.05M context window (GPT-5.4 and GPT-5.4 Pro), prompts with >272K input tokens are priced at 2x input and 1.5x output for the full session for standard, batch, and flex.
- Regional processing (data residency) endpoints are charged a 10% uplift for GPT-5.4 and GPT-5.4 Pro.

## Endpoints

| Endpoint | Route | Support |
| --- | --- | --- |
| Live | `v1/live/sessions` | Not supported |
| Chat Completions | `v1/chat/completions` | Supported |
| Responses | `v1/responses` | Supported |
| Realtime | `v1/realtime` | Not supported |
| Realtime translation | `v1/realtime/translations` | Not supported |
| Realtime transcription | `v1/realtime/transcription_sessions` | Not supported |
| Assistants | `v1/assistants` | Not supported |
| Batch | `v1/batch` | Supported |
| Fine-tuning | `v1/fine-tuning` | Not supported |
| Embeddings | `v1/embeddings` | Not supported |
| Image generation | `v1/images/generations` | Not supported |
| Videos | `v1/videos` | Not supported |
| Image edit | `v1/images/edits` | Not supported |
| Speech generation | `v1/audio/speech` | Not supported |
| Transcription | `v1/audio/transcriptions` | Not supported |
| Translation | `v1/audio/translations` | Not supported |
| Moderation | `v1/moderations` | Not supported |
| Completions (legacy) | `v1/completions` | Not supported |

## Supported features

- streaming
- structured_outputs
- function_calling
- file_search
- file_uploads
- image_input
- web_search
- prompt_caching

## Supported tools

Tools supported by this model when using the Responses API.

- function_calling
- web_search
- file_search
- tool_search
- image_generation
- code_interpreter
- hosted_shell
- apply_patch
- skills
- computer_use
- mcp

## Quick comparison

| Model | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| GPT-5.4 | $2.5 | $0.25 | $15 |
| GPT-5.2 | $1.75 | $0.175 | $14 |
| GPT-5.4 Mini | $0.75 | $0.075 | $4.5 |

## Snapshots

Snapshots let you lock in a specific version of the model so that performance and behavior remain consistent. Below is a list of all available snapshots and aliases for GPT-5.4.

- `gpt-5.4-2026-03-05`

## Rate limits

Rate limits ensure fair and reliable access to the API by placing specific caps on requests, tokens, audio duration, or other usage within a given time period. Your usage tier determines how high these limits are set and automatically increases as you send more requests and spend more on the API.

### Standard

| Tier | RPM | TPM | Batch queue limit |
| --- | ---: | ---: | ---: |
| Build | 5,000 | 1,000,000 | 3,000,000 |
| Launch | 10,000 | 4,000,000 | 200,000,000 |
| Grow | 15,000 | 40,000,000 | 15,000,000,000 |

### Long Context

> 272K input tokens

| Tier | RPM | TPM | Batch queue limit |
| --- | ---: | ---: | ---: |
| Build | 500 | 1,000,000 | 40,000,000 |
| Launch | 2,000 | 10,000,000 | 200,000,000 |
| Grow | 8,000 | 20,000,000 | 2,000,000,000 |
