---
title: "Structured outputs: three levels of guarantee on an extracted record"
capabilities: [STR-01, STR-04]
primary_capability: STR-01
industry: FSI
industry_scenario: >
  A general insurer's intake team receives first-notice-of-loss notes as free text from
  phone calls, broker emails and web forms. Downstream triage is automated, so every note
  has to become a record with the same fields — and a field the note does not support has
  to come back empty rather than guessed, because a wrong reserve figure is a financial
  misstatement.
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
last_validated: 2026-08-12
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Structured outputs: three levels of guarantee on an extracted record

Extraction is the most common thing anyone builds with a language model, and the part that
decides whether it survives production is not the prompt. It is what the model is allowed
to return.

| | |
|:--|:--|
| **What you will learn** | Three levels of guarantee on the same reply, and how to design a schema that can say "the note does not establish this" |
| **Capability** | Structured outputs on the Responses API |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — eight calls, roughly 2,700 input and 1,100 output tokens |
| **You will need** | Inference permission only |

> **What it does.** Extracts a claim record from one insurance note three ways, then runs the
> strictest of them over five deliberately uneven notes. **What it creates.** Nothing —
> `store=False` throughout.

This recipe walks up three levels of guarantee on the same insurance note — free-form
JSON, a strict JSON schema, and a Pydantic model — and then runs the strongest one over
five deliberately uneven notes to show what a schema does and does not buy you.

The short version of the lesson, and the reason the recipe exists: **a schema constrains
shape, never truth.** The interesting design work is leaving your types room to say
"the note does not establish this".

## What you will build

```
A. json_object   valid JSON, but the model names the keys
B. json_schema   your shape, enforced, nullable where evidence may be missing
C. parse()       the schema comes from your Python types; you get an instance back
D. batch         five notes, one contract, and what each one left empty
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`, which `AmazonBedrockMantleInferenceAccess` grants.
  No extra permissions and no AWS resources.
- `pydantic`, already a base dependency of this cookbook.
- Synthetic data in [`data/fnol_notes.jsonl`](data/fnol_notes.jsonl) — five fabricated
  notes for a fictional insurer. The mess in them is deliberate: relative dates
  ("yesterday", "the 3rd of last month"), a policy number written as `mi 4692 c`, two
  contradictory amounts with the note explaining which is the typo, and one note that says
  almost nothing.

