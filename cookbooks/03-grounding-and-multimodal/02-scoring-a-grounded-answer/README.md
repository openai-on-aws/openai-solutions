---
title: "Trusting a grounded answer: scoring it against its sources"
capabilities: [GRD-03, GOV-01]
primary_capability: GRD-03
industry: PUB
industry_scenario: >
  A borough council publishes automated answers about a home adaptation grant. An answer
  that overstates an award or invents an appeal deadline is a maladministration risk, so the
  service needs a check that runs on every answer before publication and produces a number
  an auditor can see.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-runtime:ApplyGuardrail
  - bedrock:CreateGuardrail
  - bedrock:CreateGuardrailVersion
  - bedrock:GetGuardrail
  - bedrock:DeleteGuardrail
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-12
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Trusting a grounded answer: scoring it against its sources

Grounding an answer in documents is the easy half. The hard half is knowing whether the
answer that came back actually says what the documents say — and answering that with
something better than a spot check.

[Bedrock Guardrails' contextual grounding check](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
does this with two scores, on any text, from any model:

- **GROUNDING** — is the answer supported by the source you supplied?
- **RELEVANCE** — does the answer address the question that was asked?

They are separate because those are two different ways to be wrong, and this recipe's
measurements show them separating cleanly.

| | |
|:--|:--|
| **What you will learn** | How to score an answer for faithfulness to its sources, where to put the threshold, and why refusals need a different path |
| **Capability** | Contextual grounding checks via `ApplyGuardrail` |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Medium — six model calls plus seven guardrail evaluations over two policies |
| **You will need** | `ApplyGuardrail`, plus permission to create and delete a guardrail |

> **What it does.** Answers four resident questions from a small document set and scores each
> answer before publishing it. **What it creates.** One guardrail, deleted in the final step —
> or set `GUARDRAIL_ID` to reuse your own.

## Screening is a separate call, and that is an advantage

On `bedrock-mantle` the guardrail is not applied inline. You call
[`ApplyGuardrail`](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) as
its own request, which the AWS documentation presents as a first-class option — usable
"without invoking the foundation models" — rather than a fallback. Three consequences
that make it the right shape here:

- **It never touches the inference path.** So it is indifferent to which endpoint or model
  produced the answer, and the same guardrail screens output from anything.
- **It composes for latency.** An inline guardrail is synchronous and adds to response
  time. A separate call can be issued concurrently, or applied only to the answers that
  matter — for a latency-sensitive service that is a better architecture, not a compromise.
- **You get the assessment, not a verdict.** Scores and thresholds come back per filter,
  which is what an audit trail needs and what a bare "blocked" would not give you.

## What you will build

```
A. the guardrail   created here, with both filters and thresholds visible
B. answer + score  four resident questions, each answer graded before publication
C. the range       what an unsupported answer scores, so you can set a threshold
D. refusals        why they score low, and how to route them
E. clean up        the guardrail is deleted
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus **guardrail
  permissions**. Two grants, and the difference matters:
  - `bedrock-runtime:ApplyGuardrail` — to screen text. This is the small one.
  - `bedrock:CreateGuardrail`, `CreateGuardrailVersion`, `GetGuardrail`,
    `DeleteGuardrail` — because this recipe builds its own guardrail and deletes it.

  **If your role only has `ApplyGuardrail`, set `GUARDRAIL_ID`** (and optionally
  `GUARDRAIL_VERSION`) to an existing guardrail carrying a contextual grounding policy, and
  the recipe skips creation and leaves your guardrail alone.
- Synthetic data in [`data/scheme_documents.jsonl`](data/scheme_documents.jsonl) — four
  short passages describing a fabricated grant for a fictional borough.

**Cost: medium, because guardrail evaluation is billed per policy on top of tokens.** Six
model calls with ~450 input tokens each, and seven guardrail evaluations over two
policies. Creating and deleting a guardrail is not itself billed.
[Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python \
  03-grounding-and-multimodal/02-scoring-a-grounded-answer/python/scoring_a_grounded_answer.py
```

## A. The guardrail is part of the recipe

The policy configuration is not setup to be hidden in a shell script — it is the thing that
makes the output interpretable. A score of `0.09` means nothing without the threshold it was
compared against:

```python
bedrock_control.create_guardrail(
    name="cookbook-grounded-answer-check",
    contextualGroundingPolicyConfig={"filtersConfig": [
        {"type": "GROUNDING", "threshold": 0.75},
        {"type": "RELEVANCE", "threshold": 0.75},
    ]},
    ...
)
```

`0.75` is a deliberate choice, not a default: demanding for a citizen-facing answer, higher
than you would set for an internal draft. Both filters are configured because an answer can
be entirely relevant and entirely invented.

## B. Answer, then score

The scoring call is where the qualifiers do the work:

```python
bedrock_runtime.apply_guardrail(
    guardrailIdentifier=GUARDRAIL_ID, guardrailVersion=version,
    source="OUTPUT",
    content=[
        {"text": {"text": CORPUS,   "qualifiers": ["grounding_source"]}},
        {"text": {"text": question, "qualifiers": ["query"]}},
        {"text": {"text": answer}},
    ],
)
```

`grounding_source` marks the text the answer must be faithful to; `query` marks the question
it must address; the unqualified item is the answer under test. Without the qualifiers this
is an ordinary content scan.

Four resident questions:

| Question | GROUNDING | RELEVANCE | Gate |
| --- | --- | --- | --- |
| Private tenant, what could I get for a stairlift? | 0.99 | 1.0 | publish |
| How long for a decision, and how do I appeal? | 0.99 | 1.0 | publish |
| I live in a council flat — do I apply here? | **1.0** | 1.0 | publish |
| Does it cover my garden fence and repainting? | 0.93 | 1.0 | publish |

All four cleared. Two of them are worth noting because the *correct* answer is a "no":
the council-flat question is answered by redirecting to the separate tenants' scheme, and
the fence question by citing the exclusion. Both are grounded refusals of the request while
still being claims **from** the documents — which is exactly why they score high, and it
sets up the distinction in step D.

## C. Where an unsupported answer lands

To place a threshold you need both ends of the range. The recipe scores a hand-written answer
against the same sources — plausible prose, invented figures:

> Yes, private tenants can apply. The maximum award for a stairlift is 25,000 per property
> each year, and there is an additional 3,000 hardship top-up for applicants over 70.
> Decisions are issued within 5 working days.

```
action     GUARDRAIL_INTERVENED
GROUNDING  0.01  (threshold 0.75) → BLOCKED
RELEVANCE  1.0   (threshold 0.75) → NONE
```

**0.01 against 0.93–1.0 for the supported answers** — a wide enough gap that 0.75 is a
comfortable place for the line rather than a finely-tuned one.

And note the split across the two filters. This answer is entirely *relevant*: it addresses
the question asked, in the right shape, with the right fields. It scores one hundredth on
faithfulness. **Relevance alone would have published it**, which is why both filters are
configured.

Four kinds of answer, both thresholds at 0.75, so you can see which axis each one fails on:

| The answer under test | GROUNDING | RELEVANCE | What the gate does | Why it lands there |
|:--|:--|:--|:--|:--|
| The four supported answers, from the step above | 0.93 – 1.0 | 1.0 | publish | Every claim is in the sources, including the two that are grounded refusals of the request |
| Plausible prose with invented figures | **0.01** | 1.0 | held on grounding | Relevant and unfaithful at once. This is the pair the two filters exist to separate |
| The model's own refusal, redirecting elsewhere | **0.09** | 1.0 | held on grounding, though the answer is correct | A refusal makes no claims *from* the source, so a faithfulness check has nothing to measure |
| A bare refusal, with no redirect | 0.63 | **0.11** | held on relevance instead | It fails the other axis: it does not address what was asked |

The first three rows come from the run. The bare refusal was measured separately and is here
because it completes the picture: **the two failure modes are not the same failure**, and a
correct answer can land in either one. That is what makes step D a design decision rather than a
threshold adjustment.

## D. Refusals need a different path

Asked something the documents do not cover — help with heating costs — the model declined and
redirected:

> The Home Adaptation Grant documents do not cover heating costs or winter fuel support.
> This grant is for specified home adaptations… Please contact the Borough's welfare
> support team.

```
GROUNDING  0.09
RELEVANCE  1.0
```

That is a correct answer, and it scores low on grounding, because a refusal makes no claims
*from* the source and a faithfulness check has nothing to measure.
A bare refusal scored 0.63 grounding and 0.11 relevance, failing on the other axis instead.

So the design rule is straightforward: **apply the grounding gate to answers that assert
something, and route refusals separately.** Telling them apart is easy — an `answered: bool`
field on a structured response, of the kind in
[`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/),
tells you which branch you are on before you decide what to score.

Grounding scores are for claims. Used that way the filter is exactly what a citizen-facing
service needs; applied to everything, it holds back the answers that were most careful about
their limits.

## Production considerations

- **Score in parallel with inference where you can.** The screening call is independent, so
  it does not have to be serial. That is the latency advantage of the separate-call shape.
- **Gate claims, route refusals.** See above — a refusal scores low by construction, so it
  needs a separate path rather than the same threshold.
- **Log the scores, not just the verdict.** `GROUNDING 0.93` and `GROUNDING 0.99` both pass
  at 0.75, and the distribution over time is what tells you the corpus is drifting away
  from the questions being asked.
- **Set the threshold from your own answers.** The gap here (0.93 vs 0.01) is wide enough
  that 0.75 is uncontroversial; a domain with heavy paraphrase will crowd the middle, and
  the only way to place the line is to score a sample you have judged by hand.
- **Guardrails are billed per policy evaluated.** Two filters means two evaluations per
  answer. Screening every answer twice — input and output — over five policies is a real
  line item at volume, so screen what needs screening.
- **Reasoning content is not screened.** Guardrails evaluate inputs and responses and
  explicitly exclude reasoning blocks, which on a reasoning model family is worth knowing.
- **This check does not replace citations.** It tells you the answer is supported somewhere
  in the source you passed; it does not tell a reader *which* passage, which is what a
  citation does. Use both.
- **The corpus you pass is the corpus you are judged against.** Passing a truncated set of
  passages makes a correct answer look ungrounded, so the text you score against has to be
  the text the model actually saw.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider and boto3 both read the
  AWS credential chain; nothing is passed, stored or printed.
- **`store=False` on every model call**, so AWS retains neither request nor response.
- **The answer text is sent to `ApplyGuardrail`** on `bedrock-runtime` in the same Region.
  That is a second service seeing the content, which is worth stating in a data-flow review
  even though it stays in-Region and in-account.
- **The guardrail is created and deleted by the recipe**, so no policy configuration is
  left behind in the account.
- **The scheme, the borough and the figures are fabricated.** No real authority, grant or
  resident.

## Limitations and non-goals

- **Retrieval is not part of this recipe.** The passages are supplied. If you use the
  server-side [Web Search](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html)
  tool, retrieved content is injected into context and is not returned to you, so there is
  no source text to pass as a `grounding_source` — grounding checks apply to retrieval you
  control. That is a real architectural constraint and the reason this recipe supplies its
  own corpus.
- **No claim-level attribution.** One score per answer, not per sentence.
- **The scores are not calibrated probabilities.** Treat them as a comparable signal with a
  threshold, not as "93% true".
- **Four questions and two contrasting variants** is enough to show the range and place a
  threshold, not to characterise the filter's accuracy.
- **No human-review workflow.** A held answer prints as `HOLD`; where it goes next is the
  part a real service has to design.

## Clean up

The recipe deletes the guardrail it created, in its final step, and says so. If the run dies
part way, the guardrail is named `cookbook-grounded-answer-check` — find it with
`aws bedrock list-guardrails` and delete it with
`aws bedrock delete-guardrail --guardrail-identifier <id>`. An unused guardrail is not
billed, but it is clutter in an account.

If you supplied `GUARDRAIL_ID`, nothing is deleted.

## Next steps

- [`cookbooks/03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](../01-grounded-regulatory-monitoring/) — where
  the retrieval comes from Bedrock's own web index, and what that costs.
- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
  — the schema that lets you tell a refusal from an answer before you score it.
