---
title: "Answering a security review: retention, isolation, residency, audit and quotas"
capabilities: [GOV-05, GOV-06, GOV-07]
primary_capability: GOV-05
industry: ENU
industry_scenario: >
  A utility wants to use a hosted model inside its control-room tooling. Approval depends on
  specifics rather than assurances: where inference runs, who is authorised to invoke it,
  what is retained and for how long, whether the traffic can avoid the public internet, and
  what the audit trail records.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-mantle:ListProjects
  - ec2:DescribeVpcEndpointServices
  - cloudwatch:ListMetrics
  - servicequotas:ListServiceQuotas
level: intermediate
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Answering a security review: retention, isolation, residency, audit and quotas

A security review is not won with a datasheet. It is won by answering specific questions
with specific evidence, including the questions where the answer is "no".

Every property below is inspectable from the API, so this recipe asks the platform rather
than quoting a document — and prints the answers in the order a reviewer asks them. Every
AWS call it makes is read-only, and it creates nothing.

| | |
|:--|:--|
| **What you will learn** | How to answer eleven reviewer questions from live API calls, including the two answers that are "no" |
| **Capability** | Retention, authorization, network path, audit and quotas |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Low — one small inference call; everything else is a control-plane read |
| **You will need** | Read-only permissions for the things being inspected |

> **What it does.** Reads the model's retention modes, the PrivateLink endpoint service, the
> CloudWatch namespace and the published quotas, then prints a reviewer's summary table with
> account identifiers masked. **What it creates.** Nothing — every AWS call is read-only.

## What you will build

```
A. retention      the modes this model offers, and what store=False does and does not mean
B. authorization  Projects: the IAM resource that inference is actually granted on
C. network        the PrivateLink endpoint service, its private DNS name, and the FIPS gap
D. audit          the request id, the metric namespace, and what CloudTrail records
E. quotas         published, per model, per Region, adjustable
F. the summary     eleven questions and their answers
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus read-only permissions
  for the things being inspected: `bedrock-mantle:ListProjects`,
  `ec2:DescribeVpcEndpointServices`, `cloudwatch:ListMetrics` and
  `servicequotas:ListServiceQuotas`. Each inspection degrades gracefully if its permission is
  missing, and says which one it needed.
- No data files and no resources.

**Cost: low.** One small inference call; every other call is a read against a control-plane
API. [Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 05-production/03-security-review/python/security_review.py
```

## A. Retention is a per-model property, so ask the model

Retention is governed by a **mode**, and each model declares which modes it will accept.
`GET /v1/models/{id}` returns `allowed_modes` and the current `mode`.

Two things a reviewer needs to hear precisely:

- **`store` defaults to `true` on Bedrock Responses requests**, and a stored response is
  retained by AWS — input and output — for 30 days. That default is what makes a response
  referenceable later, which is how `previous_response_id` works; a workload that has no
  follow-up turn can set `store=False` and keep nothing. Either way it is worth being explicit,
  so the posture is visible in the code rather than inherited.
- **`store=False` is not zero data retention.** ZDR is the mode called `none`, and `store=False`
  only removes the stored response — classifier-flagged traffic can still be retained for abuse
  detection under `default`. If `none` is absent from a model's `allowed_modes` on your account,
  the honest answer is "not enabled here" rather than "impossible": ZDR is granted per account
  and per model, and an approved account sees `none` appear in that same field. Raising it early
  is cheaper than discovering it at sign-off.
- **Content is not shared with OpenAI** under the `default` or `none` retention modes, which is
  usually the first thing a reviewer wants to know and rarely the thing they ask.

The catalogue lives on the open-weight `/v1` router — `GET /openai/v1/models` returns 404 —
and re-pointing must happen **inside** `bedrock(...)`, because a top-level `base_url=`
alongside `provider=` is rejected before any network call:

```python
catalogue = OpenAI(provider=bedrock(
    region=REGION, base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1",
))
```

> **The retention fields are not where you would look for them.** They are a Bedrock
> extension to the OpenAI model object, so the typed SDK class does not declare them:
> reading `model.allowed_modes` returns `None`, which looks exactly like "not offered". They
> arrive nested under `data_retention` in `model_extra`:
>
> ```
> status          'available'
> data_retention  {'allowed_modes': ['provider_data_share', 'default'],
>                  'mode': 'default', 'source': 'model_default'}
> ```
>
> **`none` is absent on this account**,
> so zero retention is not enabled here — and `source` tells you which scope decided,
> `model_default` meaning neither the project nor the account set one.

## B. Inference is authorized on a Project, not on a model

This is the part reviewers find counter-intuitive and architects need. The managed policy for
inference grants `bedrock-mantle:CreateInference` on
`arn:aws:bedrock-mantle:*:*:project/*` — a **project** resource
([policy document](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockMantleInferenceAccess.html)).

