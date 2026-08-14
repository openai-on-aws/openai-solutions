# Production

> **What changes when this runs at volume, and what will the security review ask?**

These three recipes are the ones to read before a launch rather than during a prototype. They
cover the two costs that matter at volume — tokens and trust — and the questions an approval
process will put to you.

None of them are about making a model answer better. They are about making the same answer
affordable, defensible and auditable.

## What each one is for

- **Prompt caching** is the largest single lever on the input bill for any workload with a
  stable prefix, and on GPT-5.6 you place the breakpoint yourself, which makes the saving
  deterministic rather than best-effort.
- **PII masking** keeps identifiers out of the model and out of what it writes, using the same
  `ApplyGuardrail` call in front of and behind the request.
- **The security review** answers eleven specific questions from live API calls — retention,
  authorization, network path, audit, quotas — including the two where the honest answer is no.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-prompt-caching/`](01-prompt-caching/) | Cutting agent cost with explicit prompt caching | intermediate | low |
| [`02-pii-masking/`](02-pii-masking/) | Masking patient identifiers before and after the model | intermediate | low |
| [`03-security-review/`](03-security-review/) | Answering a security review: retention, isolation, residency, audit and quotas | intermediate | low |
<!-- END GENERATED: group-index -->

## Running these

```bash
uv sync
uv run python 05-production/01-prompt-caching/python/prompt_caching.py
```

One of the three, the PII recipe, creates a Bedrock guardrail and deletes it, or reuses one
you name in `GUARDRAIL_ID`. The other two create nothing: prompt caching is inference only,
and the security review makes read-only calls.

## Where to go next

- [`cookbooks/01-foundations/02-projects/`](../01-foundations/02-projects/) — the workload
  boundary that a cost report and an access policy both hang off.
- [`cookbooks/03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](../03-grounding-and-multimodal/02-scoring-a-grounded-answer/)
  — the same guardrail API used to score whether an answer is faithful to its sources.
