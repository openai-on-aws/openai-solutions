---
title: Carrying reasoning across turns
capabilities: [RSN-04, RSN-05]
primary_capability: RSN-04
industry: —
industry_scenario: >
  Any multi-turn or tool-calling workload on a reasoning model. The parameter that decides
  whether earlier reasoning is replayed defaults, on GPT-5.6, to replaying all of it — so an
  agent loop pays for every prior turn's thinking on every subsequent turn unless someone
  changes it.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: advanced
estimated_cost: medium
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Carrying reasoning across turns

A reasoning model returns a reasoning item alongside its answer. On a conversation with
several turns — or an agent taking several tool-calling steps — you can carry that item
forward so the model keeps its own train of thought instead of re-deriving it.

`reasoning.context` decides how much of it comes back:

| | |
|:--|:--|
| **What you will learn** | The two ways to continue a conversation, and what `reasoning.context` adds to your input bill |
| **Capability** | Carrying reasoning across turns |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Advanced |
| **Cost** | Medium — nine calls on a problem chosen to make the model think |
| **You will need** | Inference permission only |

> **What it does.** Builds a three-turn transcript on a constraint problem, then sends it
> twice under each `reasoning.context` setting to compare the cost. **What it creates.** Two
> stored responses in step A, which `previous_response_id` requires; everything else uses
> `store=False`.

| Value | Behaviour |
| --- | --- |
| `current_turn` | Replay only the reasoning from the turn just taken |
| `all_turns` | Replay every earlier turn's reasoning — **the GPT-5.6 default** |
| `auto` | Resolve to the model's own default, which is not the same on every model |

The default is the expensive one, and the cost is not constant: each turn replays the
reasoning of every turn before it, so input grows superlinearly across a long loop. This
recipe measures the difference on the same chain with the visible transcript held identical,
so any change in input tokens is the reasoning being re-rendered and nothing else.

## What you will build

```
A. two patterns      previous_response_id, and stateless replay of response.output
B. the parameter     what each value of reasoning.context means
C. the accumulation  one four-turn chain, run twice, measured per turn
D. the carrier       encrypted_content is the thing being replayed
E. choosing          when the default earns its cost and when it does not
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`. No extra permissions, no AWS resources.
- No data files. The chain is a three-turn constraint problem in the script, chosen because
  it genuinely needs deduction — on an easy question the model emits no reasoning at all and
  there is nothing to carry or measure.