So a [project](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html) is the
authorization boundary for inference, and scoping that statement to a single project ARN is
how one workload is isolated from the rest of the account. `CreateProject` returns an `arn` —
a Bedrock addition to the OpenAI response shape — and that ARN is what an IAM policy
references. Tags on the project drive cost attribution.

Two practical notes. Every account has a `default` project and that is where inference lands
when you name none, so a policy that omits it fails even though your code never mentions a
project. And project management is signed HTTP rather than an SDK method — it lives at
`/v1/organization/projects` on the open-weight router, and
[`cookbooks/01-foundations/02-projects/`](../../01-foundations/02-projects/) does the whole
lifecycle, so this review does not repeat it.

What a reviewer needs from this section is the shape of the answer rather than the API calls:

- **Each project is an ARN** you can name in a policy, which is what makes the boundary real.
- **Each carries its own tags**, which is how model spend is attributed to a team.
- **Each carries its own data retention mode**, which overrides the account's.
- **Inference lands in `default`** whenever no project is named.

## C. The network path, including the gap

The endpoint service is `com.amazonaws.{region}.bedrock-mantle` — its own service, not a
`bedrock-runtime` alias. The detail that matters for adoption: **the private DNS name is
identical to the public hostname**, so enabling the endpoint routes existing SDK calls
through the VPC with no code change
([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html)).
Endpoint policies can scope it to `bedrock-mantle:CreateInference`.

```
service name        com.amazonaws.us-east-1.bedrock-mantle
private DNS name    bedrock-mantle.us-east-1.api.aws
DNS verification    verified
endpoint policy     supported = True
IP address types    ['ipv4', 'ipv6']
availability zones  3
```

The recipe then asks for a FIPS variant of the same service and gets `InvalidServiceName`.
**There is no `bedrock-mantle-fips` endpoint service**, while `bedrock-runtime-fips` resolves
normally. A workload with a FIPS 140-2 requirement on the endpoint cannot satisfy it on
mantle today, so a workload carrying that requirement runs its inference through
`bedrock-runtime` on a model served there, or accepts the endpoint as it is and documents the
decision.

## D. What the audit trail records

- **Per request**, an `x-request-id` — the handle to quote in a support case.
- **CloudTrail** records mantle API activity. Web Search retrieval is recorded as **data
  events**, which are **off by default**: enable them for resource type
  `AWS::BedrockWebSearch::Tool` if the trail has to show retrieval, and note that by design
  they do not record query text, returned URLs or page content.
- **CloudWatch** publishes token metrics under the `AWS/BedrockMantle` namespace. Eight
  metric names were present on this account (2026-08-13, `us-east-1`): `Inferences`,
  `InferenceClientErrors`, `InputTokens`, `OutputTokens`, `TotalInputTokens`,
  `TotalOutputTokens`, `BurnDownConsumed` and `EquivalentReservationUnits`. An empty list
  means no traffic has published yet in that Region, not that the namespace is unsupported.
- **There is no cache metric.** For cache accounting, `usage.input_tokens_details` on the
  response is the authoritative source.

## E. Quotas are published and adjustable

Quotas live under service code **`bedrock`** — `bedrock-mantle` is not a Service Quotas
service code — and are named per endpoint and per model. They are **input tokens per minute
and output tokens per minute**, separately, with **no requests-per-minute dimension**, which
is why a 429 is always a token-rate answer rather than a request-rate one. Every mantle quota
is adjustable through AWS Support.

On this account the call returned **20 mantle quotas, all 20 adjustable** (2026-08-13,
`us-east-1`), named `[bedrock-mantle endpoint] Input|Output tokens per minute for <model>`.

Two failure modes that look alike: **429** is your quota, **503** is regional capacity
pressure. Retry both; only the first is worth a quota increase.

## F. The answers

Here is what the script prints, in the order a reviewer asks. Every row was read from an API
rather than from a document, which is what makes it re-checkable the day it changes.

