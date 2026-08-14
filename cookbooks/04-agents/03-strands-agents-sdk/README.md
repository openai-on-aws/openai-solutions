---
title: Running an agent on Bedrock with Strands
capabilities: [AGT-09, AGT-01]
primary_capability: AGT-09
industry: TRV
industry_scenario: >
  The same cancelled flight a third time, in Strands — the AWS-native agent SDK, and the
  one an AWS-shaped team is most likely to reach for because it is also the path to
  AgentCore deployment.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: [agents]
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-mantle:CallWithBearerToken
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-14
validated_with:
  python: "3.12"
  openai: "2.53.0"
  strands-agents: "1.52.0"
---

# Running an agent on Bedrock with Strands

[Strands](https://strandsagents.com/) is the AWS-native agent SDK, and it treats the
Bedrock OpenAI endpoint as a first-class target rather than a generic OpenAI-compatible
URL. If your team is already on AWS, this is the path that composes most naturally with
[`cookbooks/04-agents/04-agentcore-harness/`](../04-agentcore-harness/)](../04-agentcore-harness/) when the agent
needs to run somewhere other than a laptop.

Same scenario as the two recipes before it, so what is left to look at is the SDK.

| | |
|:--|:--|
| **What you will learn** | How to point Strands at the Responses API on Bedrock, and why the model class you choose decides whether it works at all |
| **Capability** | Strands against `bedrock-mantle` |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Medium — 9 to 10 cycles across the runs measured, 16 to 19 tool calls, around 12,000 to 13,000 input tokens |
| **You will need** | Inference permission, `bedrock-mantle:CallWithBearerToken`, and the `agents` group |

> **What it does.** Runs the same rebooking agent with `bedrock_mantle_config`, printing
> each tool call and result as it happens, then asks a follow-up from the transcript
> Strands keeps on the agent. **What it creates.** Nothing outside the process.

## Two things decide whether this works

**The model class.** Strands ships more than one, and only one of them can reach the
OpenAI models:

```python
from strands.models.openai_responses import OpenAIResponsesModel

model = OpenAIResponsesModel(
    bedrock_mantle_config={"region": REGION},
    model_id=MODEL_ID,
    params={"max_output_tokens": 4096, "store": False},
)
```

`BedrockModel` is a `bedrock-runtime` **Converse** client, and Converse does not serve
GPT-5.x — so it cannot reach these models no matter what you point it at. And note the
import path: `OpenAIResponsesModel` lives in `strands.models.openai_responses`, and is
**not** re-exported from `strands.models`, which is where `BedrockModel` and
`OpenAIModel` are. Importing from the obvious place gives you an `AttributeError`.

**The extra.** `bedrock_mantle_config` needs `strands-agents[openai]`. Without it you
get a clear instruction rather than a mystery:

```
ImportError: bedrock_mantle_config requires the 'aws-bedrock-token-generator' package.
Install it with: pip install strands-agents[openai]
```

That error is also the clue to the next section.

## Strands mints a bearer token; the Agents SDK signs with SigV4

This is the substantive difference between the two SDK recipes, and it is worth knowing
because it changes what can go wrong.

| | OpenAI Agents SDK | Strands |
|:--|:--|:--|
| How it reaches mantle | an `AsyncOpenAI` built with the Bedrock provider | `bedrock_mantle_config` |
| Credential form | SigV4 signature per request | a short-term **bearer token** |
| Needs | `openai[bedrock]` | `strands-agents[openai]` |

Strands derives the base URL and the credentials from the config itself, minting the token
from your IAM credentials
through the same generator that
[`cookbooks/01-foundations/03-bedrock-api-key-auth/`](../../01-foundations/03-bedrock-api-key-auth/)
uses directly. It refuses `api_key` or `base_url` in `client_args` when the mantle
config is set, rather than letting the two fight.

The config is typed and takes more than a Region, which is what "first-class" means in
practice: `region`, `boto_session` for picking up a non-default profile,
`credentials_provider`, and `expiry` for the token's lifetime. With no `region` it
resolves one through the boto3 chain — worth setting explicitly, because a Region
resolved from ambient configuration is how the same code reaches a different endpoint on
a colleague's machine.

One consequence for your IAM policy: bearer-token auth needs
`bedrock-mantle:CallWithBearerToken`, which the `AmazonBedrockMantleInferenceAccess`
managed policy grants. If you have built a tighter policy for SigV4-only inference,
Strands will need that action added.

## What the framework replaced

Same five tools, same goal, same instructions. `@tool` derives the schema from the
signature and the docstring, so — as in the Agents SDK — the docstring is the tool
description the model reads:

```python
@tool
def get_flight(flight_number: str) -> dict:
    """Status, route and seat availability for one flight."""
```

The loop is `agent(GOAL)`. Strands calls it a **cycle** rather than a turn, and
`result.metrics` carries the count alongside accumulated token usage.

By default Strands streams its own account of the run to stdout, which is genuinely
useful when you are watching an agent work. This script sets `callback_handler=None` and
prints its own trace instead, because two accounts of one run side by side are harder to
read than either alone.

