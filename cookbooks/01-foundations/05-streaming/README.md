---
title: Streaming, and what the typed events tell you
capabilities: [FND-03]
primary_capability: FND-03
industry: —
industry_scenario: >
  Cross-industry. Any interface a person waits in front of — a support console, an
  internal assistant, a document drafting tool — where the answer takes seconds and
  a blank screen reads as a failure.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: beginner
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Streaming, and what the typed events tell you

A multi-second answer feels broken when the screen is blank and perfectly fine when words
are appearing. Streaming is how you get the second experience, and on the Responses API it
gives you rather more than a faster-feeling answer: the stream is a sequence of **typed
events**, which is what lets a UI show a model thinking, calling a tool, or citing a source
as it happens.

| | |
|:--|:--|
| **What you will learn** | How to stream a response, what each event type means, and what you can and cannot show a reader while the model works |
| **Capability** | Streaming on the Responses API |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — three calls, the largest capped at 600 output tokens |
| **You will need** | Inference permission only |

> **What it does.** Sends one prompt without streaming and again with it, then streams a
> turn the model has to reason about, printing every event type in arrival order.
> **What it creates.** Nothing — `store=False` on all three calls.

## Why stream

| | First visible output | Complete |
| --- | --- | --- |
| Unstreamed | when the whole answer is finished | the same moment |
| Streamed | as soon as the first few tokens exist | later |

Streaming does not make the model work any faster. It changes **when the reader sees the
first word**, and the script sends the same prompt both ways so you watch that gap open on
your own account rather than taking a figure from this page.

What you get in exchange for that is a small amount of extra structure. The
Responses API does not stream a string — it streams **typed events**, and you match
on `event.type` rather than reading a chunk:

```python
with client.responses.stream(model=MODEL_ID, input=PROMPT, store=False) as stream:
    for event in stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
```

That `if` is not boilerplate you could drop. Most events in a stream carry no user
text at all, and one of them is how you know the model is thinking.

## What you will build

One script, three calls, five short sections:

```
A. without streaming   the same prompt, and how long the screen stays empty
B. with streaming      the context manager, the one event that carries text,
                       and where usage appears
C. the event types     all nine, in the order they first arrived
D. a reasoning turn    what a reasoning item looks like going past, and what
                       encrypted_content actually contains
E. what to take        the three runs compared, in plain sentences
```

A and B exist as a pair, and the numbers they print are **yours**: a timing measured on one
account is not a fact about the platform, so the script labels them as that run's rather
than publishing them here.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md): a Region with model
  access, and IAM permissions for inference on `bedrock-mantle`.
- Working AWS credentials — `aws sts get-caller-identity` must succeed.
- No extra dependencies.

**Cost:** low. Three calls, the largest capped at 600 output tokens. See
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 01-foundations/05-streaming/python/streaming.py
```

## The nine events, and the item types inside them

A streamed response is a nested structure being opened and closed, and the script prints the
types in arrival order because the order is the lesson:

```
   1 x  response.created
   1 x  response.in_progress
   1 x  response.output_item.added        <- an item begins
   1 x  response.content_part.added       <- a content part inside it begins
 212 x  response.output_text.delta        <- the only events carrying text
   1 x  response.output_text.done
   1 x  response.content_part.done
   1 x  response.output_item.done
   1 x  response.completed                <- carries the final response, with usage
