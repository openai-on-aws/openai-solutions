---
title: Conversation state, and who keeps the transcript
capabilities: [FND-07, GOV-05]
primary_capability: FND-07
industry: —
industry_scenario: >
  Cross-industry. A team building a multi-turn assistant has to decide whether the
  conversation lives on the service or in their own application, which on Bedrock is
  also a decision about how long AWS retains the transcript.
models: [openai.gpt-5.6-luna]
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

# Conversation state, and who keeps the transcript

A second turn needs the first one. The Responses API offers two ways to arrange that, and
choosing between them is more interesting on Bedrock than elsewhere — because it is also a
decision about what gets retained, and for how long.

| | |
|:--|:--|
| **What you will learn** | The two ways to continue a conversation, what each one costs in tokens, and which one a regulated workload can defend |
| **Capability** | Conversation state on the Responses API |
| **Model** | `openai.gpt-5.6-luna` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — six short calls capped at 80 output tokens |
| **You will need** | Inference permission only |

> **What it does.** Runs the same two-turn conversation both ways and prints the token cost of
> each. **What it creates.** Two stored responses in pattern B, which the script deletes in its
> final step and then confirms are gone.

## The two patterns

```python
# Manual history — your application holds the messages
history.append({"role": "assistant", "content": first.output_text})
history.append({"role": "user", "content": follow_up})
second = client.responses.create(model=MODEL_ID, input=history, store=False)

# previous_response_id — the service holds them for you
second = client.responses.create(
    model=MODEL_ID, previous_response_id=first.id, input=follow_up, store=True
)
```