## Watching it work, and where the tool result hides

`agent.stream_async(prompt)` is an async iterator of plain dicts. Strands
[documents the whole event set](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/overview/);
this recipe reads three keys of it, and one of them does the work:

```python
async for event in agent.stream_async(GOAL):
    if "message" in event:                      # a whole message joined the transcript
        for block in event["message"]["content"]:
            block.get("toolUse")                # a finished tool call
            block.get("toolResult")             # its result, a moment later
    if "data" in event:
        print(event["data"], end="")            # a chunk of answer text
    if "result" in event:
        result = event["result"]                # the finished AgentResult
```

**Both halves of the loop come from `message`**, which is what keeps the code short: the
calls and their results arrive on the same key, and the arguments are complete when you
read them.

There is a second, earlier signal, and knowing why this recipe does *not* use it is the
useful part. `current_tool_use` fires while a call is still being written, and its `input`
**accumulates as the stream arrives** — the tool's name is known before its arguments are.
That is exactly what a progress spinner wants, and exactly what you do not want if you are
printing the call, because you can print half an argument. So: `current_tool_use` for "the
agent is calling get_flight", `message` for anything that needs the whole call.

**A tool result has no event of its own.** This is the asymmetry with
[`cookbooks/04-agents/02-openai-agents-sdk/`](../02-openai-agents-sdk/)](../02-openai-agents-sdk/), which emits a
semantic `tool_output` event carrying the object your function returned. Here the result
arrives as a `toolResult` block, serialised to text, so a trace that summarises it parses
it back.

**Both need the tool named on the way back**, because the model asks for several at once
and every call is announced before any result returns. Strands gives you the `toolUseId`
on both halves:

```
   → get_entitlements(tier='gold')
   → get_entitlements(tier='silver')
   → find_alternatives(origin='LIS', destination='DUB')
   ← get_entitlements: tier=gold, rebooking_priority=1, hotel_if_overnight=True
   ← get_entitlements: tier=silver, rebooking_priority=2, hotel_if_overnight=True
   ← find_alternatives: 2 direct, 1 connecting
```

**Two lifecycle keys are worth handling on Bedrock specifically.**
`event_loop_throttled_delay` is how you learn the agent hit a tokens-per-minute limit and
backed off — it is already retrying, and without this you would infer it from the clock.
`force_stop`, with `force_stop_reason`, is the loop giving up rather than finishing, which
is the difference between a short answer and an abandoned one.

**The same body works as a callback handler.** Strands offers async iterators and
callback handlers over the identical event set, differing in execution model rather than
content: `Agent(callback_handler=handle)` receives the events as keyword arguments for a
synchronous application. `callback_handler=None` on the agent here is what keeps the
output readable — the default handler is Strands' own printer, reasonable for a terminal,
and it would interleave its account of the run with this one.

## What the run cost

Two runs on 2026-08-13, `us-east-1`, `openai.gpt-5.6-terra`:

| | Run 1 | Run 2 |
|:--|:--|:--|
| Cycles | 10 | 9 |
| Tool calls | 16 | 19 |
| Rebooked | all 4 passengers | 3, one left for a human |
| Tokens | 12,071 in / 2,760 out | 12,981 in / 3,207 out |

**Do not read a framework comparison into those numbers, and do not read a cost estimate
into either column.** Across five runs of this one scenario — two on the Agents SDK,
three here — the agent rebooked between 2 and 4 passengers and made between 8 and 19 tool
calls. The model decides how much verification to do before committing, and that varies
far more than anything either SDK contributes. Comparing frameworks on cost needs many
runs of each against a fixed task; one run of each tells you only that both work.

What the numbers do show is the shape common to every agent loop: input dominates and
grows each cycle, because the instructions, the five tool definitions and the transcript
so far are resent every time.

## Why this recipe keeps the transcript to itself

[`cookbooks/04-agents/01-the-agent-loop/`](../01-the-agent-loop/)](../01-the-agent-loop/) and
[`cookbooks/04-agents/02-openai-agents-sdk/`](../02-openai-agents-sdk/)](../02-openai-agents-sdk/) both store their
turns and delete them when they finish. This recipe retains nothing, and the reason is
specific rather than a matter of taste.

**Retention is not a parameter in this provider — it follows `stateful`.** Writing
`params={"store": True}` has no effect: the provider assigns `store` from the `stateful`
flag after your params are unpacked, so the flag is the control. Which makes the question
"should this recipe be stateful?", and that is a larger decision than retention:

The same two-turn conversation, run both ways:

| | `stateful=False` | `stateful=True` |
| --- | --- | --- |
| Second turn's input tokens | 61 | **61** |
| `len(agent.messages)` after two turns | 4 | **0** |
| Retained server-side | nothing | one response per cycle |

**It does not reduce what you are billed.** The second turn cost the same 61 input tokens
either way, because the model receives the prior context regardless of who kept it. What
changes is the payload you upload and the transcript you hold locally.

