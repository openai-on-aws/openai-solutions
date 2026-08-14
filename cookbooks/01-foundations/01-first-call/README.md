---
title: Your first call, and the four permissions it needs
capabilities: [FND-01, FND-02]
primary_capability: FND-01
industry: —
industry_scenario: >
  Cross-industry. The first call any team makes, and the four IAM permissions that
  have to be in place for it to succeed.
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

# Your first call, and the four permissions it needs

You want to call a GPT-5.6 model on Amazon Bedrock and see it work. The good news is that
the code is four lines and needs no API key; the part worth your attention is the handful of
IAM permissions behind it, because when one is missing the error rarely names it.

| | |
|:--|:--|
| **What you will learn** | How to make a Responses API call to a GPT-5.6 model, and what authorizes it |
| **Capability** | The Responses API on the `bedrock-mantle` endpoint |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — one call, capped at 256 output tokens |
| **You will need** | Inference permission and model access. Nothing is created |

> **What it does.** Sends one prompt, prints the answer, then prints the shape of the
> response object and the tokens it billed. **What it creates.** Nothing at all — this is
> on-demand inference with `store=False`, so there is nothing to clean up afterwards.

## The whole call

```python
from openai import OpenAI
from openai.providers import bedrock

client = OpenAI(provider=bedrock(region=REGION))

response = client.responses.create(
    model="openai.gpt-5.6-terra",
    input="Explain prompt caching in two sentences.",
    max_output_tokens=256,
    store=False,
)
print(response.output_text)
```

**There is no API key, no token to mint and no base URL to look up.** The Bedrock provider
derives the regional endpoint for you — `https://bedrock-mantle.us-east-1.api.aws/openai/v1`
— and signs each request with SigV4 using credentials from the standard AWS credential
chain. If `aws sts get-caller-identity` works on your machine, this works too.

![Four lines of Python reach a GPT-5.6 model through the Bedrock provider, which resolves the regional endpoint and signs the request with SigV4. The AWS credential chain feeds the provider, the request reaches the bedrock-mantle endpoint inside the us-east-1 Region where IAM authorizes CreateInference on a project, and the response returns with output text and usage.](images/sdk-to-model-flow.drawio.svg)

*Everything to the right of the boundary happens in the Region you named. The band along the
bottom is the part worth noticing: no API key, no token generator, no proxy and no base URL to
configure appear anywhere in the path.*

That is genuinely all the code. What is worth a few more minutes is the layer underneath —
the permissions that let the call through — because that is where a first attempt usually
stalls, and the errors do not name the thing that is missing.

## Prerequisites

- **An AWS account with access to `openai.gpt-5.6-terra`** in the Region you choose. Check
  [Supported models by AWS Region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html)
  before you pick one, because the three tiers are not served everywhere.
- **Working AWS credentials.** Run `aws sts get-caller-identity` first; if that fails,
  nothing below will succeed.
- **The four checks described in the next section.** Attaching the
  `AmazonBedrockMantleInferenceAccess` managed policy covers the three that are IAM
  permissions; the fourth is model access, which you enable in the Bedrock console.
- **Python 3.10 or newer**, with the `openai[bedrock]` extra. Running `uv sync` installs it.

## Run it

```bash
uv sync
uv run python 01-foundations/01-first-call/python/first_call.py
```

## The four checks your first call passes

Attaching one managed policy covers almost all of this, so you may never need the table below.
It is here for the day you are handed a narrower policy and have to work out which piece is
missing — and the rows are in the order the checks happen, so a symptom points at a stage rather
than at a list.

Verified against the
[`AmazonBedrockMantleInferenceAccess` policy document](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockMantleInferenceAccess.html).

| # | Gate | IAM action or setting | On what | What it is for | Symptom when it is missing |
| --- | --- | --- | --- | --- | --- |
| 1 | **Authentication** | `bedrock-mantle:CallWithBearerToken` | `*` | Permits bearer-token authentication. SigV4 does not use it | Bearer-token authentication is rejected outright |
| 2 | **Subscription check**, first call only | `aws-marketplace:Subscribe` and `ViewSubscriptions` | `*`, gated on `aws:CalledViaLast = bedrock-mantle.amazonaws.com` | The OpenAI models are third-party Marketplace subscriptions | `AccessDenied` on the very first call, and never again |
| 3 | **Inference authorization** | `bedrock-mantle:CreateInference` | `arn:aws:bedrock-mantle:<region>:<account>:project/default` | Authorized on a Project, not a model | `AccessDenied` on the call, with no mention of a project |
| 4 | **Model access** | An account setting, not an IAM action | That model, in that Region | Enabled once per model per Region in the Bedrock console | `ResourceNotFoundException`, which reads like a typo in the model ID |

> **One managed policy covers gates 1 to 3.** `AmazonBedrockMantleInferenceAccess` grants all
> three, which is why most readers never see any of these errors. **Gate 4 is different in
> kind** — model access is a console setting rather than a permission you can attach, so no
> amount of IAM will fix it. That distinction is worth remembering, because the instinct on
> `ResourceNotFoundException` is to go hunting for a missing policy.