The second form is less code and less bookkeeping, and it exists because storing a response is
the default: Responses requests set `store: true` unless you say otherwise, and AWS keeps a
stored response — input and output — for 30 days
([reference](https://developers.openai.com/api/docs/guides/amazon-bedrock)). That is what makes
`previous_response_id` possible at all.

Side by side, the only thing that differs is which side of the boundary the transcript sits on:

| | Manual history, `store=False` | `previous_response_id`, `store=True` |
|:--|:--|:--|
| **What your application holds between turns** | The whole transcript | One response id |
| **What the service holds** | Nothing | The response, input and output |
| **For how long** | Not applicable | 30 days, or until you delete it |
| **What turn 2 sends** | The full history and the new message | An id and the new message |
| **What it takes to remove** | Nothing to remove | `client.responses.delete(id)` |
| **Redact or summarize a turn** | Yours to do, because you hold the text | Not possible on the stored copy |

So the choice comes with a retention consequence attached, which is usually what settles it.
If your workload is happy with a 30-day window, the convenient pattern is genuinely
convenient. If it is not, holding the transcript yourself is the pattern that fits — and it
brings some real advantages of its own, which the last section covers.

## What you will build

```
A. manual history, store=False       two turns, nothing left on the service
B. previous_response_id, store=True  two turns, two stored responses
C. the token comparison              what referencing a response does and does not save
D. delete what B created             and confirm it is gone
```

## Prerequisites

- **The [prerequisites in the cookbooks README](../../README.md)** — a Region with model
  access and IAM permission for inference on `bedrock-mantle`.
- **Working AWS credentials.** Run `aws sts get-caller-identity` first.
- **No extra dependencies.**

## Run it

```bash
uv sync
uv run python 01-foundations/04-conversation-state/python/conversation_state.py
```

## Referencing a response saves bookkeeping, not tokens

This is the part worth measuring, because "you do not have to resend the history" sounds like
it should be cheaper:

| Pattern | Turn 1 | Turn 2 |
| --- | --- | --- |
| Manual history | 16 input tokens | 60 input tokens |
| `previous_response_id` | 16 input tokens | 60 input tokens |

**Both second turns bill roughly four times their first.** The model receives the prior
exchange either way; what `previous_response_id` saves is the bandwidth of resending it and the
code to track it. A stateful turn is not a free turn, and `usage.input_tokens` is where you
see that.

The two figures are close but will not always match exactly: each run produces a slightly
different answer, and the manual path resends precisely the text it received while the stored
path references the service's own copy. The shape is the point rather than the digits.

## Choosing between them

The decision is genuinely two-sided, and both sides have something to recommend them.

**If you want no server-side retention, you own the transcript.** That is not a consolation
prize. Holding the messages is what lets you redact personal data before the next turn,
summarize a long thread, drop turns you are not permitted to keep, or replay a conversation
against a different model.

**If you want the convenience, plan for the 30-day window** and put it in whatever document
your security reviewer reads. It is a short, documented, deletable retention period — and this
recipe shows the delete call.

One practical note: `previous_response_id` needs the response it references to have been
stored, so the two halves travel together. A follow-up against a `store=False` response returns
a clean `404 not_found_error: Response not found.`, which is
the API telling you that you have picked half of one pattern and half of the other.

## Where `store=True` is used again

This is not a pattern the cookbook shows once and then avoids. Two later recipes use it
because it is the right tool for what they do:

- `cookbooks/02-reasoning-and-output/04-reasoning-across-turns/`
  opens with `previous_response_id` and `store=True`, because carrying a reasoning chain
  forward is exactly what the pattern is for.
- **An agent loop is the strongest case of all.** A loop that takes eight rounds resends its
  whole transcript on every round, and `previous_response_id` replaces that with an id plus
  the new tool results. It works with tool calls: sending only the `function_call_output`
  items and referencing the previous response returned a correct answer, with input growing
  59 → 138 tokens across the two turns. Note that the
  growth is still there, exactly as measured above — what you save is the resend, not the
  tokens. `cookbooks/04-agents/01-the-agent-loop/` holds
  its own transcript so the accumulation is visible, and its production notes cover the
  trade.

## There is no Conversations API on this endpoint

Upstream OpenAI material describes a third pattern: a longer-lived `Conversation` object for
durable threads across sessions and devices. It is **not available on `bedrock-mantle`**:

```
client.conversations.create() -> 404
```

It is also absent from
[OpenAI's Bedrock feature table](https://developers.openai.com/api/docs/guides/amazon-bedrock).
If you need durable threads across devices, that belongs in your application's own database —
which, if you are already holding the transcript for the reasons above, you have.

## "Stateless" and "stateful" are implementation choices

They are not different models and not different endpoints. The model receives its context on
every turn in both patterns. The only question is who keeps it between turns — your application
or the service — and nothing about the model changes either way.

## Production considerations

- **Bound the transcript before it bounds you.** Neither pattern truncates anything, so a long
  thread grows its own input bill. Manual history is where you have the room to summarize or
  drop turns.
- **Prompt caching rewards a stable prefix.** A long unchanging prefix followed by a short
  changing suffix is what caches well, which is another reason to control exactly what you
  send. See `cookbooks/05-production/01-prompt-caching/`.
- **Set `store` explicitly, whichever way you want it.** Both values are reasonable; writing
  the one you mean makes the retention posture visible to the next person who reads the code.
- **Treat response ids as pointers to retained content.** They are not secrets, but they
  resolve to a stored conversation, so handle them like any other identifier that reaches
  customer data.
- **Carry `response.output` forward unmodified on a reasoning-heavy thread.** The output can
  include a reasoning item, and passing it along keeps multi-turn quality. That is the subject
  of `cookbooks/02-reasoning-and-output/04-reasoning-across-turns/`.

## Data handling and security

- **Pattern A stores nothing on the service.** `store=False` on every call, so AWS retains
  neither request nor response.
- **Pattern B stores two responses**, retained for 30 days unless deleted — and this recipe
  deletes them in step E.
- **Credentials come from the AWS credential chain.** None are handled, stored or printed.
- **Inference stays in the Region you name**, which is printed at the start of the run.
- **The conversation is about a database product**, so no personal or customer data is sent.

## Limitations and non-goals

- **It does not summarize or truncate a long thread.** Real applications need that; the
  mechanism here is two turns.
- **It does not carry reasoning items forward**, which matters on a reasoning-heavy prompt and
  is its own recipe.
- **It does not measure latency.** The interesting difference between the patterns is retention
  and bookkeeping rather than speed.
- **It does not test what happens on day 30.** The retention period is documented, not
  something this recipe verifies.

## Clean up

Unlike the other recipes in this group, this one leaves something behind, so it cleans up after
itself and then checks:

```python
client.responses.delete(response_id)
```

After deletion, `client.responses.retrieve(...)` returns `404`. If you
interrupt the script partway through step B, two stored responses remain and age out on their
own after 30 days.

## Next steps

- [`cookbooks/01-foundations/01-first-call/`](../01-first-call/) — the call itself, and the permissions it needs.
- [`cookbooks/01-foundations/05-streaming/`](../05-streaming/) — what the response looks like as it is generated.