**Cost: low.** Eight calls, small inputs, output capped at 800 tokens. The whole run
billed roughly 2,700 input and 1,100 output tokens against
[current rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python \
  02-reasoning-and-output/01-structured-claims-intake/python/claims_intake.py
```

## A. `json_object` gets you parseable, and stops there

```python
text={"format": {"type": "json_object"}}
```

That is the whole configuration, and for a one-off script it is often enough. On the first
note it returned nine keys of its own devising:

```
policy_number, incident_type, location, incident_time, third_party_fault_admitted,
damage, vehicle_drivable, injuries_reported, estimated_repair_cost
```

Sensible keys — and none of them promised. The next note might produce `incident_type` or
`claim_type`, `estimated_repair_cost` or `amount`, a string or a number. A consumer has to
defend against every shape, which means the shape has moved into your error handling
instead of your contract.

## B. `json_schema` with `strict` makes the shape yours

```python
text={"format": {"type": "json_schema", "name": "claim_record",
                 "strict": True, "schema": CLAIM_SCHEMA}}
```

Same note, same model, the fields you asked for:

```
claim_type               'auto'
policy_number            'MI-4471-B'
incident_date            None
estimated_amount_pence   240000
injuries_reported        False
liability_disputed       False
missing_information      ["incident date (only stated as 'yesterday')"]
```

Two things in that output are worth pausing on.

**`240000`.** The note says "2,400 to put right"; the instructions say amounts are in
pence; the schema says `integer`. Currency as an integer in minor units is the difference
between arithmetic you can trust and a float that will eventually embarrass you, and the
schema is where you enforce it.

**`incident_date` is `None`, and the model explained why.** The note says "yesterday". The
model could have picked a date from the note's `received` timestamp, and a non-nullable
field would have forced it to. Because the type is nullable, "I cannot fix this from the
note" was an available answer.

The configuration is echoed back on the response — `response.text.format.type` and
`.strict` — so you can confirm what the service applied rather than assuming.

> **This is not the same feature as Bedrock's `output_config.format`.** Searching the AWS
> docs for structured output leads to
> [Get validated JSON results from models](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html),
> which is native constrained decoding for Claude models on `bedrock-runtime` and is
> rejected here. On the OpenAI models the mechanism is `text.format`, and its reference is
> the [OpenAI platform documentation](https://platform.openai.com/docs).

## C. `responses.parse()` makes your types the schema

Maintaining `CLAIM_SCHEMA` as a dict and a matching Python type is duplication that will
drift. `client.responses.parse()` takes the type:

```python
class ClaimRecord(BaseModel):
    claim_type: Literal["auto", "property", "liability"]
    policy_number: str | None
    incident_date: str | None = Field(description="ISO 8601, or null if not fixed")
    estimated_amount_pence: int | None
    injuries_reported: bool | None = Field(description="null when the note is silent")
    liability_disputed: bool | None
    missing_information: list[str]

typed = client.responses.parse(model=MODEL_ID, input=note, text_format=ClaimRecord)
record = typed.output_parsed          # a ClaimRecord, not a string
```

`record.estimated_amount_pence` is an `int` and `record.claim_type` is one of three known
strings, checked. `Field(description=...)` is not decoration — it lands in the schema the
SDK sends, so it is how you tell the model what "null" means for that field.

Nested models, lists of models and `Literal` enums all round-trip correctly here (verified
2026-08-12, `us-east-1`, `openai.gpt-5.6-terra`), so the shape of your record is not
constrained to something flat.

## D. Five notes, one contract — and this is where schema design shows

```
FNOL-2214  auto      policy MI-4471-B   date —   amount   2,400.00
   injuries_reported=False  liability_disputed=False
FNOL-2215  property  policy mi 4692 c   date —   amount   9,100.00
   injuries_reported=None   liability_disputed=None
FNOL-2216  property  policy —           date —   amount          —
   injuries_reported=None   liability_disputed=None
FNOL-2217  liability policy —           date —   amount  12,000.00
   injuries_reported=True   liability_disputed=True
FNOL-2218  auto      policy MI-5013-A   date —   amount          —
   injuries_reported=True   liability_disputed=None
```

That is what the script prints, one record over two lines.
Here is the same data as a grid, because the pattern worth seeing runs **down** a column and
**across** a row rather than along a record:

| Field | FNOL-2214 | FNOL-2215 | FNOL-2216 | FNOL-2217 | FNOL-2218 |
|:--|:--|:--|:--|:--|:--|
| `claim_type` — the one field that is **not** nullable | auto | property | **property** | liability | auto |
| `policy_number` | MI-4471-B | `mi 4692 c` | — | — | MI-5013-A |
| `incident_date` | — | — | — | — | — |
| `estimated_amount_pence` | 2,400.00 | 9,100.00 | — | 12,000.00 | — |
| `injuries_reported` | False | — | — | True | True |
| `liability_disputed` | False | — | — | True | — |
| **nulls** | **1** | 3 | **5** | 2 | 3 |

`—` is null; `False` is a value. Amounts are printed in pounds from the pence field.
`missing_information` is populated on all five and is the field that names each gap, so a null
is never silent — it is not in the block above because the script prints the record summary
rather than the whole object.

Five results, and four separate lessons.

**Every `incident_date` is null, and that is the correct answer.** Read that row across: five
out of five. No note states a full date — they say "yesterday", "the 3rd of last month",
"28/07". Fixing a year from those would be inference dressed as extraction, and each record
names the gap — `"incident year (only 28/07 provided)"`. That is the nullable design paying for
itself five times out of five.

**FNOL-2217 resolved a contradiction correctly.** The note quotes 12,000 from a
solicitor's letter and mentions that an earlier log of 1,200 was an agent's typo. The
model returned 12,000, which is what the note actually says once you read the
correction — the kind of reading that makes free-text extraction worth doing rather than
regexing for a currency figure.

**FNOL-2216 is the warning.** The note is three sentences of nothing: "some kind of
incident at the property", caller will ring back. Every nullable field came back null,
which is right — and `claim_type` came back `"property"`, which is a guess, because
`claim_type` is the one field in the model that is **not** nullable. It had to pick one of
three enum values, so it picked the one the word "property" suggested. Nothing in the
response marks that value as weaker than the same field on FNOL-2214.

That is the whole trade in one field. A required non-nullable field is a promise that the
value is always knowable. When it isn't, you get a confident guess with no flag on it. If
"unknown" is a real state for a field, it has to be in the type — as `| None`, or as an
extra `unknown` enum member.

**Normalization is still yours.** `mi 4692 c` came back exactly as written, because the
schema asks for a string and that is a string. If policy numbers have a canonical form,
validate against it after extraction; the model is not a substitute for a format check.

## Inspect what happened

The run's totals: eight calls, about 2,700 input and 1,100 output tokens, no tool fees. The
per-note phase averaged 395 input and 142 output tokens — extraction is a cheap workload,
which is why the interesting cost question is what the *records* cost downstream rather
than what the calls cost.

The measure worth building on is not "did it parse". It is **how many fields came back
null, and which ones** — that is a routing signal. FNOL-2216 with five nulls, every nullable
field in the record, goes to a human who calls the claimant back; FNOL-2214 with one null goes
straight to triage.

## Production considerations

- **Route on emptiness, not on validity.** Count nulls and read `missing_information`. A
  record with no amount and no date cannot be reserved against, however well-formed it is.
- **Make "unknown" representable in every field where it is a real state.** The
  `claim_type` guess above is the failure this prevents.
- **Validate after extraction.** Policy-number format, date plausibility, amount ranges —
  a schema guarantees types, not domain validity.
- **Cache the stable prefix.** The instructions and the schema are identical on every
  call; the note is the only thing that changes. That is exactly the stable-prefix,
  changing-suffix shape explicit prompt caching is for.
- **Set `max_output_tokens` with the schema in mind.** A truncated response is not valid
  JSON. These records need a few hundred tokens; a schema with long free-text fields needs
  materially more.
- **Retries are already configured** (`max_retries=3` on the client) because a
  tokens-per-minute quota returns 429 and extraction workloads are bursty by nature.
- **Schema conformance is not a safety property.** A prompt-injected note can still
  produce a schema-valid record; if notes come from outside your organization, screen them
  as content rather than trusting the shape.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS
  credential chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response. Claim notes
  are exactly the kind of content you do not want in a 30-day retention window by default.
- **Inference stays in the Region you name**, which is printed at the top of the run.
- **The notes are fabricated**, including the names, policy numbers and the trading name.
  No real claim, claimant or insurer.
- **Real intake text contains personal data.** This recipe does not mask it — see
  [`cookbooks/05-production/02-pii-masking/`](../../05-production/02-pii-masking/) for screening
  it with Bedrock Guardrails before it reaches the model.

## Limitations and non-goals

- **No accuracy measurement.** Five notes read by eye is a demonstration, not an
  evaluation. A real intake pipeline needs a labelled set and a per-field score.
- **No document input.** These are text notes. Scanned forms and photographs are a
  different problem, and the notes' mess is textual rather than visual.
- **No normalization, deduplication or persistence.** Records print to stdout.
- **No triage decision.** The recipe produces the record a triage rule would read; it does
  not implement the rule.
- **One model, one Region, one day.** Extraction quality varies by tier and by prompt, and
  a single run establishes neither.

## Clean up

Nothing to tear down. On-demand inference creates no resources, and `store=False` means
there is no stored response to delete.

## Next steps

- [`cookbooks/02-reasoning-and-output/02-reasoning-effort-and-verbosity/`](../02-reasoning-effort-and-verbosity/) — the
  other half of `text`: how long the answer is, and how hard the model thinks first.
- [`cookbooks/01-foundations/06-choosing-a-model/`](../../01-foundations/06-choosing-a-model/) —
  whether extraction of this shape needs the mid tier at all.
