---
title: "Server-side tools: Bedrock as the MCP client"
capabilities: [STR-06]
primary_capability: STR-06
industry: TRV
industry_scenario: >
  A hotel group's room inventory sits in a private subnet and is not reachable from the
  internet. The reservations desk wants a model to answer availability questions against it
  without exposing the system, and without a long-running client process holding the tool
  loop open.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - iam:CreateRole
  - iam:AttachRolePolicy
  - iam:DetachRolePolicy
  - iam:DeleteRole
  - iam:GetRole
  - lambda:CreateFunction
  - lambda:GetFunction
  - lambda:DeleteFunction
level: advanced
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Server-side tools: Bedrock as the MCP client

In the [client-side pattern](../03-tool-calling/), your code owns the loop: you receive a
`function_call`, execute it, send the result back, and repeat. Your process has to stay alive
for the whole exchange, and every tool call is a network round trip through it.

[Server-side tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-server-side.html)
inverts that. You declare an **MCP connector** and Bedrock runs the loop itself: it discovers
the tools, decides which to call, invokes them, reads the results, and returns a finished
answer. There is no loop in your code at all.

| | |
|:--|:--|
| **What you will learn** | How to hand Bedrock a tool server it runs for you, and why that lets a tool reach a private system |
| **Capability** | Server-side tool use via an MCP connector |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Advanced |
| **Cost** | Low — one model call, two Lambda invocations |
| **You will need** | Permission to create and delete a Lambda function and an IAM role |

> **What it does.** Deploys a Lambda that speaks MCP, declares it as a connector, and makes a
> single request that Bedrock resolves by calling the tool itself. **What it creates.** One
> Lambda function and one IAM role, both deleted in the final step.

```python
tools = [{
    "type": "mcp",
    "server_label": "marisol_inventory",
    "connector_id": FUNCTION_ARN,        # a Lambda, or an AgentCore Gateway
    "server_description": "Room inventory for Marisol Hotels",
    "require_approval": "never",         # the only accepted value
}]
```

## Why this shape is interesting, and it is not about saving code

The architectural reason is the network boundary. **The Lambda can sit in a VPC and reach a
private system that Bedrock has no route to** — a database in a private subnet, an on-premises
service over a VPN — without granting Bedrock any network access at all. The tool runs inside
your perimeter and only its results cross the boundary.

![Server-side tool use. Your process makes one request and then waits. Inside the AWS Region, the bedrock-mantle endpoint runs the loop itself — discover, decide, invoke, feed back — calling a Lambda function that speaks MCP with tools/list and tools/call, declared by connector_id as the function ARN with require_approval set to never. The function must carry the same role as the caller, because no credentials are passed, and it reaches a private VPC resource that is described rather than deployed by the recipe. One response comes back, carrying mcp_list_tools and mcp_call items.](images/server-side-loop.drawio.svg)

*One request out, one response back. The loop runs inside the Region, and the tool — not Bedrock
— is what reaches the private system.*

The two patterns answer the same seven questions differently, and none of the answers is about
how much code you write:

| | Client-side, [`03-tool-calling/`](../03-tool-calling/) | Server-side, this recipe |
|:--|:--|:--|
| **Who holds the loop** | Your code | Bedrock |
| **Your process during the exchange** | Stays alive for the whole thing | Makes one `create()` call and waits |
| **Network round trips** | One per tool call, through your process | One, for the whole exchange |
| **What the tool runs as** | Whatever your process holds | The identity that invoked the model. No credentials are passed |
| **What you deploy** | Nothing | A Lambda or an AgentCore Gateway, plus a role |
| **Intervening mid-loop** | Yours to decide, because you hold the decision | Not available — `require_approval` accepts only `"never"` |
| **Seeing what happened** | You ran it, so you saw it | `mcp_list_tools` and `mcp_call` items on the response |
| **Reaching a private system** | Your process needs a route to it | The tool does, and Bedrock never needs one |

Two rows deserve the reasoning behind them:

- **No credentials are passed to the tool.** Bedrock reuses the identity of whoever invoked
  the model. That is the trap as well as the feature: **the function's role must carry the
  same permissions as the application invoking the model**, or execution fails.
- **The steps stay observable.** The response carries `mcp_list_tools` and `mcp_call` items,
  so you can see what was discovered and what was invoked even though you did not run it —
  which is the observability you would otherwise have built yourself.

And one row is a reason to stay client-side: if a tool needs a human to approve it before it
acts, this path cannot offer that.

## What you will build

```
A. the tool server  a Lambda speaking JSON-RPC: initialize, tools/list, tools/call
B. deploy           role and function created by the recipe
C. one request      no loop, no function_call handling — one create() call
D. observe          mcp_list_tools and mcp_call items on the response
E. clean up         the function and its role are deleted
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus permission to create
  and delete a Lambda function and an IAM role. Those are significant grants.

  **If you cannot create them, set `MCP_CONNECTOR_ARN`** to an existing connector — a Lambda
  ARN or an AgentCore Gateway ARN — and the recipe skips deployment and leaves your resource
  alone.
- No data files. The inventory lives in the Lambda source, standing in for the private system
  it exists to reach.

**Cost: low.** One model call (402 input, 117 output tokens as measured), two Lambda
invocations, and no per-call tool fee — tool definitions and results are billed as tokens,
exactly as a client-side tool is.
[Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 02-reasoning-and-output/05-server-side-tools/python/server_side_tools.py
```

## The tool server is an MCP server, not a Lambda handler with a switch

[`python/mcp_tool_lambda.py`](python/mcp_tool_lambda.py) implements three JSON-RPC 2.0
methods:

| Method | Purpose |
| --- | --- |
| `initialize` | Announce the protocol version and capabilities |
| `tools/list` | How Bedrock discovers what is callable, with JSON Schema per tool |
| `tools/call` | Run one tool and return MCP content parts |

