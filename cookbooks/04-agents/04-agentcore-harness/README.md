---
title: "Deploying an agent to AgentCore Harness"
capabilities: [AGT-03, AGT-01]
primary_capability: AGT-03
industry: TRV
industry_scenario: >
  The disruption agent works, and now it has to run somewhere: with a session per traveller,
  an iteration ceiling that holds under load, and no process of ours keeping the loop alive
  between turns.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-agentcore:CreateHarness
  - bedrock-agentcore:GetHarness
  - bedrock-agentcore:ListHarnesses
  - bedrock-agentcore:DeleteHarness
  - bedrock-agentcore:InvokeHarness
  - iam:CreateRole
  - iam:PutRolePolicy
  - iam:AttachRolePolicy
  - iam:DeleteRolePolicy
  - iam:DetachRolePolicy
  - iam:DeleteRole
  - iam:GetRole
level: advanced
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Deploying an agent to AgentCore Harness

[[`cookbooks/04-agents/01-the-agent-loop/`](../../04-agents/01-the-agent-loop/)](../01-the-agent-loop/) writes the loop by hand: call the model, read
the tool calls, execute them, send the results back, repeat, stop at a ceiling. That is thirty
lines and worth knowing.

An [AgentCore Harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-models.html)
is that loop as managed infrastructure. You declare the agent and AgentCore runs it:

```python
control.create_harness(
    harnessName=HARNESS_NAME,
    executionRoleArn=role["Arn"],
    model={"bedrockModelConfig": {
        "modelId": "openai.gpt-5.6-terra",
        "apiFormat": "responses",      # ← the OpenAI-compatible surface on mantle
        "maxTokens": 800,
    }},
    systemPrompt=[{"text": SYSTEM_PROMPT}],
    maxIterations=4,
    timeoutSeconds=120,
)
```

**`apiFormat: "responses"` is the parameter this cookbook cares about.** It is what points a
harness at a GPT-5.6 model through the Responses API on `bedrock-mantle`, rather than at
Converse. The accepted values are `converse_stream`, `responses` and `chat_completions`; for
`--model-provider bedrock` all three apply, and `responses` is the one that reaches the OpenAI
models.

| | |
|:--|:--|
| **What you will learn** | How to declare an agent instead of writing its loop, and what the execution role needs |
| **Capability** | AgentCore Harness with `apiFormat: responses` |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Advanced |
| **Cost** | Low — one harness created and deleted, one invocation |
| **You will need** | Permission to manage an AgentCore harness and an IAM role |

> **What it does.** Creates a harness pointed at a GPT-5.6 model, invokes it with a session,
> and reads the streamed reply. **What it creates.** One harness and one IAM role, both deleted
> in the final step — or set `HARNESS_ARN` to invoke one you already have.

## What you will build

```
A. the role      what the execution role needs — and it is two things, not one
B. create        one create_harness call, and what the service fills in
C. invoke        a session id, a message, and a stream of events
D. what you get  the loop, the session, truncation and streaming, unwritten
E. clean up      the harness and the role are deleted
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus permission to create and
  delete an AgentCore harness and an IAM role. Those are significant grants.

  **Set `HARNESS_ARN` to invoke an existing harness** and the recipe skips creation entirely.
- No data files.

**Cost: low.** One harness created and deleted, one invocation, a few hundred tokens.
AgentCore and model tokens are billed separately —
[rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 04-agents/04-agentcore-harness/python/agentcore_harness.py
```

Around two minutes, most of it waiting for the harness to reach `READY`.

## A. The execution role needs two grants, in opposite directions

A harness runs as its own identity, and the role needs:

**Inference — use the managed policy.** `AmazonBedrockMantleInferenceAccess` is the right
grant, and a hand-written `bedrock-mantle:CreateInference` on `*` is not enough. The managed
policy also carries `CallWithBearerToken` and the Marketplace subscribe permissions, and
`CreateInference` is authorized on a **project** ARN rather than a model ARN. A role with a
plausible-looking inference statement creates fine and then returns
`401 access_denied` at invoke time.

