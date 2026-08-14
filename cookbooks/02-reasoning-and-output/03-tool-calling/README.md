---
title: "Tool calling: the flat schema, and the loop around it"
capabilities: [STR-02, STR-03]
primary_capability: STR-02
industry: MFG
industry_scenario: >
  A field service engineer at an industrial press manufacturer is on site with a failed
  component. The answers they need — stock, lead time, price, whether the machine is still
  under contract — live in systems the model cannot reach, and a wrong figure quoted to the
  customer is a commercial commitment.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: intermediate
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Tool calling: the flat schema, and the loop around it

A model that cannot reach your systems can still use them, if you let it ask. You declare
what is callable, the model returns a request to call one, your code runs it, and you send
the result back. That exchange is the whole of tool calling — and on the Responses API it
has a specific shape that differs from Chat Completions in exactly the way most likely to
trip up ported code.

| | |
|:--|:--|
| **What you will learn** | The flat Responses tool schema, the `call_id` round trip, parallel calls, and `tool_choice` |
| **Capability** | Client-side tool calling on the Responses API |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Low — around twelve calls, small inputs |
| **You will need** | Inference permission only |

> **What it does.** Declares three tools over a parts and contracts register, then works a
> field engineer's question to a real answer across several rounds. **What it creates.**
> Nothing — the tools read a committed JSON file, and `store=False` throughout.

## The schema is flat

This is the single most common porting error, so it is worth seeing side by side. Chat
Completions nests the definition under a `function` key:

```python
# Chat Completions — NOT the shape used here
{"type": "function", "function": {"name": "get_part", "parameters": {...}}}
```

The Responses API puts everything at the top level of the entry:

```python
{
    "type": "function",
    "name": "get_part_availability",
    "description": "Stock, lead time, location and price for a part number.",
    "parameters": {
        "type": "object",
        "properties": {"part_number": {"type": "string"}},
        "required": ["part_number"],
    },
}
```

The nested form is rejected with `400 validation_error: invalid request body: Invalid
'tools'`, so a ported call fails immediately rather than running without its tools.

## What you will build

```
A. declare       three tools over a parts and contracts system
B. one round     function_call out, function_call_output back, then the answer
C. in parallel   one question, two lookups, issued together
D. tool_choice   auto, none, required, and naming a specific tool
E. the loop       keep going until the model stops asking, with a ceiling
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`. No extra permissions, no AWS resources.
- Synthetic data in [`data/service_records.json`](data/service_records.json) — a fabricated
  parts catalogue and machine register for a fictional manufacturer. The tools read that
  file; in production they would be your API calls, and nothing else about the shape
  changes.

**Cost: low.** Around twelve calls with small inputs and output capped at 900 tokens. The
measured four-round loop cost 1,832 input and 272 output tokens in total — a tool loop's
input grows each round because the transcript accumulates, which the final phase measures.

## Run it

```bash
uv sync
uv run python 02-reasoning-and-output/03-tool-calling/python/tool_calling.py
```

## The protocol, in four lines

A response that wants a tool carries one or more `function_call` items instead of a message:

```python
for item in response.output:
    if item.type == "function_call":
        result = TOOL_FUNCTIONS[item.name](**json.loads(item.arguments))
```

Each carries a `call_id`, and the result must quote it:

```python
{"type": "function_call_output", "call_id": item.call_id, "output": json.dumps(result)}
```

That pairing is the only bookkeeping in the protocol. Two details matter more than they
look:

- **Carry `response.output` forward unmodified**, then append the results. On a reasoning
  model the output includes a reasoning item, and dropping or rewriting it degrades
  multi-turn tool use.
- **`output` is a string.** JSON-encode structured results; the model reads them as text.

## What a run looks like

The engineer's first question needs two different systems, and the model asked both at once:

```
output item types: ['reasoning', 'function_call', 'function_call']
  find_part          args={"description":"rod seal","machine_model":"VL-880S"}
  get_machine_cover  args={"serial_number":"VLC-880-01192"}
```

Then one more round to price the candidate it preferred, then the answer:

```
round 2  1 tool call(s)  502 in / 73 out
  → get_part_availability(part_number='VL-4472-SEAL')
round 3  0 tool call(s)  639 in / 119 out
  Yes. Fit VL-4472-SEAL — 45 mm uprated fluoroelastomer rod seal
  - Available today: 6 on hand at Central Spares, Rotherham; 0-day lead time
  - Price: £73.25 each
  - Cover: the original warranty expired 2024-04-02, but the Comprehensive
    service contract runs to 2027-03-31 and covers parts
```

