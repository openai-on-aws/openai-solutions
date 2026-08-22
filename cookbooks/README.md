# OpenAI models on Amazon Bedrock — cookbooks

Runnable recipes for building with the OpenAI GPT-5.6 models on Amazon Bedrock.

Each recipe solves one clearly defined problem, runs end to end, and is set in a concrete
industry scenario so the constraints are real ones — an audit trail a compliance team would
accept, a cost per transaction that rules out an approach, a rule that has to be applied
exactly as written.

## What is different about running these models on Bedrock

The GPT-5.6 family is served through the **OpenAI Responses API on the
`bedrock-mantle` endpoint**, authenticated with SigV4 from the standard AWS
credential chain. Three consequences shape every recipe here:

- **There is no API key and no token to mint.** If `aws sts get-caller-identity`
  works, the recipes work.
- **Inference is authorized on a Project ARN**, not on a model ARN. That makes
  [Projects](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html) the unit of
  both access isolation and cost attribution, and it is why two workloads can share one AWS
  account cleanly — see [`cookbooks/01-foundations/02-projects/`](01-foundations/02-projects/).
- **Some capabilities have no first-party equivalent**: native
  [Web Search](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html)
  backed by an AWS-operated index with no data egress by default, explicit
  prompt-caching breakpoints, and Bedrock Guardrails.

## Prerequisites

- An AWS account with access to the OpenAI models in a
  [supported Region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html).
- IAM permissions for inference on `bedrock-mantle`. The
  [`AmazonBedrockMantleInferenceAccess`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockMantleInferenceAccess.html)
  managed policy is the simplest starting point; it grants
  `bedrock-mantle:CreateInference` on `project/*`, the two `bedrock-websearch`
  retrieval actions, and the AWS Marketplace subscribe permission these
  third-party models need. Individual recipes list anything further.
- Python 3.10 or newer.

## Setup

