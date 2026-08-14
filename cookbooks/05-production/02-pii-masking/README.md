---
title: Masking patient identifiers before and after the model
capabilities: [GOV-04]
primary_capability: GOV-04
industry: HCLS
industry_scenario: >
  A clinic summarizes patient telephone notes into a care-coordination queue. Identifiers
  must not reach the model and must not appear in the summary, but the clinical content has
  to survive de-identification well enough for a triage decision.
models: [openai.gpt-5.6-luna]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-runtime:ApplyGuardrail
  - bedrock:CreateGuardrail
  - bedrock:CreateGuardrailVersion
  - bedrock:DeleteGuardrail
level: intermediate
estimated_cost: low
status: validated
last_validated: 2026-08-12
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Masking patient identifiers before and after the model

A clinical note is mostly useful information wrapped around a few identifiers. You want the
first part and not the second, and
[Bedrock Guardrails' sensitive-information policy](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
gives you exactly that: detect personal data, then either **block** the request or
**anonymize** each entity into a placeholder like `{NAME}`.

Because screening on this endpoint is a separate `ApplyGuardrail` call rather than an inline
option, **you decide where it sits** — and the answer is usually both sides:

| | |
|:--|:--|
| **What you will learn** | How to screen identifiers out of a prompt and out of a reply, and how to check what your patterns actually remove |
| **Capability** | Sensitive-information policies via `ApplyGuardrail` |
| **Model** | `openai.gpt-5.6-luna` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Low — one model call and around ten guardrail evaluations |
| **You will need** | `ApplyGuardrail`, plus permission to create and delete a guardrail |

> **What it does.** Masks a clinical call note, summarizes the masked text, screens the summary
> too, then searches the masked notes for identifiers it knows are there. **What it creates.**
> One guardrail, deleted in the final step.

```
note ──► screen (INPUT) ──► masked note ──► model ──► summary ──► screen (OUTPUT) ──► queue
```

The input screen is what stops identifiers reaching the model at all. The output screen is a
different control, not a duplicate: a model can reintroduce an identifier from an earlier
turn, a tool result or a retrieved document.

## What you will build

```
A. the guardrail  six built-in entities plus two regexes
B. screen input   identifiers replaced before the model sees anything
C. summarize      the model works on masked text
D. screen output  the summary screened as well
E. verify         search the masked text for identifiers we know were there
F. clean up       the guardrail is deleted
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus guardrail
  permissions — and note the split, because it decides what a restricted role can run:
  - `bedrock-runtime:ApplyGuardrail` to screen text.
  - `bedrock:CreateGuardrail`, `CreateGuardrailVersion`, `DeleteGuardrail` because the
    recipe builds its own and deletes it.

  **Set `GUARDRAIL_ID` to reuse an existing guardrail** if you only hold `ApplyGuardrail`.
- Synthetic data in [`data/call_notes.jsonl`](data/call_notes.jsonl) — four fabricated
  telephone notes. The identifiers are invented: `555-01xx` numbers, `example.com`
  addresses, and record numbers in a made-up local format. **No real patient data, and none
  should ever be used to test this.**

**Cost: low.** One model call plus around ten guardrail evaluations over a single policy.
Creating and deleting a guardrail is not billed; evaluation is billed per policy configured,
on top of tokens ([rates](https://aws.amazon.com/bedrock/pricing/)).

## Run it

```bash
uv sync
uv run python 05-production/02-pii-masking/python/pii_masking.py
```

## A. Configure per direction, or half of it does nothing

The shape of the configuration is the first lesson:

```python
{
    "type": "NAME",
    "action": "ANONYMIZE",
    "inputAction": "ANONYMIZE",
    "outputAction": "ANONYMIZE",
    "inputEnabled": True,
    "outputEnabled": True,
}
```

**All five fields, deliberately.** With only `action` set, screening behaves inconsistently
between directions — a guardrail configured that way detected nothing on `source="INPUT"`
and masked correctly on `source="OUTPUT"` for the same sentence. With the per-direction
fields set explicitly, one sentence containing a name, email, phone, address and SSN masked
identically both ways. The same fields appear in
[AWS's own example](https://aws.amazon.com/blogs/machine-learning/integrate-tokenization-with-amazon-bedrock-guardrails-for-secure-data-handling/).

### The built-in entity list has a hole where a date of birth should be

The supported types cover names, addresses, emails, phones, ages, national identifiers,
payment details, credentials and more — the full enum comes back in the validation error if
you pass a bad one. There is **no date type at all**: `AGE` exists, nothing matches a date
of birth. For a clinical note that is one of the most identifying fields present.

So this recipe adds two regexes, and the reason is different for each:

```python
("MedicalRecordNumber", r"\b88-\d{5}\b"),   # local format, no built-in could know it
("DateOfBirth",         r"\b\d{2}/\d{2}/\d{4}\b"),  # no built-in type exists
```

## B, C, D. Screen, summarize, screen again

The note goes in:

> Call from Ines Halvorsen (MRN 88-40921), DOB 14/03/1958, about her follow-up after the
> knee replacement. Reports swelling worse in the evenings and pain waking her around 3am…

and reaches the model as:

> Call from {NAME} (MRN {MedicalRecordNumber}), DOB {DateOfBirth}, about her follow-up after
> the knee replacement. Reports swelling worse in the evenings and pain waking her around
> 3am…

The model then summarizes that, at `reasoning.effort: none` because summarizing a short note
needs no deliberation and this runs at volume. **The clinical content survives**: the
swelling pattern, the night pain, the medication intolerance and the driving question are all
still in the summary, which is the point — de-identification did not cost the triage decision
anything.

The output screen found nothing to mask, which is the expected result once the input was
masked. It stays in the pipeline because it is cheap and because it covers a different
failure.

One practical note for a data-flow diagram: the two screens and the model call go to
**different endpoints**. Inference is `bedrock-mantle` through the OpenAI client, while
`ApplyGuardrail` is `bedrock-runtime` through boto3, so the recipe builds two clients. In
day-to-day terms it is all Bedrock, in one Region and one account. It is worth naming because a
guardrail evaluates the text rather than just passing it along, which makes it a second place
the unmasked note is processed.

## E. Check your patterns against your own text

The recipe knows which identifiers are in its own synthetic
notes, so it searches the masked text for them and reports survivors:

```
CN-4471   5 masked  ADDRESS, DateOfBirth, EMAIL, MedicalRecordNumber, NAME
     still present after masking: 555-0142
CN-4472   4 masked  ADDRESS, MedicalRecordNumber, NAME, PHONE
CN-4473   5 masked  EMAIL, MedicalRecordNumber, NAME, PHONE, US_SOCIAL_SECURITY_NUMBER
CN-4474   4 masked  ADDRESS, MedicalRecordNumber, NAME, PHONE
```

Read the two columns against each other:

- **The regexes fired everywhere their pattern appeared** — `MedicalRecordNumber` on all four
  notes, `DateOfBirth` on the one that has one. A regex either matches or it does not.
- **The built-in `PHONE` entity caught three of four.** `555-0142` in CN-4471 survived, while
  the same format was masked in the other three notes. In isolation a short number like that
  is genuinely ambiguous, and detection of built-in entities is inferred rather than matched.

**That contrast is the design guidance**, and it is the main thing to take from this recipe:
write a regex for every identifier format you own and can describe — record numbers, case
references, internal account formats, dates in your house style — and let the built-in entity
types cover the open-ended things you cannot enumerate, like names in free text. Used that way
the two mechanisms complement each other, and a quick check against text whose answers you
know tells you your patterns are right.

## `ANONYMIZE` or `BLOCK`, per entity

Both actions are configured per entity, so the choice is not global:

- **`ANONYMIZE`** replaces the entity and lets the work continue. Right for a name in a note
  you still want summarized.
- **`BLOCK`** refuses the whole request and returns your configured message. Right for
  something that should never have been submitted — a payment card in a clinical note means
  someone pasted the wrong thing, and masking it quietly is worse than stopping.

A useful default is `ANONYMIZE` for what you expect and `BLOCK` for what you do not.

## Masking is irreversible, and sometimes that is wrong

`{NAME}` cannot be turned back into a name. For a summary in a triage queue that is exactly
right. For a workflow where a downstream system needs the real identifier — to book the
appointment the summary recommends — it is a dead end.

The pattern for that case is **tokenization** rather than masking: replace the identifier
with a format-preserving token that an authorized service can reverse, so the model works on
protected data while the trusted ends of the pipeline can still resolve it. AWS documents
this pattern built on the same `ApplyGuardrail` call
([integrating tokenization with Bedrock Guardrails](https://aws.amazon.com/blogs/machine-learning/integrate-tokenization-with-amazon-bedrock-guardrails-for-secure-data-handling/)),
and it is deliberately out of scope here — it needs a tokenization service, which is a
larger architecture than this recipe.

## Production considerations

- **Screen both directions.** The input screen protects the model and your logs; the output
  screen protects the reader. They fail differently.
- **Regex what you can enumerate.** See phase E. This is the difference between "usually
  masked" and "always masked".
- **Verify against known text, repeatedly.** Guardrails policies are backed by models that
  AWS updates without action from you, which is good for coverage and means your assurance
  evidence has a shelf life. Re-run the check on a fixed corpus as a regression test.
- **Screening is billed per policy evaluated.** Two directions over one policy is two
  evaluations per note; at clinical volume that is a real line item, so screen what needs it.
- **Reasoning content is not screened.** Guardrails evaluate inputs and responses and
  explicitly exclude reasoning blocks, so do not treat the trace as covered.
- **`store=False` matters more here than usual.** Bedrock Responses requests default to
  `store: true` with 30-day AWS retention; on clinical text that is a decision you want to
  make deliberately, and the recipe makes it on every call.
- **Placeholders collide.** Two different people in one note both become `{NAME}`, so a
  summary cannot distinguish them. If the note has multiple actors, tokenization or numbered
  placeholders are the way out, not masking.
- **Ask what the model needs.** The cheapest way to protect an identifier is not to send it.
  Masking is for the text you cannot restructure.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider and boto3 both read the
  AWS credential chain; nothing is passed, stored or printed.
- **`store=False` on the model call**, so AWS retains neither request nor response.
- **The unmasked note exists only in the recipe's own process and in the `ApplyGuardrail`
  request.** Both stay in-Region and in-account, and that second service seeing the text is
  worth naming in a data-flow review.
- **The guardrail is created and deleted by the recipe**, leaving no policy behind.
- **All notes, names, numbers and record identifiers are fabricated.** Never run this with
  real patient data.
- **This recipe is not a compliance control by itself.** It demonstrates a mechanism;
  whether a pipeline built on it satisfies a specific regime is a question for the people
  who own that determination.

## Limitations and non-goals

- **No reversibility.** See the tokenization note above.
- **Four notes.** Enough to show the mechanism and one detection gap, not enough to
  characterize recall.
- **English, one locale.** Detection quality varies by language and by identifier
  convention, and the regexes here encode a specific date and record-number format.
- **No consent, retention or access model.** A real clinical pipeline needs all three
  around what this recipe demonstrates.
- **No structured extraction.** The summary is prose; turning a note into fields is
  a different job.
- **The output screen is not tested adversarially.** It found nothing because there was
  nothing; a prompt designed to make the model reproduce an identifier is a different
  experiment.

## Clean up

The recipe deletes the guardrail it created, in its final step. If a run dies part way, the
guardrail is named `cookbook-pii-masking` — find it with `aws bedrock list-guardrails` and
delete it with `aws bedrock delete-guardrail --guardrail-identifier <id>`. If you supplied
`GUARDRAIL_ID`, nothing is deleted.

## Next steps

- [`cookbooks/03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](../../03-grounding-and-multimodal/02-scoring-a-grounded-answer/)
  — the same `ApplyGuardrail` call used for a different policy: scoring whether an answer is
  faithful to its sources.
- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
  — extraction into fields, which is what a triage queue usually wants next.
