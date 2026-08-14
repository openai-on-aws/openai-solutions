---
title: Running an agent on Bedrock with the OpenAI Agents SDK
capabilities: [AGT-06, AGT-01]
primary_capability: AGT-06
industry: TRV
industry_scenario: >
  The same cancelled flight as the previous recipe, handled by the same five tools and
  the same goal — but with the OpenAI Agents SDK running the loop, which is what an
  airline would actually ship rather than a hand-written while loop.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: [agents]
iam_actions:
  - bedrock-mantle:CreateInference
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-14
validated_with:
  python: "3.12"
  openai: "2.53.0"
  openai-agents: "0.20.0"
---

# Running an agent on Bedrock with the OpenAI Agents SDK

Nobody ships the hand-written loop. You write it once to understand it — that is
[[`cookbooks/04-agents/01-the-agent-loop/`](../../04-agents/01-the-agent-loop/)](../01-the-agent-loop/) — and then you use a
framework, because retries, turn limits, tool schemas and result handling are solved
problems. This recipe runs the identical scenario through the
[OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents), so what you
see is the framework rather than a new problem.

| | |
|:--|:--|
| **What you will learn** | How to point the OpenAI Agents SDK at Bedrock, and the one setting a Bedrock workload must change |
| **Capability** | The Agents SDK against the Responses API on `bedrock-mantle` |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Medium — 5 to 7 model calls across the runs measured, 7,100 to 12,100 input tokens, plus a two-call follow-up |
| **You will need** | Inference permission only, and the `agents` dependency group |

> **What it does.** Hands the same goal, the same five tools and the same instructions
> to `Runner.run_streamed()`, printing each tool call and its result as the agent makes
> them, then the rebookings and the token cost.
> **What it creates.** Nothing outside the process; the write tool mutates an in-memory
> copy of the flight data.

## The client is the integration point

The SDK takes an OpenAI client and uses it for every call, so pointing it at Bedrock is
a matter of building the right client:

```python
from agents import Agent, OpenAIResponsesModel, Runner, function_tool
from openai import AsyncOpenAI
from openai.providers import bedrock

agent = Agent(
    name="Disruption manager",
    instructions=INSTRUCTIONS,
    model=OpenAIResponsesModel(
        model=MODEL_ID,
        openai_client=AsyncOpenAI(provider=bedrock(region=REGION), max_retries=3),
    ),
    tools=TOOLS,
)
```

That is the entire Bedrock-specific part. SigV4 from the AWS credential chain, the
regional `bedrock-mantle` endpoint and the `openai/v1` path all come from the provider,
so there is no token to mint and no base URL to assemble.

Two details worth knowing before you spend an afternoon on them. The SDK requires
**`AsyncOpenAI`**, not the synchronous client. And the provider needs the Bedrock extra
— without it you get `OpenAIError: Bedrock AWS authentication requires optional AWS
dependencies`, which is at least a clear instruction.

## Keep the trace inside AWS

This is the one line a Bedrock workload has to add, and it is worth understanding rather
than copying:

```python
set_tracing_disabled(True)
```

The SDK traces runs to OpenAI's platform by default, which is a sensible default for a
first-party workload — you get a timeline of every agent run for free. It is the wrong
default here, because these prompts and tool calls are Bedrock traffic and a team that
chose Bedrock for in-Region processing did not choose to send them elsewhere.

The default exporter posts to `https://api.openai.com/v1/traces/ingest`, and export is
gated on one thing: whether an
API key is available, from the exporter or from `OPENAI_API_KEY`. With no key the run
**succeeds** and logs a warning:

```
WARNING:openai.agents:OPENAI_API_KEY is not set, skipping trace export
```

So on a clean Bedrock-only machine nothing leaves. On a laptop that also has
`OPENAI_API_KEY` exported — routine for anyone who uses first-party OpenAI too — the
same run exports its trace with no error and no prompt. Disabling tracing makes the
behaviour independent of whatever happens to be in the environment, which is the
property you want. If you want the timeline, keep it and point the exporter somewhere
you control.

## What the framework replaced

Same five tools, same goal, same instructions as recipe 01. Three things disappeared:

**The tool schemas.** `@function_tool` derives the JSON schema from the signature and
the docstring, so the docstring is no longer documentation — it is the description the
model reads when deciding which tool to call. Write it for the model.

```python
@function_tool
def get_flight(flight_number: str) -> dict:
    """Status, route and seat availability for one flight."""
    ...
```