Two details that are easy to get wrong:

- **A tool result is wrapped in `content` parts**, not returned bare:
  `{"content": [{"type": "text", "text": "..."}], "isError": false}`.
- **Bad arguments are a result, not an exception.** The handler returns
  `isError: true` with a message, so the model can correct itself on the next turn — the same
  principle as the client-side recipe, and it matters more here because you are not in the
  loop to catch anything.

## What comes back

One `create()` call, and the whole tool exchange has already happened:

```
output item types: ['mcp_list_tools', 'reasoning', 'mcp_call', 'message']

mcp_list_tools   discovered: ['search_rooms', 'get_room']
mcp_call         search_rooms({"property_name":"Marisol Lisboa","accessible_only":true})
                 → {"content":[{"type":"text","text":"{\"property\": \"Marisol Lisboa\", …

the answer:
  Tonight at Marisol Lisboa, there is 1 accessible twin available:
  - Room code: MRS-LIS-02
  - Rate: EUR 210 per night
  A Porto fallback is not needed, as a suitable accessible room is available in Lisbon.

402 in / 117 out
```

Three things to read there.

**`mcp_list_tools` is the discovery step**, and it happened without you asking: Bedrock called
`tools/list` on the function, got both tools with their schemas, and decided which it needed.
You declared an ARN, not a tool catalogue.

**`mcp_call` keeps the invocation visible.** The arguments the model chose and the raw result
the function returned are both on the response, so a server-side loop is not a black box — it
is the same observability you would have built yourself, without building it.

**The question had two parts and the model only needed one call.** It was asked for a Lisbon
room *and* a Porto fallback; finding a suitable accessible room in Lisbon, it stopped and said
the fallback was unnecessary. Bedrock ran as many calls as the answer needed and no more.

## `connector_id` takes a Lambda or a Gateway

The [AWS documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-server-side.html)
documents the parameter with an **AgentCore Gateway** ARN, which centralizes tool management
across several agents and supports IAM-authenticated gateways. A **Lambda** ARN also works and
is what this recipe uses, because a function is far cheaper to create and delete than a
gateway for a demonstration.

Which to choose in production: a Lambda when the tool is specific to one workload, a Gateway
when several agents share a tool catalogue and you want one place to manage it.

## Production considerations

- **Match the function's role to the caller's permissions.** This is the documented trap. The
  function executes under the invoking identity, so a mismatch fails at call time rather than
  at deploy time.
- **Put the function in the VPC that can reach your system**, and keep it off the public
  internet. It needs no function URL: Bedrock invokes it through the connector.
- **The tool definitions cost input tokens on every request that carries the connector**, just
  as client-side definitions do. A large tool catalogue is a real cost at volume, which is one
  argument for a Gateway with a curated set.
- **You cannot intervene mid-loop.** `require_approval` accepts only `"never"`, so there is no
  human-in-the-loop checkpoint on this path. If a tool needs approval before it acts, it
  belongs in a client-side loop where you hold the decision.
- **Cold starts are part of the answer's latency**, and they are inside a call you no longer
  control. Provisioned concurrency is the lever if that matters.
- **Log inside the function.** Since you are not in the loop, the function's own CloudWatch
  logs plus the `mcp_call` items on the response are your only view of what happened.
- **Timeouts compound.** A slow tool extends the model call; set the function timeout below
  your client timeout so the failure surfaces as a tool error rather than a dead request.

## Data handling and security

- **No credential is handled by the recipe**, and none is passed to the function. The Bedrock
  provider and boto3 read the AWS credential chain; Bedrock reuses the caller's identity when
  invoking the tool.
- **`store=False` on the model call**, so AWS retains neither the request nor the answer.
- **Nothing is exposed publicly.** No function URL, no API Gateway, no public bucket. The
  function is reachable only through the connector.
- **Account identifiers are masked** from printed ARNs.
- **Tool results enter the model's context**, so what the function returns is what leaves your
  perimeter. Return the fields the answer needs, not whole records.
- **The properties, rooms and rates are fabricated.**

## Limitations and non-goals

- **No VPC attachment.** The recipe's function is not in a VPC, because creating subnets and
  security groups is a change with account-wide consequences. The VPC case is the *reason* for
  the pattern and is described rather than deployed.
- **No AgentCore Gateway.** Only the Lambda connector is used.
- **The inventory is in the function source**, not a database. A real tool server holds a
  connection to something.
- **No approval flow**, because the API does not offer one on this path.
- **One tool call pattern.** Multi-step server-side loops and streaming
  (`response.output_text.delta` alongside `mcp_call` items) are not shown.
- **The CloudWatch log group outlives the function.** The recipe says so rather than deleting
  logs you may want to read.

## Clean up

The recipe deletes the Lambda function and the IAM role it created, in its final step. The
CloudWatch log group `/aws/lambda/cookbook-mcp-inventory-tools` survives deliberately, so the
invocation logs are still readable — delete it yourself if you want nothing left.

If a run dies part way, remove them with:

```bash
aws lambda delete-function --function-name cookbook-mcp-inventory-tools
aws iam detach-role-policy --role-name cookbook-mcp-inventory-tools-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name cookbook-mcp-inventory-tools-role
```

If you supplied `MCP_CONNECTOR_ARN`, nothing is deleted.

## Next steps

- [`cookbooks/02-reasoning-and-output/03-tool-calling/`](../03-tool-calling/) — the client-side loop this replaces, and where
  approval and mid-loop control still live.
- [`cookbooks/04-agents/01-the-agent-loop/`](../../04-agents/01-the-agent-loop/) — an agent that
  owns its loop, and the write-tool decisions that come with it.
