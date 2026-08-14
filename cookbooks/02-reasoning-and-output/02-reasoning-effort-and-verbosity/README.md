---
title: Right-sizing reasoning effort and verbosity against a quality bar
capabilities: [RSN-01, RSN-02, RSN-06]
primary_capability: RSN-01
industry: RCG
industry_scenario: >
  A retailer adjudicates returns automatically at high volume, so the cost of a single
  decision is the constraint that decides the design. The team needs to know the cheapest
  reasoning level that still gets the outcome right, and needs the answer measured against
  its own policy rather than assumed from a model card.
models: [openai.gpt-5.6-luna]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-12
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Right-sizing reasoning effort and verbosity against a quality bar

Two parameters on the same request control two different things, and conflating them is
the most common way to overpay for a reasoning model:

- **`reasoning.effort`** — how much the model thinks before it answers. Levels are `none`,
  `low`, `medium`, `high`, `xhigh` and `max`, default `medium`
  ([source](https://aws.amazon.com/blogs/machine-learning/introducing-explicit-prompt-caching-for-openai-gpt-5-6-models-on-amazon-bedrock/)).
- **`text.verbosity`** — how long the answer is. `low`, `medium`, `high`, default `medium`.

They are independent, so *think hard and answer briefly* is a legitimate and useful
combination. This recipe puts both against a task with known answers, so you can see what
each dial actually changes and what it costs.

| | |
|:--|:--|
| **What you will learn** | What each reasoning effort level buys on a real task, and how `text.verbosity` changes answer length independently |
| **Capability** | Reasoning effort and output verbosity |
| **Model** | `openai.gpt-5.6-luna` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Medium — 48 calls for the sweep, plus seven more |
| **You will need** | Inference permission only |

> **What it does.** Sweeps four effort levels over twelve return requests scored against a
> written policy, then varies verbosity on two prompts. **What it creates.** Nothing —
> `store=False` throughout.

## What you will build

```
A. the task     12 return requests against an 8-rule policy, with known outcomes
B. the sweep    accuracy and tokens at effort none / low / medium / high
C. verbosity    the same request at three answer lengths, effort held constant
D. sampling     temperature, and the one effort level that accepts it
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`. No extra permissions, no AWS resources.
- Synthetic data: [`data/returns_policy.md`](data/returns_policy.md) (eight rules that
  interact) and [`data/return_requests.jsonl`](data/return_requests.jsonl) (twelve requests
  with the expected outcome and governing rule written in). Both fabricated, for a
  fictional retailer.

**Cost: medium, because of call volume rather than fee type.** The sweep is 4 levels × 12
cases = 48 calls, plus 7 more for verbosity and sampling. Inputs are small and identical
(8,062 input tokens per level); output ranges from 279 tokens at `none` to 1,434 at `high`.
No per-operation fees. [Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python \
  02-reasoning-and-output/02-reasoning-effort-and-verbosity/python/effort_and_verbosity.py
```

Around four minutes for the full sweep.

## A. A task with right answers

Scoring reasoning effort needs a task where "correct" is not a matter of taste. The policy
has eight rules that interact deliberately:

- **R4 (faulty) overrides R2 (electronics) and R3 (final sale).** An opened, faulty speaker
  is a refund, not the store credit R2 would give.
- **R6 (Gold) extends some windows and not others.** Day 32 on a 30-day window is a reject
  for a standard member and a refund for Gold.
- **R7 (heavy) and R8 (missing packaging) change the handling, not the eligibility.**

Six of the twelve cases need two rules combined. Each case carries `expected_decision` and
`expected_rule`, written from the policy, so **nothing is adjudicated by a judge model** —
the score is an exact comparison against a `Literal` field.

The answer comes back as a schema, which is the technique from
[`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../01-structured-claims-intake/):

```python
class Ruling(BaseModel):
    decision: Literal["refund", "store_credit", "reject"]
    governing_rule: str
```

## B. The sweep, and what it actually shows

One variable changes across the four runs, all on `openai.gpt-5.6-luna`:

| `reasoning.effort` | Decisions correct | Rule cited correctly | Output tokens | of which reasoning |
| --- | --- | --- | --- | --- |
| `none` | **12/12** | 10/12 | **279** | 0 |
| `low` | 12/12 | 9/12 | 620 | 333 |
| `medium` | 12/12 | 10/12 | 1,171 | 898 |
| `high` | 12/12 | 10/12 | 1,434 | 1,134 |

**The outcome saturates at the bottom of the ladder.** The cheap tier, told not to think at
all, got all twelve rulings right — including every case that needs two rules combined, and
including R4 overriding R2 on an opened faulty item. Going from `none` to `high` bought
**5.1× the output tokens and no additional correct decisions**.

**The rule-citation column stays flat too**, at 9–10 out of 12 at every level. Repeat runs
moved it around within that band, so on this task the extra thinking is not buying better rule
references either — if the citation is what your audit trail depends on, a clearer instruction
about how to cite is likely to help more than a higher effort setting.

**What to take from the shape.** Two quality bars land in different places, and effort is the
dial you set once you know which bar you are aiming at. For *the outcome*, this workload is
already clear at `none`, and on a service adjudicating thousands of returns a day that is the
whole cost model. For anything more demanding than this — a task where the cheap tier at zero
effort does not already saturate — the ladder is there, and the same sweep tells you where to
stop.

> **`max_output_tokens` has to cover the thinking.** Reasoning tokens are drawn from the
> same budget as the answer, so a cap sized for a short reply will truncate a high-effort
> request. The 2,000 here is generous for a one-line ruling and exists so the top of the
> ladder is not silently starved.

## C. Verbosity moves length, within what the task allows

Effort held at `medium`, only `text.verbosity` changing:

| `text.verbosity` | A ruling (constrained) | A help-centre article (open-ended) |
| --- | --- | --- |
| `low` | 89 output tokens, 33 words | 333 tokens, 82 words |
| `medium` | 120 tokens, 56 words | 839 tokens, 100 words |
| `high` | 115 tokens, 53 words | 718 tokens, 134 words |

Two prompts, because the parameter can only stretch an answer as far as the task has room.
On the ruling — a decision and a rule reference — `low` and `high` are 33 and 53 words:
the task pins the length, and verbosity nudges it. On the open-ended article the low
setting produced a quarter of the word count of the high one.

Note the non-monotonic token counts in both columns. **Verbosity is a bias on length, not a
budget**, and the word counts track the intent more faithfully than the token counts do. If
you need a hard ceiling, `max_output_tokens` is the parameter that enforces one; if you
need a specific shape, say so in the prompt, which takes precedence over the parameter.

The value comes back on `response.text.verbosity`, so you can confirm what the service
applied.

> **It must be nested inside `text`.** A top-level `verbosity=` fails the whole request
> with `400 unknown_parameter` — a plausible mistake, since most parameters are flat.

## D. `temperature` is available at exactly one effort level

Every GPT-5.x model here is a reasoning model, and sampling controls and reasoning are
alternatives rather than companions:

```python
response = client.responses.create(
    model=MODEL_ID,
    input=request,
    reasoning={"effort": "none"},     # required for what follows
    temperature=0.2,
    max_output_tokens=400,
)
```

At `effort: none`, `temperature` and `top_p` are accepted and echoed back on the response.
At any reasoning level they return `400 unsupported_parameter`. The error names the model
rather than the effort level, so it reads as though
sampling is unavailable outright — it is not.

The practical consequence: **decide per call which axis you want.** A workload that needs
reproducibility-shaped behaviour and low latency runs at `effort: none` with a low
temperature. A workload that needs deliberation cannot also pin sampling, and controls
variability through the prompt and the schema instead — which is what phase B does, and why
its rulings are stable enough to score.

## Inspect what happened

`usage.output_tokens_details.reasoning_tokens` is the number that makes effort visible: 0
at `none`, rising to 1,134 at `high` on the same twelve inputs. You cannot read the
reasoning itself — on this endpoint the reasoning item carries encrypted content and its
summary comes back empty — but you can see exactly what it cost, which is the number a
capacity model needs.

Input tokens were identical at 8,062 per level, because the policy and the requests do not
change. **Effort is an output-side cost.** That matters for a long-prefix workload: if your
instructions are large and your questions small, effort changes the cheap half of the bill.

## Production considerations

- **Sweep your own labelled set before choosing a level**, and re-sweep after a model or
  prompt change. The result here is one model, one policy, one day.
- **Give the sweep enough cases to see the difference you care about.** Twelve is enough to
  show a saturated outcome column; resolving a few percentage points needs more cases and
  repeat runs.
- **Set `max_output_tokens` above the reasoning you are paying for**, or high effort
  truncates.
- **Cache the policy.** It is an identical multi-thousand-token prefix on every call and a
  natural explicit cache breakpoint.
- **Effort interacts with quota, not just cost.** Quotas are input and output tokens per
  minute; raising effort raises output tokens per request, so peak throughput falls even
  though the request count is unchanged.
- **Do not build an effort picker from an error message.** The per-model
  `400 unsupported_value` on a bad level omits `max`, which works, and the generic
  `400 invalid_value` advertises `minimal`, which does not. Probe the level you intend to
  use.
- **Keep a human on the reject path.** A wrong `refund` costs margin; a wrong `reject`
  costs a customer. Those are not symmetric, and a single accuracy number hides it.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS credential
  chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **Inference stays in the Region you name**, printed at the top of the run.
- **The policy, the requests and the retailer are fabricated.** No real customer, order or
  returns policy.
- **Real return requests contain personal data** — names, addresses, order identifiers.
  This recipe's inputs deliberately do not, and screening real ones is a separate step.

## Limitations and non-goals

- **Twelve cases shows the method, not an evaluation.** No confidence intervals, one prompt
  formulation.
- **No latency measurement.** Effort plainly affects response time, but this was not
  measured on throughput-limited capacity, so no timing claim is made here.
- **Only four of six levels.** `xhigh` and `max` exist and are untested here.
- **One model.** The right level is likely to differ on Terra and Sol, and the cheapest
  adequate *combination* is a tier-and-effort question, not an effort question.
- **No prompt tuning.** A better prompt might lift the citation column further than any
  effort setting does; the recipe holds the prompt constant on purpose.

## Clean up

Nothing to tear down. On-demand inference creates no resources, and `store=False` means
there is no stored response to delete.

## Next steps

- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../01-structured-claims-intake/) — the schema that
  makes these rulings checkable in the first place.
- [`cookbooks/01-foundations/06-choosing-a-model/`](../../01-foundations/06-choosing-a-model/) —
  the tier axis, which pairs with the effort axis to decide what a decision costs.