Three of those rows are worth a sentence each.

**Inference is authorized on a Project ARN rather than a model ARN.** If you are used to
`bedrock:InvokeModel` on `foundation-model/*`, this is the one that surprises you. Every
account has a `default` project and that is where calls land when you name none, so a policy
that omits `project/default` fails even though your code never mentions a project.

That design is worth more than a footnote, because it is what lets two workloads share an AWS
account with separate permissions and separate cost reporting.
[`cookbooks/01-foundations/02-projects/`](../02-projects/) creates a project, runs inference
inside it, and shows the policy its ARN makes possible.

**The OpenAI models are third-party AWS Marketplace subscriptions.** That explains why a
Marketplace action appears in an inference policy at all, and why its absence bites exactly
once and then never again.

**Web Search lives under a different service prefix.** The gates above cover
inference. Grounding a call with
[Web Search](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html) adds
`bedrock-websearch` actions, which the grounding recipes cover.

## What comes back

`response.output_text` is a convenience accessor over a list of typed items, and it is worth
looking underneath it once so the shape is familiar later:

```
Output items: ['message']
Input tokens:     13
Output tokens:    53
  of which reasoning: 0
Total tokens:     66
```

A **reasoning item** appears alongside the message when the model works something out before
answering, which depends on the prompt. This one does not need it, so only a message comes
back. `usage.output_tokens_details.reasoning_tokens` is where that shows up either way, and
`cookbooks/02-reasoning-and-output/02-reasoning-effort-and-verbosity/`
is the recipe that takes the subject properly.

## Why this recipe sets `store=False`

Responses requests on Bedrock **store the response by default**, and AWS keeps it — input and
output — for 30 days
([reference](https://developers.openai.com/api/docs/guides/amazon-bedrock)). That default is
what makes a stored response referenceable later, and it is the foundation of the
`previous_response_id` pattern that the
[conversation-state recipe](../04-conversation-state/) uses.

This recipe has a single turn and nothing to refer back to, so it opts out with
`store=False` and keeps the account clean. That is the judgement to carry forward: leave
storage on when a later turn will reference the response, and turn it off when it will not.

## Production considerations

- **Pass the Region and the model explicitly, and print them.** The provider will happily
  resolve a Region from the environment, which means the same code can run against a
  different Region on a colleague's machine — and Sol is not served in `us-west-2` at all.
  Being explicit costs one line and removes a whole class of confusion.
- **Treat a 429 as a token-rate signal.** Quotas on this endpoint are input and output tokens
  per minute; there is no requests-per-minute dimension, so a 429 means you are moving too
  many tokens rather than making too many calls. The SDK retries twice by default with
  exponential backoff, which is why this recipe does not hand-roll a loop — raise
  `max_retries` on the client if your traffic is bursty.
- **Scope permission 1 to a single project ARN for a real workload.** That is how you keep two
  teams in one account from reaching each other's inference, and it is the reason the
  permission is shaped that way.
- **Check the model is served where you intend to run** before you promise a Region to anyone.

## Data handling and security

- **The recipe never handles a credential.** The provider reads the AWS credential chain, so
  nothing is passed, stored or printed.
- **`store=False` on the call**, so AWS retains neither the request nor the response.
- **Inference stays in the Region you name**, and the Region is printed at the top of the run
  so there is no doubt which one served it.
- **Nothing leaves the AWS boundary.** The recipe declares no tools and performs no
  retrieval.
- **The prompt is a fixed string** containing no personal or customer data.

## Limitations and non-goals

- **It does not stream.** The answer arrives in one piece; the
  [streaming recipe](../05-streaming/) covers the typed event stream.
- **It does not cover Bedrock API keys**, which are the subject of
  [`cookbooks/01-foundations/03-bedrock-api-key-auth/`](../03-bedrock-api-key-auth/).
- **It does not create a Project.** The call lands in the account's `default` project, which
  is what happens when you name none.

## Clean up

There is nothing to tear down. On-demand inference creates no resources, and `store=False`
means no stored response is left behind. If you experiment with `store=True`, you can remove
what you created:

```python
client.responses.delete(response.id)
```

## Next steps

- [`cookbooks/01-foundations/02-projects/`](../02-projects/) — the resource that
  `CreateInference` is granted on, and how to scope a policy to one workload.
- [`cookbooks/01-foundations/03-bedrock-api-key-auth/`](../03-bedrock-api-key-auth/) — the other supported way
  to authenticate, and why a key left in your environment quietly overrides everything else.
- [`cookbooks/01-foundations/05-streaming/`](../05-streaming/) — the same call, delivered as it is generated.
- [`cookbooks/01-foundations/06-choosing-a-model/`](../06-choosing-a-model/) — which of the three tiers to reach for.