**Session memory — an inline policy.** A harness provisions a managed memory for session
state and then reads and writes it *as the execution role*. So the role needs the
`bedrock-agentcore` memory actions on `memory/*`:

```python
{
    "Sid": "SessionMemory",
    "Effect": "Allow",
    "Action": ["bedrock-agentcore:CreateEvent", "bedrock-agentcore:ListEvents",
               "bedrock-agentcore:GetEvent", "bedrock-agentcore:ListActors",
               "bedrock-agentcore:ListSessions",
               "bedrock-agentcore:RetrieveMemoryRecords", ...],
    "Resource": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:memory/*",
}
```

Miss this half and the harness creates successfully, reaches `READY`, and fails on invocation
with `AccessDeniedException` on `ListEvents` against a memory you never created. Worth setting
up front, because the symptom points at memory rather than at the role.

## B. What the service fills in

```
status          READY
version         1
arn             arn:aws:bedrock-agentcore:us-east-1:<account>:harness/cookbook_harness_…
allowedTools    ['*']
truncation      sliding_window
memory          provisioned
```

Three of those were defaulted for you. `allowedTools` is a filter you can narrow to specific
tool names, `truncation` is a sliding window over the conversation as it grows, and the memory
is created and attached without being asked for. The harness reached `READY` in about ten
seconds.

One operational note the recipe encodes: **a harness name stays reserved for a while after
deletion**, so a re-run with a fixed name hits
`ConflictException: An agent with the specified name already exists` even though the harness is
gone from the console. The recipe generates a unique suffix per run, which also means two
people can run it in one account without colliding.

## C. Invoking it

```python
runtime.invoke_harness(
    harnessArn=HARNESS_ARN,
    runtimeSessionId=str(uuid.uuid4()),
    messages=[{"role": "user", "content": [{"text": question}]}],
)
```

`runtimeSessionId` is required, and it is the handle for the conversation — pass the same one
again and the harness continues where it left off, using the memory it provisioned. You are
not carrying a transcript.

The response is an **event stream**:

```
event types: {'messageStart': 1, 'contentBlockDelta': 230,
              'contentBlockStop': 1, 'messageStop': 1, 'metadata': 1}
```

Worth knowing: **those are Bedrock-shaped events, not Responses-shaped ones.** The model ran
through the Responses API — that is what `apiFormat: responses` did — but the harness normalizes
its output to `messageStart` / `contentBlockDelta` / `messageStop`. So a client written against
one harness works against another regardless of which API format the model behind it uses,
and it is not the typed `response.output_text.delta` stream that
[`cookbooks/01-foundations/05-streaming/`](../../01-foundations/05-streaming/) shows.

## D. What you did not write

| The harness provides | You would otherwise write |
| --- | --- |
| The loop, bounded by `maxIterations` | The `while` loop and its ceiling |
| Session continuity via `runtimeSessionId` | Transcript storage and replay |
| `truncation` as a sliding window | Deciding what to drop as context grows |
| A streamed response | Stream handling, or a blocking call |
| Tool wiring by declaration | Tool dispatch, `call_id` pairing, error plumbing |

Tools are declared the same way the model is, with a `type` of `agentcore_gateway`,
`remote_mcp`, `agentcore_code_interpreter`, `agentcore_browser` or `inline_function`. Note the
last one is a *client-executed* declaration — the harness surfaces the call and your caller
runs it — so a fully server-side tool needs a gateway or an MCP server, which is the same
distinction as [`cookbooks/02-reasoning-and-output/05-server-side-tools/`](../../02-reasoning-and-output/05-server-side-tools/).

What stays yours: the model and its API format, the system prompt, the iteration ceiling, the
timeout, and which tools the agent may use.