**And the transcript you hold locally goes to zero.** `agent.messages` is emptied after
every turn, and Strands raises if you pass a `conversation_manager` or `context_manager`
alongside a stateful model, because the service owns the history. That removes the
sliding-window trimming a long agent loop eventually needs, and this disruption run takes
eight cycles to work through the manifest.

**Response ids are reachable, but only the latest one.** `agent._model_state` carries
`{"response_id": "resp_…"}`, a private attribute holding exactly one id — where a stateful
run of this recipe would have stored one response per cycle. Nothing surfaces the others:
`result.to_dict()`, `agent.messages` and `result.metrics` carry no `resp_…` at all, and the
`tracking_id` on each message is a Strands UUID of its own. So all but the last would sit
out the 30-day window with no handle to remove them.

Retaining data you cannot remove is a worse default than not retaining it. If you need
server-side state with Strands, keep your own record of the ids as they go past, or use a
project whose data-retention mode you have set deliberately — see
[`cookbooks/01-foundations/02-projects/`](../../01-foundations/02-projects/).

## Where the conversation lives

Strands keeps the transcript on the agent object, so a follow-up is just another call to
the same agent:

```python
result = agent(GOAL)
follow_up = agent("Which passengers could not be rebooked?")
```

`agent.messages` held 18 items after the first run. Because the transcript is in your
process, `store=False` costs nothing here — the agent is already the record, and no
server-side state is needed to continue. Note that `result.metrics.accumulated_usage`
accumulates across calls on the same agent, so the second figure is the running total
rather than the follow-up alone.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md): a Region with model
  access and inference permission on `bedrock-mantle`.
- **`bedrock-mantle:CallWithBearerToken`**, because Strands authenticates with a token.
- The `agents` dependency group: `uv sync --group agents`.
- Working AWS credentials — `aws sts get-caller-identity` must succeed.

**Cost:** medium. Around a dozen model calls across the run and the follow-up, with input
growing each cycle. No per-operation tool fees. See
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

The flight, passenger and entitlement data in [`data/`](data/) is synthetic.

## Run it

```bash
uv sync --group agents
uv run python 04-agents/03-strands-agents-sdk/python/strands_agents_sdk.py
```

## Production considerations

- **Set a cycle ceiling.** This script relies on the agent finishing on its own, which is
  fine for a demonstration and not for production. Strands takes limits on the agent; set
  one and decide what a truncated run means.
- **Pass `region` explicitly.** Region resolution through the boto3 chain is convenient
  and makes the endpoint depend on ambient configuration. `openai.gpt-5.6-sol` is not
  served in `us-west-2`, so an agent that resolves its own Region works on one machine
  and fails on another.
- **Token lifetime is yours to choose.** `expiry` on the mantle config controls it. A
  long-running agent host wants a deliberate value rather than the default.
- **Keep your own record of the writes.** `REBOOKINGS` here; a database in production.
  The model's summary is an account of the run, not the system of record.
- **`params` is where inference settings go**, including `store` and
  `max_output_tokens`. A reasoning-heavy agent needs headroom there, because reasoning
  tokens draw on the same budget as the answer.

## Data handling and security

- **Credentials come from the AWS credential chain.** Strands exchanges them for a
  short-term bearer token; no key is written to disk, and none is printed.
- **`store=False`** through `params`, so no transcript is retained by AWS — which here is
  a necessity rather than a preference, for the reason above.
- **Nothing is sent outside AWS.** Strands has no third-party telemetry destination, so
  unlike the Agents SDK there is no trace-export setting to change.
- **Inference stays in the Region you name**, which is printed at the start.
- All passenger data is synthetic, and identifiers are invented.

## Limitations and non-goals

- One agent, no multi-agent orchestration. Strands supports handoffs and swarms; those
  are a different subject.
- No cycle limit set, as noted above.
- No AgentCore deployment here — that is
  [`cookbooks/04-agents/04-agentcore-harness/`](../04-agentcore-harness/)](../04-agentcore-harness/).
- The tools are in-process functions over a JSON file, not a reservation system.
- Not a benchmark. The token figures are one run, and the section above says why they
  cannot be compared with the Agents SDK recipe's.

## Clean up

Nothing to remove. Inference only, `store=False` leaves no stored response, the bearer
token expires on its own, and the write tool mutates an in-memory copy of
[`data/`](data/) that is discarded when the process exits.

## Next steps

- [`cookbooks/04-agents/04-agentcore-harness/`](../04-agentcore-harness/)](../04-agentcore-harness/) — running an
  agent as a managed AWS deployment rather than a local process.
- [`cookbooks/04-agents/02-openai-agents-sdk/`](../02-openai-agents-sdk/)](../02-openai-agents-sdk/) — the same
  agent in the OpenAI Agents SDK, if you have not read it.
- [`cookbooks/05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/)
  — the answer to input growing every cycle.

## Further reading

- [Strands documentation](https://strandsagents.com/) — the SDK itself.
- [Amazon Bedrock AgentCore developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
  — where a Strands agent goes when it leaves your laptop.
