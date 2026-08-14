---
title: Cutting agent cost with explicit prompt caching
capabilities: [EFF-02, EFF-01, EFF-07]
primary_capability: EFF-02
industry: TMT
industry_scenario: >
  A telecom operator's tier-2 support agents work every fault against the same access
  network runbook. The agent loop resends that runbook on every turn, so at contact-centre
  volume the stable context — not the customer's question — is what dominates the bill and
  eats the tokens-per-minute quota.
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
last_validated: 2026-08-12
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Cutting agent cost with explicit prompt caching

Most production prompts are mostly the same prompt. An agent loop, a RAG pipeline and a
support assistant all send a large stable block — instructions, a runbook, retrieved
context — followed by a small changing one. Paying full price for the stable block on every
turn is the most common avoidable cost in a language-model workload.

Bedrock gives GPT-5.6 two ways out
([announcement](https://aws.amazon.com/blogs/machine-learning/introducing-explicit-prompt-caching-for-openai-gpt-5-6-models-on-amazon-bedrock/)):

- **Implicit**, the default. Bedrock places a breakpoint on the latest message and looks
  for a reusable prefix. No parameters, no code.
- **Explicit**, where you mark the boundary. More control, and deterministic.

This recipe measures both, and shows the two configuration mistakes that quietly turn
caching off.

| | |
|:--|:--|
| **What you will learn** | How to place a cache breakpoint yourself, what a cached prefix saves, and the two configuration choices that turn caching off |
| **Capability** | Explicit prompt caching on GPT-5.6 |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Low — around 16 calls, most of the input billed at the cache read rate |
| **You will need** | Inference permission and a GPT-5.6 model |

> **What it does.** Sends a support runbook as a stable prefix under implicit and explicit
> caching, then runs a six-turn session and reports how much of the input came from the cache.
> **What it creates.** Cache entries that expire on their own within 30 minutes.

## What you will build

```
A. the prefix    what is stable, and the 1,024-token floor
B. implicit      the default, with no parameters at all
C. explicit      mark the boundary, watch it write then read
D. the cache key a partition, not a label
E. the prefix's home  instructions= versus a marked content part
F. the session   six turns over one runbook
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`. No extra permissions, no AWS resources.
- **A GPT-5.6 model.** Explicit caching is 5.6-only: `prompt_cache_options` on
  `openai.gpt-5.5` returns
  `400 invalid_parameter: prompt_cache_options is not supported on this model`. 5.5 and 5.4
  get implicit caching only.
- Synthetic data in [`data/runbook.md`](data/runbook.md) — a fabricated tier-2 runbook for
  a fictional operator, sized deliberately above the caching floor.

**Cost: low.** Around 16 calls with roughly 1,280 input tokens each and output capped at
200. Most of that input is billed at the cache read rate, which is the point.
[Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 05-production/01-prompt-caching/python/prompt_caching.py
```

## A. The floor is 1,024 tokens, and falling under it is silent

The runbook plus one question bills **1,281 input tokens**, which clears the minimum
cacheable prefix of 1,024 tokens with little to spare.

Under that floor nothing caches, `cached_tokens` stays `0`, and **the request still
succeeds**. There is no error to catch, so the first thing to check when caching appears not
to work is the size of the thing you are trying to cache.

## B. Implicit caching costs nothing to adopt

```python
client.responses.create(model=MODEL_ID, input=[...])   # that is all
```

```
implicit turn 1   READ   in=1281   cached=1279   written=0
implicit turn 2   READ   in=1281   cached=1279   written=0
```

Both turns read, because an earlier call in the same run had already sent this prefix. That
is implicit caching working with zero configuration, and it is why the honest framing of
explicit mode is *more control*, not *caching versus no caching*.

Note that implicit caching covers the **whole** input including the top-level
`instructions` field. Explicit mode does not — see step E, which is the entire reason that
matters.

## C. Explicit caching is deterministic

```python
prefix_part = {
    "type": "input_text",
    "text": RUNBOOK,
    "prompt_cache_breakpoint": {"mode": "explicit"},   # end of what repeats
}

client.responses.create(
    model=MODEL_ID,
    input=[
        {"type": "message", "role": "developer", "content": [prefix_part]},
        {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": question}]},
    ],
    prompt_cache_key="northlink-runbook-v1",
    extra_body={"prompt_cache_options": {"mode": "explicit", "ttl": "30m"}},
)
```

```
explicit turn 1   write  in=1281   cached=0      written=1258
explicit turn 2   READ   in=1281   cached=1258   written=0
```

Call one writes 1,258 tokens, call two reads exactly 1,258. **This is deterministic on
GPT-5.6, not best-effort** — the same numbers come back on every repeat, which is what makes
it something you can put in a cost model rather than hope for.

Two details in that call:

- **The breakpoint goes at the end of what repeats.** Everything before it is the cacheable
  prefix; everything after is the changing suffix. Breakpoints attach to `input_text`,
  `input_image` and `input_file` parts, and you can place up to four — which is what lets you
  cache several sections that change at different rates.
- **`ttl` accepts only `"30m"`.** `"5m"` and `"1h"` are rejected with
  `400 invalid_value: Invalid value: '5m'. Supported values are: '30m'.` Thirty minutes is a
  floor on reuse, not a tunable.

![The same request drawn twice. On call one, a stable prefix — the developer message carrying the runbook, 1,258 tokens — is followed by a breakpoint and then a changing suffix, the user question; the measurement is written=1258, cached=0. On call two the prefix is identical and the suffix is a different question, and the measurement is cached=1258, written=0. Because the prefix and the cache key are the same, the second call is a cache hit: the prefix is written once and read on every subsequent turn.](images/cache-breakpoint.drawio.svg)

*What to take from it: the prefix is one block that exists in both requests, written the first
time and read every time after. The breakpoint is the line between what repeats and what
changes, and the ratio between those two blocks is the whole economics of the feature.*

## D. `prompt_cache_key` partitions the cache

This is the mistake with the largest bill attached, because the instinct that causes it is a
good one: adding an identifier to a key for observability.

```
key 'runbook-v1-session-8912'    write  in=1276   cached=0      written=1258
key 'northlink-runbook-v1'       READ   in=1280   cached=1258   written=0
```

Same prefix, same breakpoint, different key: **a full rewrite at the write premium, and no
read.** A key that carries a session id, request id or timestamp therefore pays the premium
on every single call and never collects the discount — strictly worse than not caching at
all.

**Key on what the prefix is, not on what the request is.** `northlink-runbook-v1` names the
content and its version, so a runbook update becomes `-v2` and cleanly invalidates the old
entry. If you need per-tenant isolation, that belongs in the key; a per-*request* value never
does.

## E. `instructions=` cannot carry a breakpoint

The natural place for a system prompt is the `instructions` field, and the AWS blog's
implicit example puts it there. It caches fine implicitly. Switch that same workload to
explicit mode:

```
instructions= + explicit, call 1    —    in=1278   cached=0   written=0
instructions= + explicit, call 2    —    in=1280   cached=0   written=0
```

**Nothing written, nothing read.** A breakpoint cannot be attached to `instructions`, and
explicit mode with no breakpoint anywhere is a complete opt-out of caching. So a team that
turns on explicit caching to save money, without moving the system text, silently caches
nothing — worse than the implicit behaviour they replaced, with no error to notice.

The fix is structural, not a parameter: move the system text into a `developer` message as an
`input_text` part and mark it, which is exactly what step C does. Worth knowing that "explicit
mode with no breakpoints" is also the documented way to opt *out* of cache billing
deliberately — it is only a trap when it is an accident.

## F. What a session actually looks like

Six turns against the warm prefix:

```
turn 1   READ   in=1281   cached=1258
turn 2   READ   in=1281   cached=1258
turn 3   READ   in=1276   cached=1258
turn 4   READ   in=1280   cached=1258
turn 5   READ   in=1278   cached=1258
turn 6   READ   in=1280   cached=1258

6 turns, 7676 input tokens in total:
    7548 read from cache
       0 written to cache
     128 new content
98% of this session's input arrived through the cache.
```

**98%** — and the shape is what generalizes, not the digit: in a loop with a large stable
prefix, almost the entire input bill is cache reads after the first turn. The 128 tokens of
new content are the actual questions.

Two economic consequences:

- **Reads are discounted heavily, writes carry a premium**, so break-even arrives early. A
  prefix read even a handful of times has already paid for its write. Current rates are on
  the [pricing page](https://aws.amazon.com/bedrock/pricing/) — this recipe deliberately
  quotes ratios rather than numbers, because prices move.
- **Cached input does not count against the input-tokens-per-minute quota.** So caching
  raises the throughput ceiling on a busy loop as well as lowering the bill, which is often
  the more urgent problem in a contact centre at peak.

## Inspect what happened

The response is the authoritative source, and **CloudWatch has no cache metric**:

```python
d = response.usage.input_tokens_details
d.cached_tokens        # read from cache
d.cache_write_tokens   # written to cache
# input_tokens = cached_tokens + cache_write_tokens + new content
```

A hit is `cached_tokens > 0`. `cache_write_tokens == 0` on its own proves nothing — you also
see it when nothing cached at all, which is exactly what step E looks like. **Assert on
`cached_tokens`.**

## Production considerations

- **Choose the mode by prefix shape.** Implicit for an exactly-repeating prompt; explicit for
  a stable prefix with a changing suffix, or for several sections that change at different
  rates.
- **Version the cache key with the prefix.** `-v1` to `-v2` on a runbook edit invalidates
  cleanly; a stale key serving an old prefix is a correctness problem, not just a cost one.
- **The cache is scoped per model and per Region.** A prefix written on Terra will not read on
  Luna, and one written in `us-east-1` will not read in `us-east-2`. Do not split a
  cache-sensitive workload across tiers or Regions, and remember a Region failover starts
  cold.
- **Thirty minutes is the only TTL.** A workload with gaps longer than that pays a write per
  gap; if the traffic is bursty, that changes the arithmetic.
- **Order your context by rate of change.** Stable instructions first, then the runbook, then
  retrieved context, then the turn. A breakpoint can only help if what precedes it is
  genuinely identical, byte for byte.
- **Anthropic-style `cache_control` is silently ignored here.** It is the Claude mechanism and
  does not cross over; any hit you see alongside it is ordinary implicit caching. The OpenAI
  mechanism is `prompt_cache_breakpoint`.
- **Measure across calls, not on one.** A single request cannot tell you whether caching is
  working; the write/read pair can.
- **Caching is orthogonal to `store`.** This recipe runs `store=False` throughout and caches
  normally — cache state and response retention are different things.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS credential
  chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **A cached prefix is content held server-side for up to 30 minutes.** Cache scope is your
  own account, model and Region, but it is worth naming in a data-flow review: caching a
  prefix that contains customer data means that data is retained for the TTL. Cache the
  stable, non-sensitive part of your context, which is usually exactly what repeats anyway.
- **The runbook, the operator and the ticket codes are fabricated.**

## Limitations and non-goals

- **No latency claims.** Caching reduces prefill work and should reduce time-to-first-token,
  but this was not measured on representative capacity, so no timing figure is given.
- **No absolute cost figures.** Ratios and token counts only; rates belong to the pricing
  page.
- **One prefix, one Region, one model.** No cross-Region or cross-tier measurement beyond
  stating the documented scope.
- **No multi-breakpoint example.** Several sections changing at different rates is the
  natural next step and is not shown here.
- **Not a real agent loop.** There are no tools and no conversation state; the turns are
  independent so the caching behaviour is unambiguous.
- **The 30-minute TTL is not tested to expiry**, and a read close to the boundary is not
  characterized.

## Clean up

Nothing to tear down. Cache entries expire on their own within 30 minutes, on-demand
inference creates no resources, and `store=False` leaves no stored response.

## Next steps

- [`cookbooks/02-reasoning-and-output/02-reasoning-effort-and-verbosity/`](../../02-reasoning-and-output/02-reasoning-effort-and-verbosity/)
  — the output-side cost lever, which composes with this input-side one.
- [`cookbooks/05-production/02-pii-masking/`](../02-pii-masking/) — what to screen out of a prefix before you cache
  it for half an hour.