![Two panels. Custom built: your process holds the while loop bounded by MAX_ROUNDS, the transcript and the tool implementations — you own the loop. Using AgentCore Harness: your caller is one invoke_harness call with a harness ARN, a session id and messages, while AgentCore Runtime holds the loop with maxIterations 4, timeoutSeconds 120, sliding_window truncation and provisioned memory, running under its own execution role carrying AmazonBedrockMantleInferenceAccess plus memory actions. The response streams messageStart, contentBlockDelta and messageStop events. One arrow crosses back: an inline_function call the harness surfaces for your caller to run.](images/boundary-moved.drawio.svg)

*The comparison is with [[`cookbooks/04-agents/01-the-agent-loop/`](../../04-agents/01-the-agent-loop/)](../01-the-agent-loop/), where
the same loop runs in your process. What moved is the loop and the transcript; what came back is
`inline_function`, the one declaration that still executes on your side.*

## Production considerations

- **`maxIterations` is the safety and cost control**, exactly as the hand-written ceiling was.
  It just lives in the declaration now.
- **Version the harness.** `create_harness` returns a version, and updating produces a new one.
  Pin the version an endpoint serves rather than tracking latest.
- **Give each conversation its own `runtimeSessionId`**, and treat it as an identifier tied to a
  user — the session's memory holds what was said.
- **Narrow `allowedTools`.** It defaults to `['*']`. Naming the tools the agent may call is the
  cheap way to bound a deployed agent's reach.
- **The execution role is the agent's identity.** Anything the agent can reach, the role can
  reach. Scope it per agent rather than sharing one role across several.
- **Deleting the harness deletes the memory it provisioned**, so the session history goes with
  it. If that history has a retention requirement, manage the memory explicitly instead of
  letting the harness provision one.
- **A hand-rolled loop is still the better place to learn and debug.** When a deployed agent
  behaves oddly, reproducing it against the raw Responses API is how you find out whether the
  model or the harness is responsible.

## Data handling and security

- **No credential is handled by the recipe.** boto3 reads the AWS credential chain; the harness
  runs under the execution role it is given.
- **Account identifiers are masked** from every printed ARN.
- **The harness stores conversation state** in the managed memory it provisions, which is a
  retention question the hand-rolled loop did not have. The recipe deletes it with the harness.
- **No public exposure.** The harness has no inbound endpoint in this recipe; it is invoked
  through the AgentCore data-plane API with SigV4.
- **The scenario is fabricated**, and the question sent contains no personal data.

## Limitations and non-goals

- **No tools.** The harness here has none, so the comparison with the hand-rolled loop is about
  the deployment rather than about tool execution. Wiring a gateway is the natural next step.
- **No endpoint.** `CreateHarnessEndpoint` exists and is not used; invocation goes straight to
  the data-plane API.
- **No memory configuration.** The provisioned default is accepted rather than configured.
- **One invocation, one session.** Session continuity is described but not demonstrated across
  turns.
- **No VPC configuration**, no inbound authorizer, no observability wiring.
- **No comparison against a framework SDK.** Pointing the OpenAI Agents SDK or Strands at
  Bedrock is a separate capability from deploying a harness.

## Clean up

The recipe deletes the harness and the execution role in its final step, and the managed memory
goes with the harness. The role name is fixed and cookbook-specific, so the recipe removes it
even if an earlier interrupted run created it.

If a run dies part way:

```bash
aws bedrock-agentcore-control list-harnesses
aws bedrock-agentcore-control delete-harness --harness-id <id>
aws iam delete-role-policy --role-name cookbook-disruption-harness-role \
  --policy-name harness-session-memory
aws iam detach-role-policy --role-name cookbook-disruption-harness-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockMantleInferenceAccess
aws iam delete-role --role-name cookbook-disruption-harness-role
```

If you supplied `HARNESS_ARN`, nothing is deleted.

## Next steps

- [[`cookbooks/04-agents/01-the-agent-loop/`](../../04-agents/01-the-agent-loop/)](../01-the-agent-loop/) — the loop this replaces, which is still
  where you debug agent behaviour.
- [`cookbooks/02-reasoning-and-output/05-server-side-tools/`](../../02-reasoning-and-output/05-server-side-tools/)
  — tools Bedrock executes for you, the other half of a fully managed agent.