These recipes use [uv](https://docs.astral.sh/uv/), which provisions the
interpreter, creates the virtualenv, and installs exactly what `uv.lock` pins:

```bash
uv sync
cp .env.example .env      # then edit: Region and model tier
```

A recipe needing more than the base stack names a dependency group in its README —
install it with `uv sync --group <name>`.

Prefer pip? `requirements.txt` is generated from `uv.lock` and carries the same
exact versions:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Your first call

```python
import os

from openai import OpenAI
from openai.providers import bedrock

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "openai.gpt-5.6-terra"

client = OpenAI(provider=bedrock(region=REGION))

response = client.responses.create(
    model=MODEL_ID,
    input="Explain prompt caching in two sentences.",
    max_output_tokens=256,
    store=False,
)

print(f"{MODEL_ID} in {REGION}")
print(response.output_text)
print(response.usage)
```

That is the whole thing. No API key, no token to mint, no base URL — the provider
derives the regional endpoint and takes credentials from the AWS credential chain.

`store=False` is deliberate. Responses requests on Bedrock store the response by default, and
AWS keeps it — input and output — for 30 days, which is what lets a later call reference it with
`previous_response_id`. A single-turn example has nothing to refer back to, so it opts out.
[`cookbooks/01-foundations/04-conversation-state/`](01-foundations/04-conversation-state/) is
where that choice is made properly.

## How the recipes are organized

Five groups, each with its own README:

| Directory | What it covers |
| --- | --- |
| [`cookbooks/01-foundations/`](01-foundations/) | Making a call, Projects as the workload boundary, credentials, conversation state, streaming, and choosing between the three models |
| [`cookbooks/02-reasoning-and-output/`](02-reasoning-and-output/) | Strict schemas, reasoning effort and verbosity, tool calling, carrying reasoning across turns, and tools Bedrock runs for you |
| [`cookbooks/03-grounding-and-multimodal/`](03-grounding-and-multimodal/) | Native Web Search with citations, and scoring whether an answer is faithful to its sources |
| [[`cookbooks/04-agents/`](04-agents/)](04-agents/) | An agent loop written by hand, the same agent run by the OpenAI Agents SDK and by Strands, and one deployed to an AgentCore harness |
| `cookbooks/05-production/` | Explicit prompt caching, PII masking, and the questions a security review will ask |

Every recipe is one directory:

```
01-first-call/
├── README.md          the problem, the approach, the prerequisites
├── python/            the reference implementation
│   └── first_call.py
├── typescript/        the port, as those land
└── data/              synthetic inputs, only when the recipe needs them
```

The narrative lives once, in the recipe's README, above both language directories: a
recipe's teaching content is the same in any language, and only the implementation differs.

**Python is the implementation to read today.** Every recipe has one, and it is the version
that has been run against a real account and validated. TypeScript is coming, and until a
given port exists its `typescript/` directory carries a short note saying so — a reader
looking for TypeScript should find an answer rather than an empty folder.

The reason each language gets its own directory, rather than the script sitting beside the
README, is that a TypeScript recipe is not a single file: it needs its own `package.json`
and `tsconfig.json`. At the recipe root those would be ambiguous about whether they govern
the recipe or just one language. Paying one extra click now also means the path you bookmark
today still resolves after the port lands.

### All recipes

<!-- BEGIN GENERATED: recipe-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-foundations/01-first-call/`](01-foundations/01-first-call/) | Your first call, and the four permissions it needs | beginner | low |
| [`01-foundations/02-projects/`](01-foundations/02-projects/) | Projects: the resource that authorizes inference and attributes cost | beginner | low |
| [`01-foundations/03-bedrock-api-key-auth/`](01-foundations/03-bedrock-api-key-auth/) | Authenticating with a Bedrock API key | beginner | low |
| [`01-foundations/04-conversation-state/`](01-foundations/04-conversation-state/) | Conversation state, and who keeps the transcript | beginner | low |
| [`01-foundations/05-streaming/`](01-foundations/05-streaming/) | Streaming, and what the typed events tell you | beginner | low |
| [`01-foundations/06-choosing-a-model/`](01-foundations/06-choosing-a-model/) | Choosing a model: the same prompt on Luna, Terra and Sol | beginner | low |
| [`02-reasoning-and-output/01-structured-claims-intake/`](02-reasoning-and-output/01-structured-claims-intake/) | Structured outputs: three levels of guarantee on an extracted record | beginner | low |
| [`02-reasoning-and-output/02-reasoning-effort-and-verbosity/`](02-reasoning-and-output/02-reasoning-effort-and-verbosity/) | Right-sizing reasoning effort and verbosity against a quality bar | intermediate | medium |
| [`02-reasoning-and-output/03-tool-calling/`](02-reasoning-and-output/03-tool-calling/) | Tool calling: the flat schema, and the loop around it | intermediate | low |
| [`02-reasoning-and-output/04-reasoning-across-turns/`](02-reasoning-and-output/04-reasoning-across-turns/) | Carrying reasoning across turns | advanced | medium |
| [`02-reasoning-and-output/05-server-side-tools/`](02-reasoning-and-output/05-server-side-tools/) | Server-side tools: Bedrock as the MCP client | advanced | low |
| [`03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](03-grounding-and-multimodal/01-grounded-regulatory-monitoring/) | Grounded regulatory change monitoring with native Web Search | intermediate | medium |
| [`03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](03-grounding-and-multimodal/02-scoring-a-grounded-answer/) | Trusting a grounded answer: scoring it against its sources | intermediate | medium |
| [`03-grounding-and-multimodal/03-reading-a-scanned-manual/`](03-grounding-and-multimodal/03-reading-a-scanned-manual/) | Reading a scanned manual: photos, tables and figures | intermediate | medium |
| [`03-grounding-and-multimodal/04-rag-with-knowledge-bases/`](03-grounding-and-multimodal/04-rag-with-knowledge-bases/) | RAG with Bedrock Knowledge Bases: retrieve then generate with citations | intermediate | low |
| [`04-agents/01-the-agent-loop/`](04-agents/01-the-agent-loop/) | The agent loop: a goal, some tools, and a round ceiling | advanced | medium |
| [`04-agents/02-openai-agents-sdk/`](04-agents/02-openai-agents-sdk/) | Running an agent on Bedrock with the OpenAI Agents SDK | intermediate | medium |
| [`04-agents/03-strands-agents-sdk/`](04-agents/03-strands-agents-sdk/) | Running an agent on Bedrock with Strands | intermediate | medium |
| [`04-agents/04-agentcore-harness/`](04-agents/04-agentcore-harness/) | Deploying an agent to AgentCore Harness | advanced | low |
<!-- END GENERATED: recipe-index -->

**Nineteen of the twenty-two recipes are here.** `01-foundations` landed first because everything
else assumes it: the call, the permissions, the credentials, and the choice of model. One group is
left:

| Pull request | Adds | Recipes |
| --- | --- | --- |
| `05-production` | Explicit prompt caching, PII masking, and the questions a security review asks | 3 |

Each group brings its own landing page and appends its rows to the index above. The paths named
in this README resolve as their groups land.

**Recipes are plain executable Python, not notebooks**, and each one is
self-contained. There is no shared framework to learn first: the client
construction and the model ID are in the recipe, where you can see them.

Every recipe was run end to end against a real Bedrock account, and its README opens with
the date that happened on. Check it: these models and this endpoint change every few weeks,
so a recipe last run three months ago is a weaker promise than one from last week.

## Choosing a model

The GPT-5.6 family has three members, and recipes name the one they use in a
constants block at the top of the file:

| Model ID | Use it for | Regions |
| --- | --- | --- |
| `openai.gpt-5.6-luna` | High volume, latency-sensitive: classification, routing, summarization | `us-east-1`, `us-east-2`, `us-west-2` |
| `openai.gpt-5.6-terra` | The default for production workloads | `us-east-1`, `us-east-2`, `us-west-2` |
| `openai.gpt-5.6-sol` | Hardest reasoning, agentic coding, long-horizon tasks | `us-east-1`, `us-east-2` |

**Sol is not served in `us-west-2`.** Switching Region without checking gives you
`404 not_found_error: The model 'openai.gpt-5.6-sol' does not exist`, which reads like
a typo in the model ID rather than a Region problem.

All three take text and images in, produce text out, and have a 1,050,000-token
context window. Confirm current availability in
[Supported models by AWS Region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html).

## Cost

**These recipes call foundation models and therefore incur charges.** The index above
gives each one a band, and every recipe's README states the counts behind it — how many
calls, what the output is capped at, and whether a non-token fee applies:

| Band | What it means |
| --- | --- |
| **low** | A handful of calls with small inputs and output capped in the low hundreds of tokens. No fees beyond tokens |
| **medium** | Dozens of calls, **or** reasoning-heavy output, **or** a per-operation fee on top of tokens, **or** a lot of injected context. Native Web Search is the common reason: it is billed per retrieval operation, separately from tokens |
| **high** | Sustained agent loops or long-context work at scale — worth thinking about before running twice |

The bands describe **that recipe's own run**, not the pattern at production volume. They
are deliberately not prices: rates change per model and per Region, so multiply the token
counts each recipe prints by the current
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

Two things that catch people out. **Reasoning tokens are output tokens** — they are billed,
and they do not appear in the text you read, so every recipe prints
`usage.output_tokens_details.reasoning_tokens`. And **one Web Search retrieval step is one
billed operation however many query strings it contains**, so budget per operation rather
than per turn.

## Data handling

Recipes take credentials from the AWS credential chain and never read a key from a
file or embed one in code. They set `store=False`, keep inference in the Region you
name, and set `external_web_access: False` on Web Search so retrieval is served
from the AWS-operated index. Synthetic data is fabricated, never derived from real
records — each recipe using it says so in its prerequisites.

## Troubleshooting

Failures that are easy to misdiagnose, with what actually causes them.

| Symptom | Cause |
| --- | --- |
| `401 invalid_api_key`, but `aws sts get-caller-identity` works | `AWS_BEARER_TOKEN_BEDROCK` is set in your environment. The provider prefers a key over your IAM credentials, so a short-term key that has expired fails while the AWS CLI keeps working. The error never mentions a token. Run `unset AWS_BEARER_TOKEN_BEDROCK`. See [`cookbooks/01-foundations/03-bedrock-api-key-auth/`](01-foundations/03-bedrock-api-key-auth/) |
| `AccessDenied` on the very first call, with no mention of a model | The OpenAI models are third-party AWS Marketplace subscriptions, so the calling identity needs `aws-marketplace:Subscribe`. It is in `AmazonBedrockMantleInferenceAccess` |
| `AccessDenied` on inference with credentials that clearly work | Inference is authorized on a **Project ARN**, not a model ARN. Your policy has to cover the project you are calling — including `project/default` |
| `ResourceNotFoundException` on a model that should exist | Wrong Region, or model access not enabled there. Sol is not served in `us-west-2`, where the same call returns `404 not_found_error: The model 'openai.gpt-5.6-sol' does not exist` |
| `400 validation_error: The model ... does not support the '/v1/chat/completions' API` | Chat Completions is not available for the GPT-5.x family on Bedrock, on either path. Use the Responses API — OpenAI's [migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses) covers the port |
| `400 unsupported_parameter: 'temperature' is not supported with this model` | Sampling parameters are accepted only when `reasoning={"effort": "none"}`. The message names the model, not the effort level |
| A tool result is ignored and the model answers as though no tool ran, HTTP 200 | The result was returned in the Chat Completions shape, `{"role": "tool", ...}`. The Responses API needs `{"type": "function_call_output", "call_id": ...}`, and the old shape is accepted without error |
| A grounded turn completes with empty `output_text` and no `message` item | `max_tool_calls` was exhausted before the model wrote an answer. The searches are still billed. Raise the budget and instruct the model to stop searching and answer |
| `429` | A tokens-per-minute quota, not a request-rate limit — there is no requests-per-minute quota. Back off; the client already retries |
| `ModuleNotFoundError: openai.providers` | The Bedrock extra is missing. `uv sync`, or `pip install "openai[bedrock]"` |
| A grounded answer with no citations, HTTP 200, no error | Web Search is silently off, usually because `bedrock-websearch:InvokeSearch` is denied. Check the `web_search_call` items in `response.output` for `status: "failed"` rather than trusting the HTTP code |
| A guardrail is configured, but a call through the Responses API is never screened | Guardrails are applied by a separate `ApplyGuardrail` call on `bedrock-runtime`, not inline on this endpoint. Screening the input before the call and the answer after it is the supported pattern, and it can run concurrently with inference. |
| An `input_file` request returns 200 with an empty answer | The `file_url` uses `https://`. Only `s3://` is fetched, and any other scheme is ignored rather than rejected, so the model answers with no document in front of it. Use `s3://`, or inline the bytes as base64 |
| `400 validation_error: unsupported image_url scheme` | `input_image` accepts `data:` and `s3://` only. A public HTTPS image URL, which the first-party API takes, is rejected here |
| `400 validation_error: Unsupported file type: 'unknown'` | An `input_file` with a `file_url` and no `filename`. The type is inferred from the filename, so it is required on that path |

## Further reading

- [OpenAI model cards on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards-openai.html)
- [Web Search on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html)
- [Projects on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html)
- [OpenAI models in Amazon Bedrock](https://developers.openai.com/api/docs/guides/amazon-bedrock)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