**The loop.** The runner calls the model, executes tool calls, feeds results back
and returns when there is a final answer with no tool work left. Those are
[the five steps OpenAI documents](https://developers.openai.com/api/docs/guides/agents/running-agents),
and they are what recipe 01 writes out by hand.

**The ceiling, as a parameter.** `max_turns=8` replaces a `while rounds < MAX_ROUNDS`,
and the runner raises `MaxTurnsExceeded` instead of falling out of the loop. The
decision is the same one; only its expression changed.

## Watching it work, and the two layers of event

`Runner.run_streamed()` returns immediately; the work happens as you consume
`stream_events()`. Two families of event arrive, and the difference between them is the
useful part:

```python
result = Runner.run_streamed(agent, GOAL, max_turns=8, auto_previous_response_id=True)

async for event in result.stream_events():
    if event.type == "run_item_stream_event":
        if event.name == "tool_called":
            call = event.item.raw_item          # .name, .arguments, .call_id
        elif event.name == "tool_output":
            output = event.item.output          # whatever your function returned
    elif event.type == "raw_response_event":
        if event.data.type == "response.output_text.delta":
            print(event.data.delta, end="")
```

**`raw_response_event` is the Responses API verbatim** — the same typed events
[`cookbooks/01-foundations/05-streaming/`](../../01-foundations/05-streaming/) walks
through, including `response.function_call_arguments.delta` if you want to watch a tool's
arguments being written a fragment at a time.

**`run_item_stream_event` is the SDK's own semantic layer**, and it is the one to build
on. It has already decided that a tool was called and what it returned, so there is no
JSON to reassemble and no bookkeeping to get wrong.

**Name the tool on the way back.** The model asks for several tools at once, so every
`tool_called` event arrives before any `tool_output`, and a trace that prints only the
results leaves you pairing them by eye:

```
   → find_alternatives(origin='LIS', destination='DUB')
   → get_entitlements(tier='gold')
   → get_entitlements(tier='silver')
   ← find_alternatives: 2 direct, 1 connecting
   ← get_entitlements: tier=gold, rebooking_priority=1, hotel_if_overnight=True
   ← get_entitlements: tier=silver, rebooking_priority=2, hotel_if_overnight=True
```

Keeping a `call_id → name` map as the calls go past costs two lines and makes the
parallelism legible, which is worth seeing: the agent is not asking one question at a
time.

## What the run cost

Two runs on 2026-08-13, `us-east-1`, `openai.gpt-5.6-terra`, same goal and same data:

| | Run 1 | Run 2 |
|:--|:--|:--|
| Model calls | 5 of 8 allowed | 7 of 8 |
| Tool calls | 8 | 10 |
| Rebooked | 2 passengers | 2 passengers |
| Tokens | 7,133 in / 2,080 out | 12,091 in / 1,885 out |

**Both columns are the same agent on the same data.** The model chooses how much to
verify before committing, so a run can cost 70% more than the one before it without
anything having changed. Budget an agent from a distribution, not from one observation —
and cap it with `max_turns`, which is the only number here you control.

What is stable is the shape: input dominates and grows every round, because each call
resends the instructions, all five tool definitions and the transcript so far. That is
the cost structure of any agent loop, hand-written or not, and it is what makes
`cookbooks/05-production/01-prompt-caching/`
worth reading next.

In both runs the agent left two passengers unbooked because the data gave it no fares and
no arrival times, and said so instead of inventing them. That part was not variance —
that is the instructions doing their job.

## Pick one continuation strategy, and know what it costs here

OpenAI documents [four ways](https://developers.openai.com/api/docs/guides/agents/running-agents)
to carry state into the next turn, and its guidance is to **pick one**: mixing local replay
with server-managed state can duplicate context. On Bedrock three of the four are available,
and the choice has a retention consequence that does not exist on the first-party API.

| Strategy | Where state lives | On Bedrock |
|:--|:--|:--|
| `result.to_input_list()` | your process | **Works.** No retention; you can edit or redact before the next turn |
| `session` | storage you control | **Works.** No retention. This is what [OpenAI's own cookbook example](https://cookbook.openai.com/examples/agents_sdk/session_memory) uses, and it adds trimming and summarization on top |
| `previous_response_id` | the service | **Works**, and requires `store=True` — so the responses are retained for 30 days |
| `conversation_id` | the service | **Not available.** There is no Conversations API on `bedrock-mantle` |

`client.conversations.create()` returns `404` on this endpoint.

This recipe takes the server-managed route, which is why it sets `store=True`. One detail
decides whether that flag does anything at all:

```python
result = await Runner.run(agent, GOAL, max_turns=8, auto_previous_response_id=True)
```

**Without `auto_previous_response_id`, `store=True` changes nothing on the wire.** The same
prompt
billed 69 then 182 input tokens with `store=False`, and 69 then 182 with `store=True` — the
runner replays the input list either way, so you would pay 30 days of retention for no
change in the request. With the flag on, each turn chains to the previous response id and
carries only the new items. And the coupling is enforced: `auto_previous_response_id=True`
with `store=False` returns `404 not_found_error: Response not found.`

The follow-up therefore sends **only the new question** and points at
`result.last_response_id`, rather than replaying `to_input_list()`. It still cost 3,831
input tokens, because the model receives the whole prior run as context regardless — server
-managed continuation saves the payload, not the bill. That measurement is in
[`cookbooks/01-foundations/04-conversation-state/`](../../01-foundations/04-conversation-state/).

If you would rather not retain anything, use `to_input_list()` or a session and set
`store=False`. Both are equally correct; what is not correct is doing both at once.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md): a Region with model
  access and inference permission on `bedrock-mantle`.
- The `agents` dependency group, which brings `openai-agents` and the `openai[bedrock]`
  extra: `uv sync --group agents`.
- Working AWS credentials — `aws sts get-caller-identity` must succeed.

**Cost:** medium. Seven model calls in total across the run and the follow-up, with
input growing each round. No per-operation tool fees. See
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

The flight, passenger and entitlement data in [`data/`](data/) is synthetic.

## Run it

```bash
uv sync --group agents
uv run python 04-agents/02-openai-agents-sdk/python/openai_agents_sdk.py
```

## Production considerations

- **Set the ceiling deliberately.** `max_turns` is your bound on cost and on damage from
  a confused agent. The runner raises when it is hit, so catch `MaxTurnsExceeded` and
  decide what a partial run means for your workload.
- **Keep your own record of the writes.** `result` gives you the model's account of what
  happened; the authoritative record is what your tools actually committed. This recipe
  keeps `REBOOKINGS` for that reason.
- **`max_retries` belongs on the client.** Token-per-minute quotas return `429`, and the
  provider's retry handles it for every call the agent makes.
- **Decide the trace destination explicitly**, rather than inheriting it from the
  environment. Disabled is the safe default on Bedrock; a self-hosted OpenTelemetry
  collector is the option if you want the timeline.
- **A tool that writes needs an authorization story of its own.** The model decides
  *whether* to call `rebook_passenger`; only your code can decide whether this caller is
  allowed to.

## Data handling and security

- **Credentials come from the AWS credential chain** via the Bedrock provider. No key is
  handled, stored or printed.
- **`store=True`** through `ModelSettings`, because this recipe uses server-managed
  continuation. AWS retains each response for 30 days, so the script deletes all of them in
  its final step — 7 of 7 on the validated run.
- **Tracing is disabled**, so no prompt or tool call is sent outside AWS.
- **Inference stays in the Region you name**, which is printed at the start.
- All passenger data is synthetic, and identifiers are invented.

## Limitations and non-goals

- One agent, no handoffs. The SDK's orchestration and specialist handoffs are a separate
  subject.
- No guardrails or approval pauses. The SDK supports both, and a write tool in
  production would want the approval flow rather than an unattended commit.
- No user interface around the stream. The events are printed as a trace; rendering
  them into something a passenger-facing agent would show is your framework's problem.
- The tools are in-process functions over a JSON file, not calls to a reservation system.
- The follow-up demonstrates server-managed continuation only. `to_input_list()` and
  sessions are named and measured against, but not exercised.

## Clean up

The recipe stores one response per model call, so it deletes them in its final step and
prints the count. Nothing else needs removing: the write tool mutates an in-memory copy of
[`data/`](data/) that is discarded when the process exits.

If the script dies part way, the responses it had already created stay until they age out
after 30 days. Re-running is safe — deleting a response that is already gone is a no-op.

## Next steps

- [[`cookbooks/04-agents/03-strands-agents-sdk/`](../../04-agents/03-strands-agents-sdk/)](../03-strands-agents-sdk/) — the same
  agent again in Strands, which reaches mantle a different way and authenticates
  differently.
- [[`cookbooks/04-agents/04-agentcore-harness/`](../../04-agents/04-agentcore-harness/)](../04-agentcore-harness/) — running an
  agent as a managed AWS deployment instead of a local process.
- `cookbooks/05-production/01-prompt-caching/`
  — the answer to the growing input cost above.

## Further reading

- [Agents SDK](https://developers.openai.com/api/docs/guides/agents) — the SDK's own
  documentation.
- [Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)
  — the loop, the turn limit and the four continuation strategies.
- [Models and providers](https://developers.openai.com/api/docs/guides/agents/models) —
  how the SDK is pointed at a model, which is the seam Bedrock plugs into.