```

**The reasoning turn added no new event types.** Both runs emitted the same nine. What changed
is the item *inside* `response.output_item.added`:

```
plain answer     item types ['message']
with reasoning   item types ['reasoning', 'message']
```

That is the most useful thing to know before building a UI on this: you do not watch for
reasoning-specific events. You watch `response.output_item.added` and read `event.item.type` —
which is the same place a `function_call` or a `web_search_call` turns up on a turn that uses
tools. One handler covers all of them.

Three more things worth taking from that shape.

**The text is one layer deep, not at the top.** A response holds items, an item holds content
parts, a content part holds text, and `response.output_text.delta` is the leaf. Four levels open
in order and close in reverse, so the nine events above are really four pairs of brackets with
the text deltas inside the innermost one:

| Level | Opens at | Closes at | What that level carries |
| --- | --- | --- | --- |
| 1 — the response | `response.created`, then `response.in_progress` | `response.completed` | The final response object, and the only copy of `usage` |
| 2 — the output item | `response.output_item.added` | `response.output_item.done` | `item.type`, which is `message`, `reasoning`, `function_call` or `web_search_call` |
| 3 — the content part | `response.content_part.added` | `response.content_part.done` | The part that citations later attach to |
| 4 — the text | `response.output_text.delta`, many times | `response.output_text.done` | The only user-visible text anywhere in the stream |

Reading it as brackets is what makes the rest of the API predictable. When you later add Web
Search, annotations arrive as their own events on level 3, because that is the level they belong
to — you can work out where a new event type will appear without being told.

**`response.completed` is where the response object lands.** The SDK also accumulates it for
you: `stream.get_final_response()` after the loop returns an object identical in shape to what
a non-streamed call gives you, so the measurement code at the end of this recipe is the same
either way.

**`stream=True` on `responses.create` yields the same events** without the context manager.
Prefer the context manager: it closes the HTTP connection when the loop raises, which a bare
iterator does not.

### The events this recipe does not produce

Nine event types is what a plain text answer emits. A turn that uses tools emits more,
and they arrive on the same nested structure — which is the reason the API streams typed
events rather than a string:

| Event | When it appears |
| --- | --- |
| `response.function_call_arguments.delta` / `.done` | a **client-side** tool call, with the JSON arguments arriving in fragments |
| `response.output_item.added` with `item.type == "function_call"` | the model has decided to call your function |
| `response.output_item.added` with `item.type == "web_search_call"` | a **server-side** tool step Bedrock is running for you |
| `response.output_text.annotation.added` | a citation attaching to the text as it is written |

Two consequences worth knowing before you build a UI on this.

**Streamed tool arguments are fragments, not JSON.** You cannot `json.loads` a
`function_call_arguments.delta`; accumulate them and parse once at `.done`, or take the
whole item from `stream.get_final_response()`. Rendering a "calling get_weather…"
state is a good use of the `added` event; parsing partial arguments is not.

**Server-side tools stream their steps too.** With Bedrock's
Web Search, retrieval happens inside the turn without any client-side loop, so the
`web_search_call` items arriving mid-stream are your only live view of what it is
doing. The same is true of an MCP connector executed by Bedrock. If you buffer until
`response.completed`, you get the same data — you just get it after the wait rather
than during it, which defeats the purpose on a turn that takes 30 seconds.

This recipe deliberately stays on the plain-text case so the nine events are legible.
The tool events belong with the recipes whose subject is tools.

## Reasoning is visible in the stream, and unreadable

With `reasoning={"effort": "high"}` and an arithmetic prompt, the stream shows this
(2026-08-11, `us-east-1`):

```
    1.86s  a reasoning item opened
    1.86s  a message item opened
12:12

← response
   answer             12:12
   reasoning tokens   137, billed as output and drawn from max_output_tokens
   encrypted_content  1028 characters of ciphertext, not prose
                      It was complete at 1.86s, on the event that opened the item
```

Nothing arrives while the model is thinking. Then the reasoning item opens and closes with
no text between, and the message item follows. So:

- **You can tell a reader that the model is thinking.** Watch for
  `response.output_item.added` where `event.item.type == "reasoning"`, and render a
  "thinking" state. That is what the pause is.
- **You cannot show them what it thought.** Asking for the trace with
  `include=["reasoning.encrypted_content"]` returns roughly a kilobyte of opaque
  ciphertext, not prose. It is meant to be passed back on a later turn, which is what
  `cookbooks/02-reasoning-and-output/04-reasoning-across-turns/`
  does with it. If your product needs a visible rationale, ask the model to write one as
  ordinary output.
- **The blob is complete on the event that opens the item**, not assembled from later
  events, so a streaming application that wants to chain the next turn can persist it
  immediately rather than waiting for `response.completed`. The recipe reads it from
  `event.item.encrypted_content` for that reason, and prints when it arrived.
- **The pause is billed.** 137 reasoning tokens here, invisible in `output_text`, counted
  in `usage.output_tokens_details.reasoning_tokens`, and drawn from the same
  `max_output_tokens` budget as the answer.

This is also the honest answer to "does streaming hide the wait on a reasoning model?" —
only partly. The thinking happens before any text exists, so higher effort pushes the
first token later. Streaming hides a long *answer*; it cannot hide a long *think*, which
is worth designing a visible "thinking" state around.

## Where the token counts arrive

`usage` is populated once, on `response.completed`, and is `None` on every earlier event.
Section B reads the counts from `event.response.usage` on that event rather than from the
accumulated response, because in a streaming recipe where a value comes from is part of
the lesson:

```
   tokens             31 in / 228 out, read off the response.completed event
   No delta event carried a usage object, so there is no running total to
   meter: a per-request cost figure is recorded when the turn ends.
