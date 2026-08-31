# Foundations

> **How do I call these models on AWS at all?**

Start here. These five recipes take you from an empty terminal to a working call, and then
through the four decisions everyone makes in their first week: how to authenticate, who keeps
the conversation, whether to stream, and which of the three GPT-5.6 models to point at the
problem.

Each one runs in under a minute and costs a fraction of a cent. None of them create AWS
resources, so you can work through the whole group and leave nothing behind.

## What makes this different from calling OpenAI directly

The API is the same — this is the OpenAI Responses API, and your existing knowledge of it
carries over. What changes is everything around the call:

- **There is no API key to manage.** The Bedrock provider signs requests with SigV4 from the
  standard AWS credential chain, so on an EC2 instance or in Lambda there is no credential in
  your code at all. [`01-first-call/`](01-first-call/) shows the four lines this takes, and
  [`03-bedrock-api-key-auth/`](03-bedrock-api-key-auth/) covers the times you do want a key.
- **IAM authorizes every call**, and it does so on a Project ARN rather than a model ARN.
  That makes [Projects](02-projects/) the unit for isolating one workload from another and for
  attributing its cost, without standing up a second AWS account.
- **Inference stays in the Region you name**, and your data does not leave it.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-first-call/`](01-first-call/) | Your first call, and the four permissions it needs | beginner | low |
| [`02-projects/`](02-projects/) | Projects: the resource that authorizes inference and attributes cost | beginner | low |
| [`03-bedrock-api-key-auth/`](03-bedrock-api-key-auth/) | Authenticating with a Bedrock API key | beginner | low |
| [`04-conversation-state/`](04-conversation-state/) | Conversation state, and who keeps the transcript | beginner | low |
| [`05-streaming/`](05-streaming/) | Streaming, and what the typed events tell you | beginner | low |
| [`06-choosing-a-model/`](06-choosing-a-model/) | Choosing a model: the same prompt on Luna, Terra and Sol | beginner | low |
<!-- END GENERATED: group-index -->

## Suggested order

Read [`01-first-call/`](01-first-call/) first, whatever else you need — it is the one that
explains what authorizes a call, and the permission model behind it is the thing most likely
to stop you. After that the group is à la carte:

| If you want to | Read |
| --- | --- |
| Separate two workloads in one account, or attribute their cost | [`cookbooks/01-foundations/02-projects/`](02-projects/) |
| Use a key because your tool cannot sign with SigV4 | [`03-bedrock-api-key-auth/`](03-bedrock-api-key-auth/) |
| Build anything with more than one turn | [`04-conversation-state/`](04-conversation-state/) |
| Put a model behind an interface a person waits in front of | [`05-streaming/`](05-streaming/) |
| Decide which of Luna, Terra and Sol to use | [`06-choosing-a-model/`](06-choosing-a-model/) |

## Running these

```bash
uv sync
uv run python 01-foundations/01-first-call/python/first_call.py
```

One recipe needs an extra dependency group, because it mints a short-term Bedrock key:

```bash
uv sync --group foundations
uv run --group foundations python \
  01-foundations/03-bedrock-api-key-auth/python/bedrock_api_key_auth.py
```

Every recipe prints the request before it prints the answer, so you can follow what is being
sent and why without reading the source. Each README states its prerequisites, the Region it
was validated in, what it costs, and what it deliberately leaves out. See the
[cookbooks README](../README.md) for setup and the IAM permissions common to all of them.

## Where to go next

- [`cookbooks/02-reasoning-and-output/`](../02-reasoning-and-output/) — shaping what comes back:
  strict schemas, reasoning effort, verbosity and tool calling.
- [`cookbooks/03-grounding-and-multimodal/`](../03-grounding-and-multimodal/) — giving the model
  current information with Bedrock's native Web Search, and checking that its answer is
  faithful to the sources.
- [`cookbooks/05-production/`](../05-production/) — what changes at volume: prompt caching and
  PII screening.