**Cost: medium, from call volume and reasoning output.** Around nine calls on a problem
chosen to make the model think — the three transcript turns alone produced 419, 63 and 1,221
reasoning tokens, all billed as output.
[Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python \
  02-reasoning-and-output/04-reasoning-across-turns/python/reasoning_across_turns.py
```

## A. Two continuity patterns, and only two

**`previous_response_id`** references a response AWS stored, so the transcript lives
server-side:

```python
first = client.responses.create(model=MODEL_ID, input=question_one, store=True)
second = client.responses.create(
    model=MODEL_ID, previous_response_id=first.id, input=question_two, store=True,
)
```

It requires `store=True`, and on Bedrock a stored response means AWS retains input and
output for 30 days. That is a data-handling decision, not an implementation detail.

**Stateless replay** keeps the transcript in your application:

```python
history += response.output          # unmodified, reasoning item included
history.append({"role": "user", "content": next_question})
```

Both send the model the same context. The difference is who stores it — so the choice is a
retention question, not a capability one.

There is no third pattern here. A Conversations API exists on the first-party OpenAI API and
is not available on this endpoint, so these two are the whole set.

**Carry `response.output` forward unmodified.** Filtering it to "just the message" is the
mistake that quietly removes the reasoning item, and with it the thing this recipe is about.

## B and C. What each setting costs

`reasoning.context` decides how much of the earlier reasoning is rendered back into the
request. At `effort: medium`, sending the same three-turn transcript and the same question
under each setting:

| `reasoning.context` | Input tokens |
| --- | --- |
| `current_turn` | 1,064 |
| `all_turns` (the default) | **2,773** |

**+1,709 tokens, or +161%, for the same question over the same history.**

The shape is what to plan around: `all_turns` re-renders the reasoning of *every* earlier
turn, so what it adds grows with turn count while `current_turn` stays flat. On three turns
it already more than doubles the input; in a twenty-turn agent loop it becomes the largest
single item in the input bill. That makes it a parameter worth setting deliberately rather
than inheriting.

The value comes back on `response.reasoning.context`, so you can confirm what the service
applied.

### Give it something to carry

The amount of reasoning in the transcript is what there is to replay, and that depends
entirely on the task. The constraint problem in this recipe produces **419, 63 and 1,221**
reasoning tokens across its three turns, with encrypted blobs of 1,904, 968 and 5,012
characters.

A straightforward question produces almost none — sometimes no reasoning item at all — and
then both settings cost the same because there is nothing to render. So when you try this on
your own workload, read `usage.output_tokens_details.reasoning_tokens` first: it tells you
whether this parameter is worth tuning for that task at all.

**Compare answers as well as tokens.** If a chain reaches the same conclusion under
`current_turn`, the extra input bought nothing on that workload. On a chain where later steps
genuinely depend on earlier deduction, the replay is doing real work.

## D. What carries the reasoning, and how to drop it

The reasoning item comes back with `summary: []`, `content: []` and an opaque
`encrypted_content` blob. You cannot read it; the model can, and `all_turns` is what renders
it back into the next request.

That gives you a second, finer control. Removing `encrypted_content` from an individual item
leaves nothing to replay for that turn, and the cost drops to the `current_turn` level:

```
all_turns, blob removed      input_tokens=1064
all_turns, blob present      input_tokens=2773
current_turn                 input_tokens=1064
```

So there are two levers: the parameter for the whole request, and the items themselves for
individual turns. A long-running agent can keep continuity for its recent steps and shed the
older ones, which is more precise than switching the whole conversation to `current_turn`.

Two more properties worth knowing:

- **The blob is returned whether or not you store the response**, so stateless replay loses
  nothing.
- **`usage.output_tokens_details.reasoning_tokens`** is how you see how much thinking
  happened. That number, not the trace, is what a capacity model needs.

## E. Choosing

- **`all_turns`** for a short chain where later turns build on earlier deduction and
  correctness matters more than the input bill.
- **`current_turn`** for a long loop, where replaying twenty prior traces costs more than it
  adds.
- **`auto`** looks portable and is not: it resolves per model, so changing model can change
  your cost profile without changing a line of your code. Pin the value you mean.

## Production considerations

- **Decide this parameter deliberately in any agent loop.** It is the difference between
  linear and superlinear input growth, and the default is the superlinear one.
- **Compare settings on a fixed transcript.** Send the same history twice rather than
  running the conversation twice, so you are looking at the parameter rather than at two
  different sets of answers.
- **The encrypted blob is Region-scoped.** Reasoning produced in one Region cannot be
  replayed into another; a cross-Region failover starts without it.
- **Long chains need compaction, not just a cheaper context setting.** Summarize or drop
  early turns once a conversation outgrows its usefulness — replaying less reasoning does
  not shrink the visible transcript.
- **Pair with caching carefully.** A stable prefix caches well; a transcript that grows every
  turn does not, because the prefix changes. Cache the instructions, not the conversation.
- **`store=True` for `previous_response_id` has a retention consequence.** If you chose
  `store=False` for a reason, stateless replay is the pattern that respects it.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS credential
  chain; nothing is passed, stored or printed.
- **`store=False` everywhere except step A**, which sets `store=True` because
  `previous_response_id` requires it — and says so, because that means AWS retains those two
  requests and responses for 30 days.
- **The encrypted reasoning blob is content.** It travels in your request payload and is
  scoped to the Region that produced it.
- **The questions are a synthetic arithmetic chain**, chosen to need real deduction and to
  contain nothing sensitive.

## Limitations and non-goals

- **No latency measurement.** Replaying reasoning changes the amount of input to process; no
  timing claim is made here.
- **One chain, three turns, one model, one effort level.** The +161% is specific to this
  transcript; what generalizes is that the cost grows with turn count.
- **No compaction implementation.** The production note recommends it; the recipe does not
  demonstrate it.
- **No tool calls.** Reasoning replay matters most in a tool loop, and this recipe isolates
  the parameter instead so nothing else moves.
- **`xhigh` and `max` effort are not swept here**, which would change how much reasoning
  there is to carry in the first place.

## Clean up

The two calls in step A are stored, so AWS retains them for 30 days. Everything else uses
`store=False` and leaves nothing. There are no resources to delete.

## Next steps

- [`cookbooks/02-reasoning-and-output/02-reasoning-effort-and-verbosity/`](../02-reasoning-effort-and-verbosity/) — how much
  reasoning gets produced in the first place, which sets how much there is to replay.
- [`cookbooks/05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/) — the
  other half of the input bill in a loop.