| # | The question | The answer | Read from |
|:--|:--|:--|:--|
| 1 | What is retained, and for how long? | A stored response — input and output — for 30 days. `store` defaults to `true`; a turn with no follow-up can set `store=False` and keep nothing | `GET /v1/models/{id}`, plus the documented default |
| 2 | **Is zero data retention available?** | **No — not enabled on this account.** `allowed_modes` is `['provider_data_share', 'default']`, and `none` is absent. It is granted per account and per model, so this is "not enabled here", not "impossible" | `data_retention` in `model_extra` |
| 3 | Is content shared with the model provider? | No, under the `default` and `none` retention modes | `data_retention.mode`, currently `default` |
| 4 | What authorizes a call? | `bedrock-mantle:CreateInference`, granted on `arn:aws:bedrock-mantle:*:*:project/*` — a **project** resource, not a model | The managed policy document |
| 5 | How is one workload isolated from another? | Scope that statement to a single project ARN. Each project is an ARN a policy can name, and carries its own tags and its own retention mode. Name none and inference lands in `default` | `GET /v1/organization/projects` |
| 6 | Can the traffic avoid the public internet? | Yes, over PrivateLink: `com.amazonaws.us-east-1.bedrock-mantle`, private DNS `bedrock-mantle.us-east-1.api.aws`, verified, endpoint policies supported, IPv4 and IPv6, 3 availability zones. The private name equals the public one, so existing calls need no change | `ec2:DescribeVpcEndpointServices` |
| 7 | **Is there a FIPS endpoint?** | **No.** `bedrock-mantle-fips` returns `InvalidServiceName`, while `bedrock-runtime-fips` resolves normally | The same call, asked twice |
| 8 | What identifies a single request? | An `x-request-id` on every response — the handle to quote in a support case | The response headers |
| 9 | What does the audit trail record? | CloudTrail records mantle API activity. Web Search retrieval is recorded as **data events**, which are off until you enable them for `AWS::BedrockWebSearch::Tool` — and by design they never record query text, returned URLs or page content | CloudTrail configuration |
| 10 | What can be monitored? | Eight metrics under `AWS/BedrockMantle`: `Inferences`, `InferenceClientErrors`, `InputTokens`, `OutputTokens`, `TotalInputTokens`, `TotalOutputTokens`, `BurnDownConsumed`, `EquivalentReservationUnits`. There is no cache metric — use `usage.input_tokens_details` | `cloudwatch:ListMetrics` |
| 11 | What are the limits, and can they be raised? | Input tokens per minute and output tokens per minute, separately, per model and per Region, with no requests-per-minute dimension. 20 mantle quotas on this account, all 20 adjustable through AWS Support | `servicequotas:ListServiceQuotas`, service code `bedrock` |

Rows 2, 5, 6, 10 and 11 are account-specific, so run it against your own account before
quoting any of them.

**The two "no" answers are the reason to run this rather than read a datasheet.** A reviewer told
the truth about two gaps has reason to believe the other nine.

## Production considerations

- **Re-run this before each review.** Every answer is a live property; `allowed_modes` in
  particular is per-model and can change without a documentation update.
- **Scope `CreateInference` to a project ARN** rather than `project/*`, and give each workload
  its own project. That is the isolation story, and it is also the cost-attribution story.
- **Prefer short-term tokens to long-term API keys**, and note that `CallWithBearerToken`
  supports a `bedrock-mantle:BearerTokenType` condition key — the lever for allowing
  short-term credentials while denying long-term ones.
- **Turn on the data events you are relying on.** An audit claim about retrieval is false
  until Web Search data events are enabled.
- **Mask account identifiers in anything you publish**, including logs and screenshots. This
  recipe redacts twelve-digit account numbers from its own output for that reason.
- **Guardrails are a separate call on this endpoint.** If the review expects content
  screening, it is `ApplyGuardrail` alongside inference rather than an inline parameter.
- **Reasoning content is excluded from guardrail evaluation**, which is worth disclosing on a
  reasoning model rather than leaving to be discovered.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider and boto3 both read the
  AWS credential chain; nothing is passed, stored or printed.
- **`store=False` on the single inference call**, so nothing from this run is retained.
- **Every AWS call is read-only** — describe, list and retrieve. Nothing is created, modified
  or deleted.
- **Account identifiers are masked** from any ARN before printing, so the output is safe to
  paste into a review document.
- **No customer or workload data is used.** The one model call sends a fixed sentence.

## Limitations and non-goals

- **Not an assessment.** It gathers evidence; whether that evidence satisfies a particular
  regime is a judgement for the people who own it.
- **One Region, one model.** `allowed_modes` is per model and availability is per Region, so
  the answers are specific to what you pass in.
- **No IAM policy simulation.** It does not test whether your policy actually permits what it
  claims; `iam simulate-principal-policy` is the tool for that.
- **No project is created.** This recipe reads the properties of the one it runs in;
  [`cookbooks/01-foundations/02-projects/`](../../01-foundations/02-projects/) creates and
  archives one.
- **No PrivateLink endpoint is created**, only described. Creating one changes the account's
  network posture and belongs in a change process.
- **No CloudTrail configuration.** It reports what would be needed rather than enabling data
  events, which is a billable, account-wide change.

## Clean up

Nothing to tear down: every call is read-only and `store=False` leaves no stored response.

## Next steps

- [`cookbooks/05-production/02-pii-masking/`](../02-pii-masking/) — the content control that sits alongside these
  platform controls.
- [`cookbooks/05-production/01-prompt-caching/`](../01-prompt-caching/) — where a cached prefix means content is
  held server-side for up to 30 minutes, which belongs in the same data-flow review.
