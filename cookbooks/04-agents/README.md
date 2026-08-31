# Agents

> **How do I let a model pursue a goal, and then run that somewhere?**

An agent is a tool loop with a goal instead of a question: the model decides how many steps to
take, in what order, and when it is finished. All four recipes here take **one scenario** — an
airline rebooking passengers off a cancelled flight — and work through it four ways, so that
what changes between them is the machinery and never the problem.

Read them in order. The hand-rolled loop is short, and knowing it is what lets you debug
everything after it.

## The four shapes

- **Your loop.** You call the model, read the tool calls, execute them, send the results back,
  and stop at a ceiling you set. Nobody ships this, and writing it once is what makes the rest
  legible.
- **The OpenAI Agents SDK.** The loop, the tool schemas and the turn limit come from the
  framework. On Bedrock the integration point is the client: build one with the Bedrock
  provider and hand it over. It signs with SigV4.
- **Strands.** The AWS-native SDK, with a first-class config for the Bedrock endpoint. It
  reaches mantle by minting a short-term bearer token, which is a different credential path
  with a different IAM action behind it.
- **A harness.** You declare the model, the system prompt, the tools and the limits, and
  AgentCore runs the loop, keeps the session, applies a truncation strategy and streams the
  result.

What stays yours in all four cases: the iteration ceiling, the policy on tools that write, and
the trace you keep for an audit.

Those four paragraphs say what each shape *is*. The mechanical answers — which are what you need
when you are choosing one — sit side by side here:

| | Your loop | OpenAI Agents SDK | Strands | A harness |
|:--|:--|:--|:--|:--|
| **Recipe** | [`01-the-agent-loop/`](01-the-agent-loop/) | [`02-openai-agents-sdk/`](02-openai-agents-sdk/) | [`03-strands-agents-sdk/`](03-strands-agents-sdk/) | [`04-agentcore-harness/`](04-agentcore-harness/) |
| **Validated with** | `openai 2.53.0` | `openai-agents 0.20.0` | `strands-agents 1.52.0` | `openai 2.53.0` |
| **How you point it at Bedrock** | `OpenAI(provider=bedrock(region=REGION))` | An `AsyncOpenAI` built with the same provider, handed to the model | `bedrock_mantle_config={"region": REGION}` | `apiFormat: "responses"` in the harness declaration |
| **The import that matters** | — | `from agents import Agent, OpenAIResponsesModel, Runner, function_tool` | `from strands.models.openai_responses import OpenAIResponsesModel` | — |
| **Credential** | SigV4 from the credential chain | SigV4, because it is the same provider | A short-term bearer token it mints for you | The harness's own execution role |
| **Extra IAM action** | — | — | `bedrock-mantle:CallWithBearerToken` | `bedrock-agentcore:*` and `iam:*` to create the role |
| **Extra dependency** | — | `agents` group | `agents` group | — |
| **Who runs the loop** | You | The `Runner` | The `Agent` | AgentCore |
| **Third-party telemetry** | None | **Traces to `api.openai.com` by default** — see the recipe | None | None |

Two rows are worth reading twice. **Strands takes a different credential path**, so it needs an
IAM action the other three do not — that is a policy conversation, not a preference. And the
Agents SDK **exports traces outside AWS unless you stop it**, which matters because a trace
carries prompts and tool calls; the recipe shows the one line that closes it.

One thing the two SDK recipes will not give you is a benchmark. The same scenario rebooked 2, 3
and 4 passengers across three runs, because the model decides how much checking to do — that
variance is much larger than anything the frameworks contribute, so the token totals are not
comparable.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-the-agent-loop/`](01-the-agent-loop/) | The agent loop: a goal, some tools, and a round ceiling | advanced | medium |
| [`02-openai-agents-sdk/`](02-openai-agents-sdk/) | Running an agent on Bedrock with the OpenAI Agents SDK | intermediate | medium |
| [`03-strands-agents-sdk/`](03-strands-agents-sdk/) | Running an agent on Bedrock with Strands | intermediate | medium |
| [`04-agentcore-harness/`](04-agentcore-harness/) | Deploying an agent to AgentCore Harness | advanced | low |
<!-- END GENERATED: group-index -->

## Running these

```bash
uv sync
uv run python 04-agents/01-the-agent-loop/python/the_agent_loop.py
```

The first three are inference only; the two SDK recipes need `uv sync --group agents` first.
The fourth creates an AgentCore harness and an IAM role and deletes both, so it needs
permission to manage them.

## Where to go next

- [`cookbooks/02-reasoning-and-output/03-tool-calling/`](../02-reasoning-and-output/03-tool-calling/)
  — the protocol underneath the loop, including `tool_choice` and parallel calls.
- [`cookbooks/02-reasoning-and-output/04-reasoning-across-turns/`](../02-reasoning-and-output/04-reasoning-across-turns/)
  — the parameter that decides how much of the agent's earlier thinking is replayed each round.
- [`cookbooks/05-production/01-prompt-caching/`](../05-production/01-prompt-caching/) — how to
  stop paying full price for the instruction prefix on every round.
