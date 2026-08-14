---
title: "Choosing a model: the same prompt on Luna, Terra and Sol"
capabilities: [FND-06]
primary_capability: FND-06
industry: RCG
pins_models: true
industry_scenario: >
  An online grocery retailer checks basket totals against its pricing rules. A wrong
  total is a refund and a complaint, so this is a task where the model choice has to be
  made on evidence rather than on the tier names.
models: [openai.gpt-5.6-luna, openai.gpt-5.6-terra, openai.gpt-5.6-sol]
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

# Choosing a model: the same prompt on Luna, Terra and Sol

The GPT-5.6 family on Bedrock is three models — Luna, Terra and Sol — sharing one API, one
1,050,000-token context window and one set of parameters
([model cards](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards-openai.html)).
Moving between them is a one-line change, which is a real strength: you can start on the
cheap tier and escalate without rewriting anything.

It also makes it tempting to pick a tier from its description. This recipe gives you a way
to pick it from evidence instead.

| | |
|:--|:--|
| **What you will learn** | How to compare the three tiers on a task with a checkable answer, and a procedure for choosing one for your own workload |
| **Capability** | Model selection across the GPT-5.6 family |
| **Models** | `openai.gpt-5.6-luna`, `-terra`, `-sol` |
| **Region** | `us-east-1` or `us-east-2` — Sol is not served in `us-west-2` |
| **Level** | Beginner |
| **Cost** | Low — three calls, around 2,150 tokens in total |
| **You will need** | Inference permission and access to all three models |

> **What it does.** Sends one pricing question to all three models and checks each answer
> against a committed Python function. **What it creates.** Nothing — `store=False`
> throughout, and the recipe never executes anything a model wrote.

Here is the smallest demonstration that it does. One prompt — a pricing function and a
basket — sent to all three, each asked for the total in cents and nothing else:

```
Basket: BSK-05 — subtotal lands just under the threshold, so shipping applies
Correct answer, from the committed function: 3674 cents

openai.gpt-5.6-luna   ←  2582 cents   wrong
openai.gpt-5.6-terra  ←  2582 cents   wrong
openai.gpt-5.6-sol    ←  3674 cents   correct
```

Three things worth taking from three numbers:

- **The answers differ**, so the tier is a real decision rather than a cost dial.
- **The two cheaper models agree with each other and are both wrong.** Agreement between
  models is not evidence of correctness — worth remembering before building a cheap-model
  consensus check.
- **A wrong answer here is not an arithmetic slip.** Asked separately to show their
  working, Luna and Terra both applied the multibuy credit to a line that is *not* flagged
  `multibuy` — the function credits only lines that are, via `if line.get("multibuy")` —
  while Sol read the guard. Every model got `1149 × 3 × 95% = 3274.65 → 3275` right. What
  separated them was reading the code precisely.

The reply is a bare integer on purpose, so reading it needs no parsing and the recipe does
not have to introduce anything you have not met yet. Constraining a reply to a schema is
the better tool once you are doing this for real; that is structured output, and it belongs
with the reasoning-and-output group rather than in foundations.

Note also that you cannot see the models' internal reasoning on this endpoint: the
reasoning item carries encrypted content and its `summary` comes back empty even when you
ask for one (checked 2026-08-12). The token counts tell you how much thinking happened;
if you want an explanation you can read, ask the model to write one as ordinary output.

> **This is a probe, not an evaluation.** One prompt on one basket cannot rank models,
> and it is not meant to. The point is to show you that the outputs diverge on a task
> with a checkable answer, so that you measure your own task across the three rather than
> choosing from the tier names. A comparison that genuinely exercises the flagship needs
> harder, longer work — a one-shot coding challenge run across all three is planned for
> the agents group, where an agent loop and tools make the difference visible.

## How the answer is checked

The prompt shows the model [`data/pricing_engine.py`](data/pricing_engine.py) and asks
what `basket_total_cents` returns for one basket, as a bare integer. **Ground truth is
that function**, so nothing is adjudicated by a judge model and no rubric is involved —
and the recipe never executes anything a model wrote, only its own committed code. An
empty or non-numeric reply is printed as-is and counted wrong rather than being patched
over.

The function accumulates the ordering decisions a real pricing engine does: a percentage
discount rounded half-up per line, a multibuy credit computed from the *discounted* unit
price, a free-shipping test on the subtotal *before* the voucher, and the voucher clamped
at zero with shipping added last. Each rule is reasonable; together they are hard to
simulate in your head, which is what makes the task discriminating without being long.