Worth noticing what it did there: `VL-4471-SEAL` is the exact original part and has **zero
stock with an 11-day lead time**, while `VL-4472-SEAL` is the uprated equivalent with six on
the shelf. Asked whether the engineer could fix it *today*, it priced the one that is
actually available and justified the substitution — a judgement that needed both tool
results together.

### Errors as data let the model recover

The last phase asks about a different press, and the first attempt went wrong in a useful
way:

```
round 1  find_part(description='rod seal', machine_model='VLC-880')  → {"matches": []}
         get_machine_cover(serial_number='VLC-880-00031')            → model "VL-880"
round 2  find_part(description='rod seal', machine_model='VL-880')   → found
round 3  get_part_availability(part_number='VL-4471-SEAL')
round 4  the answer: £48.50, 11-day lead, customer pays — warranty
         expired 2019-07-21 and there is no service contract
```

It searched with the **serial number** where a model code was wanted, got an empty list back,
read the real model from the other tool's result, and retried correctly. That only works
because `find_part` returns `{"matches": []}` instead of raising: **a tool that returns its
problem as data gives the model something to recover from, while an exception ends the run.**

Input grew 238 → 405 → 538 → 651 across those four rounds for 272 output tokens in total.

## `tool_choice` decides who chooses

| Value | Effect |
| --- | --- |
| `"auto"` | The default. The model calls a tool when it judges one is needed |
| `"none"` | Tools stay declared but unusable; the model answers from context |
| `"required"` | The model must call something, even for a general question |
| `{"type": "function", "name": "get_machine_cover"}` | Pins the first call to one tool |

Naming a tool is how you keep a workflow on rails when you already know what has to happen
first — a support flow that must always check entitlement before quoting, for example. It
constrains the first call, not the whole conversation.

## Parallel calls are the default, not a feature to enable

When a question needs two independent lookups, they arrive as two `function_call` items in
a single response. Your code can execute them concurrently and return every result in one
request, which is one network round trip instead of two.

The corollary is that your tool functions should be safe to run concurrently. Reads
usually are. Writes usually are not, and the way to keep control is to describe a write
tool as one-at-a-time in its own description rather than hoping.

## Production considerations

- **Bound the loop.** A ceiling on rounds is not optional; without one, a confused model
  and a flaky tool can bill indefinitely. Treat hitting the ceiling as an alert.
- **The cost model is the transcript, not the call count.** Every round resends the whole
  conversation including previous calls and results, so input tokens grow superlinearly
  across a long loop. A stable instruction prefix is worth caching.
- **Return errors as data, not exceptions.** A tool that returns
  `{"error": "no such part number"}` lets the model correct itself; a raised exception ends
  the run. The functions here do the former deliberately.
- **Validate arguments before executing.** `arguments` is model-generated JSON. Treat it as
  untrusted input, especially for anything that writes, deletes or spends.
- **Describe tools for a reader who cannot see your code.** The description is the entire
  basis for the model's choice; "use when the engineer has no part number" changes
  behaviour more than any parameter.
- **Keep the tool count honest.** Every declared tool costs input tokens on every request.
  Three tools is free; fifty is a design decision.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS credential
  chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **Tool results enter the model's context.** Whatever your tool returns is sent to the
  model on the next request, so a tool that reads customer records is a data-flow decision,
  not just an integration. Return the fields the model needs and no more.
- **The parts catalogue, machines, sites and prices are fabricated.**

## Limitations and non-goals

- **No agency.** This recipe answers questions; it does not pursue a goal across many
  steps. That is `cookbooks/04-agents/01-the-agent-loop/`.
- **No write tools.** Every tool here reads. Letting a model change state is a different
  risk conversation.
- **No concurrency.** Parallel calls are shown arriving together and then executed in
  sequence, because the tools are local dictionary lookups.
- **No streaming.** Tool calls surface as typed events in a stream, which a live UI wants
  and a script does not.
- **No retry or timeout handling around the tools themselves**, which a real integration
  needs on every call it makes.

## Clean up

Nothing to tear down. On-demand inference creates no resources, and `store=False` means
there is no stored response to delete.

## Next steps

- `cookbooks/04-agents/01-the-agent-loop/` — the same
  protocol given a goal instead of a question, with a write tool and a ceiling.
- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../01-structured-claims-intake/) — schemas for the
  answer, as opposed to schemas for the request.