```

So a cost figure is something you record when a turn finishes rather than something you
meter as it runs. When you need a hard ceiling while the turn is in flight,
`max_output_tokens` is the right mechanism: it is enforced by the service, so unlike a
client-side counter it cannot be raced.

## Inspect what happened

The script ends on what the three runs together establish, written out rather than left
as a table to interpret:

```
E. What to take from this

   Streaming changed when the first word appeared, not what the turn cost.
   Reading began at 0.5s streamed against 5.8s unstreamed, while the
   two answers billed 256 and 232 output tokens — a difference that comes
   from the wording the model chose, not from how it was delivered.
```

The token counts differ between the two runs because the model worded the answer
differently, not because streaming changed the price. A streamed call is not cheaper.

## Production considerations

- **Set a client timeout.** The default is generous but not infinite, and a streamed
  turn with reasoning can be slow. A stalled stream shows up as a client-side
  timeout mid-render, so decide what your UI does with a half-written answer.
- **Handle a mid-stream failure explicitly.** Exiting the `with` block closes the
  connection, but the text you have already printed is still on the reader's screen.
  Either buffer until `response.completed` and render once, or make partial output
  visibly provisional. This recipe does not verify whether closing the stream stops
  the model working, so do not assume abandoning a stream saves money.
- **Do not parse text out of deltas to drive logic.** Waiting for
  `stream.get_final_response()` and reading the typed items is both simpler and
  correct; delta boundaries fall wherever the tokenizer put them, mid-word and
  mid-JSON.
- **429 is a tokens-per-minute quota** on this endpoint, not a request-rate limit.
  The client's `max_retries` backs off for you, which is why this recipe sets it and
  does not hand-roll a retry loop. A retry restarts the stream from the beginning.
- **Streaming and buffering fight each other.** A proxy, load balancer or WSGI layer
  that buffers responses will erase the benefit while everything still "works" —
  measure first-token time end to end in your own stack, not just against the API.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS
  credential chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **Inference stays in the Region you name**, and the Region is printed at the start.
- **No tools, no retrieval, no network access beyond Bedrock**, so no content leaves
  the AWS boundary.
- The prompts are fixed strings containing no personal or customer data. Note that
  streaming to an end user's browser puts model output in a new place — if that
  output can contain sensitive input, the transport and the client-side buffer are
  now in scope for your review.

## Limitations and non-goals

- Does not stream tool calls or Web Search annotations. Those add event types
  (`response.output_text.annotation.added` among them) and belong with the recipes
  whose subject they are.
- Does not build a UI. It shows which events to watch; rendering is your framework's
  problem.
- Does not verify whether abandoning a stream stops generation or billing.
- Does not cover background mode, which is a different way to handle a slow response
  and is not streaming.
- **No latency figures are published here.** The script times your own run; timings from
  one account and Region do not transfer to another, so this recipe reports the shape —
  first token early, completion later — and leaves the numbers to your environment.

## Clean up

Nothing to tear down. On-demand inference creates no resources, and `store=False`
means there is no stored response to delete.

## Next steps

- [`cookbooks/01-foundations/01-first-call/`](../01-first-call/) — the unstreamed call, and the four
  permissions that authorize it.
- [`cookbooks/01-foundations/06-choosing-a-model/`](../06-choosing-a-model/) — which of the three GPT-5.6
  models to point this at, measured rather than assumed.