`data/baskets.jsonl` holds six baskets. Change `BASKET_ID` in the script to try another —
`BSK-04` and `BSK-06` are the ones where the voucher interacts with the shipping
threshold.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md): a Region with model
  access, and IAM permissions for inference on `bedrock-mantle`.
- **A Region where all three models are served** — `us-east-1` or `us-east-2`. Sol is not
  served in `us-west-2`, where the same call returns
  `404 not_found_error: The model 'openai.gpt-5.6-sol' does not exist` (verified
  2026-08-11). Availability is not uniform, so check
  [Supported models by AWS Region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html)
  before designing around a tier: a workload pinned to one Region for residency reasons
  may have fewer candidates than the family has members.
- Synthetic data in [`data/`](data/) — a fabricated pricing engine and baskets for a
  fictional retailer.

**Cost:** low. Three calls, around 2,150 tokens in total. See
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 01-foundations/06-choosing-a-model/python/choosing_a_model.py
```

## Choosing a tier for real

The measurement this recipe is too small to make, stated as the procedure instead:

![A top-to-bottom flow for choosing a tier. First, which Regions must this run in, noting that Luna and Terra are served in us-east-1, us-east-2 and us-west-2 while Sol is served in us-east-1 and us-east-2. Then define the quality bar in business terms. Then measure Luna against the bar on your own labelled set. If it clears the bar, ship on Luna. If not, measure Terra and then Sol, looping back to the same decision; if it still does not clear, consider splitting the workload between a cheap tier for routing and a strong tier for the fraction that matters. A dashed arrow returns to the measurement step whenever a new model ships.](images/choosing-a-tier.drawio.svg)

*The written steps below are the authority; the diagram is the version to put on a slide in a
design review. The two things it makes obvious are that escalation is a loop rather than a
ladder, and that "ship on Luna" is a success state rather than a compromise.*

1. **Filter by Region first.** Residency requirements are not negotiable, and model
   availability is not uniform.
2. **Write the bar down in business terms** before looking at any model — "no incorrect
   basket total", "every high-severity ticket routed correctly". A bar defined after
   seeing the scores is not a bar.
3. **Start at Luna.** On easy, high-volume work the tiers often tie, and at volume that
   tie is worth real money.
4. **Escalate only where a measurement says you must**, on enough cases that one answer is
   not a large fraction of the score, and repeat each run. On a handful of cases the
   variation within one model can be as wide as the gap between two of them.
5. **Use different tiers for different steps.** A cheap model routing and a strong model
   adjudicating the small fraction that matters is the normal end state, not a compromise.
6. **Re-run when a model ships**, which on Bedrock is every few weeks. That is why this is
   a script rather than a table.

This is the same shape as the OpenAI Cookbook's
[Practical Guide for Model Selection](https://developers.openai.com/cookbook/examples/partners/model_selection_guide/model_selection_guide),
which is worth reading for the framework; what is Bedrock-specific is step 1.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS
  credential chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **Inference stays in the Region you name**, which is printed at the start.
- **The recipe never executes model output.** The pricing function is committed code the
  model only reads.
- **The data is fabricated** — an invented retailer, invented SKUs, no personal data.

## Limitations and non-goals

- **One prompt, one basket, one run per model.** This is a probe. Do not cite these
  results as model capabilities.
- **The printed working is the model's own account of its answer, not its reasoning
  trace.** The internal trace is not readable on this endpoint, and a written explanation
  can rationalize as easily as it can explain — treat it as a debugging aid, not as
  evidence of how the answer was produced.
- **No latency comparison.** This recipe does not time the models. The published
  positioning is the guide — Luna is the fast, low-cost tier, Terra the general-purpose
  middle, Sol the largest — and anything finer has to be measured on the account, Region
  and payload shape you will actually run.
- **No cost figures**, because per-tier rates change; the script prints token counts and
  the [pricing page](https://aws.amazon.com/bedrock/pricing/) has the rates.
- **The task is deliberately small and is not what the flagship is for.** Sol targets
  long-horizon agentic work — multi-step coding, autonomous investigation. A one-shot
  coding challenge across the three tiers is planned for the agents group.
- **Does not test image input**, which all three models accept.
- **Does not tune reasoning effort**, which moves accuracy on a single tier and is its own
  subject.

## Clean up

Nothing to tear down. On-demand inference creates no resources, and `store=False` means
there is no stored response to delete. Importing the pricing module leaves a
`data/__pycache__/` directory behind, which git ignores and you can delete.

## Next steps

- [`cookbooks/01-foundations/05-streaming/`](../05-streaming/) — what the reader sees while any of the three is
  working.
- [`cookbooks/03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](../../03-grounding-and-multimodal/01-grounded-regulatory-monitoring/) —
  giving the model current information, which changes what any tier can answer.
