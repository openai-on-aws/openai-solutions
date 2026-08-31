---
title: "Projects: the resource that authorizes inference and attributes cost"
capabilities: [FND-08, GOV-06]
primary_capability: FND-08
industry: —
industry_scenario: >
  Cross-industry. Two teams share one AWS account and need separate boundaries for access and
  for cost, without the overhead of separate accounts. On the mantle endpoint that boundary is
  a Project.
models: [openai.gpt-5.6-luna]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-mantle:CreateProject
  - bedrock-mantle:ListProjects
  - bedrock-mantle:GetProject
  - bedrock-mantle:ArchiveProject
level: beginner
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Projects: the resource that authorizes inference and attributes cost

Every call you have made so far landed in a project, whether you knew it or not. The first-call
recipe mentioned this in passing — `bedrock-mantle:CreateInference` is granted on a **project
ARN** rather than a model ARN — and this recipe is where that becomes useful rather than
surprising.

| | |
|:--|:--|
| **What you will learn** | What a Project is, how to create one with cost-allocation tags, how to set its data retention, and how to scope an IAM policy to it |
| **Capability** | [Projects](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html) on the `bedrock-mantle` endpoint |
| **Model** | `openai.gpt-5.6-luna` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — two tiny calls. Projects themselves are free |
| **You will need** | Permission to create and archive projects, plus inference |

> **What it does.** Lists the projects in your account, creates one with cost-allocation tags,
> runs inference inside it two different ways, and prints the IAM policy its ARN makes
> possible. **What it creates.** One project, archived in the final step — set `KEEP_PROJECT=1`
> to leave it in place.

## What a Project is

A Project is a **logical boundary for a workload** inside a single AWS account: an application,
an environment, an experiment. It gives you two things that are otherwise awkward to arrange
([reference](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html)):

- **Access isolation.** A project is an IAM resource, so a policy can permit inference in one
  project and nowhere else.
- **Cost attribution.** A project carries AWS tags, so Cost Explorer can group model spend by
  team, environment or cost centre.

The comparison that makes this land is with a separate AWS account. Accounts are billing and
ownership boundaries at the infrastructure level, and standing one up per workload brings
cross-account roles, resource sharing and account sprawl. A project is created in one API call
and gives you the workload boundary without any of that.

**Every account starts with a `default` project**, and that is where inference lands when you
name none — including every other recipe in this cookbook. So you are already using the
feature; creating your own is how you start benefiting from it.

> **Projects are one of several cost controls on Bedrock.** For the full picture — what you can
> track, attribute and cap — see
> [Cost management for Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-management.html).

## Prerequisites

- **The [prerequisites in the cookbooks README](../../README.md)**, plus permission to manage
  projects: `bedrock-mantle:CreateProject`, `ListProjects`, `GetProject` and `ArchiveProject`.

  Note the credential caveat if you are using a **long-term** Bedrock API key: its default
  policy allows only get and list on projects, not create, update or archive. Use a short-term
  key or SigV4, or attach the additional permissions.
- **Working AWS credentials.** The recipe signs its own requests, so
  `aws sts get-caller-identity` must succeed.

## Run it

```bash
uv sync
uv run python 01-foundations/02-projects/python/projects.py
```

## The Projects API is on the `/v1` router, and it is plain HTTP

Two practical facts shape the code, and both are worth knowing before you go looking:

**The OpenAI SDK does not expose project operations.** So the recipe builds and signs the
requests itself. It is standard AWS work — botocore signs for service `bedrock-mantle` with
whatever credentials the environment already has — and it is all in one helper you can lift:

```python
request = AWSRequest(method=method, url=url, data=payload,
                     headers={"Content-Type": "application/json"} if payload else {})
SigV4Auth(CREDENTIALS, "bedrock-mantle", REGION).add_auth(request)
```

**The path is `/v1/organization/projects`**, on the open-weight router. The OpenAI-model router
`/openai/v1` returns `404` for it, which is easy to trip
over given every other call in this cookbook goes to `/openai/v1`.

| Operation | Call |
| --- | --- |
| List | `GET /v1/organization/projects` |
| Create | `POST /v1/organization/projects` |
| Retrieve | `GET /v1/organization/projects/{id}` |
| Archive | `POST /v1/organization/projects/{id}/archive` |

## Creating one, and why the tags matter

```python
projects_api("POST", body={
    "name": "cookbook-support-assistant",
    "tags": {
        "Project": "SupportAssistant",
        "Environment": "Sandbox",
        "Owner": "TeamAlpha",
        "CostCenter": "21524",
    },
})
```

The response:

```
id              proj_5ht6vmk4cnu6yfmc345k
arn             arn:aws:bedrock-mantle:us-east-1:<account>:project/proj_5ht6vmk4cnu6yfmc345k
status          active
object          organization.project
data_retention  {'mode': 'inherit'}
```

**Set the tags at creation, using keys your finance team already reports on.** Tags are what
Cost Explorer groups by, so this single field is what turns a project from a permissions
boundary into a cost centre. `CostCenter`, `Environment` and `Owner` are the usual three;
whatever you choose, choose it before the spend starts, because a tag applied later does not
retroactively label yesterday's usage.

Two more fields to notice. **`arn` is a Bedrock addition** to the OpenAI response shape, and it
is the reason this recipe exists — see the next section. And **`data_retention: inherit`** is the
starting point for the retention section below.

## Associating a call with a project

Two ways, and the choice is about how your application is shaped:

```python
# One service, one project — set it once on the client.
client = OpenAI(provider=bedrock(region=REGION), project=project_id)

# One process, many tenants — set it per request.
client.responses.create(..., extra_headers={"OpenAI-Project": project_id})
```

Both return `200`. A project id that does not exist gives a clean
`404 not_found_error` naming the project ARN it looked for, which is a helpful error rather
than a silent fallback to `default`.

## Data retention is a project setting, not a request parameter

A project carries its own **retention mode**, so you set it once here rather than on every
call. The effective mode for a request is the first non-`inherit` value of **project →
account → the model's own default**, which means a project can tighten or relax what the
account says.

There are four modes:

| Mode | Behaviour |
| --- | --- |
| `inherit` | Defer to the account, then to the model. This is what a new project starts as |
| `default` | The model's own retention policy applies |
| `provider_data_share` | AWS may retain data and share it with the model provider, which some models require before they can be used at all |
| `none` | Zero data retention |

Setting it is one call:

```python
projects_api("POST", f"/{project_id}", body={"data_retention": {"mode": "default"}})
```

### Which mode works with the OpenAI models

Each model declares the modes it accepts in `allowed_modes`, and a mode outside that list does
not silently retain less — it makes the model **unavailable**. The recipe shows both outcomes
on the same project, with `openai.gpt-5.6-luna`:

```
project mode 'none'      → model status 'unavailable'
                           allowed_modes ['provider_data_share', 'default']
                           reason: This model is not available under data retention mode 'none'.
                           inference: 400 validation_error

project mode 'default'   → model status 'available'
                           effective 'default' (source: 'project')
                           inference: 200
```

Two separate things happen there, and keeping them apart is what makes the outcome predictable.
First the effective mode is **resolved**, project to account to model default. Then that mode is
**checked** against the model's `allowed_modes`:

| Project mode | Account mode | Effective mode | `source` | Outcome |
|:--|:--|:--|:--|:--|
| `inherit` | `inherit` | the model's own default | `model_default` | available, `200` |
| `inherit` | `default` | `default` | `account` | available, `200` |
| `default` | anything | `default` | `project` | available, `200` |
| `none` | anything | `none` | `project` | available and `200` if `none` is in this model's `allowed_modes`, otherwise unavailable and `400 validation_error` |

The last row is the one to internalize, and the first two follow from the resolution order above
rather than from a measurement. **`source` is the field to read when the effective mode is not
the one you set** — it names the scope that decided, so `'project'` confirms your setting took
effect rather than the account's.

**Read `allowed_modes` rather than assuming, because it is per model *and* per account.** On a
standard account the GPT-5.6 models offer `default` and `provider_data_share`, so a project set
to `none` stops them working.

**`none` is reachable, though.** Zero data retention is granted per account and per model: if
your workload requires it, AWS evaluates eligibility, and **an approved account sees `none`
appear in that model's `allowed_modes`**
([reference](https://developers.openai.com/api/docs/guides/amazon-bedrock)). So the check the
recipe performs is also how you confirm whether your account already has it — do not conclude
from someone else's output that the answer is no for you.

Two more facts belong next to this:

- **AWS does not share request or response content with OpenAI** when the effective retention
  mode is `default` or `none`.
- **Under `default`, retention is narrow rather than absent.** Classifier-flagged traffic is
  kept up to 30 days for automated offline abuse detection, and a stored response is kept for
  30 days so you can retrieve or reference it. Setting `store: false` removes the second but not
  the first — which is exactly why `store=False` is not ZDR.

There is also a separate control worth knowing by name.
[Zero operator access](https://aws.amazon.com/blogs/machine-learning/exploring-the-zero-operator-access-design-of-mantle/)
means AWS operators have no technical mechanism to sign in to the underlying compute or reach
customer data, including prompts and completions. It is independent of retention mode: ZOA is
about who *can* look, retention is about what is *kept*.

The full reference, including account-level configuration and the
`bedrock-mantle:DataRetentionMode` condition key that enforces a mode across an organisation
with an SCP, is
[Data retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html).

## What the ARN is for

This is the part worth carrying away. Because a project is a resource, it can appear in a
policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "InferenceInThisProjectOnly",
    "Effect": "Allow",
    "Action": "bedrock-mantle:CreateInference",
    "Resource": "arn:aws:bedrock-mantle:us-east-1:<account>:project/proj_5ht6..."
  }]
}
```

An identity holding that policy can run inference in that project and nowhere else in the
account.

**That is the difference between a project and a tag.** A tag describes a resource; a project
*is* the resource, so it can carry permissions. Two teams sharing one account get a project
each, and neither can spend the other's quota or reach the other's stored responses. It is
also why the managed inference policy grants `CreateInference` on `project/*` — broad enough to
work out of the box, and the first thing to narrow for a real workload.

![Inside one AWS account, two projects sit either side of a trust boundary: support-assistant and payments-api-prod. Team Alpha's role reaches its own project and gets 200, and is denied with AccessDenied across the boundary; the Payments role behaves the same way in reverse. Both projects reach the same model, openai.gpt-5.6-terra, because the project is the authorization boundary rather than the model.](images/two-workloads-two-boundaries.drawio.svg)

*The two denied arrows are the whole point: each role holds a policy scoped to one project ARN,
so the isolation is enforced by IAM rather than by convention. Note that both projects reach the
same model — a project does not contain models, it is what the call is authorized against.*

## Archiving is the delete

```
status       archived
archived_at  1786614394
```

Archiving retires a project without erasing it: the record stays, so historical cost data keeps
its project attribution, and no new inference can run in it. A deleted project would take its
billing history with it.

## Production considerations

- **One project per workload and environment**, not per team. `payments-api-prod` and
  `payments-api-staging` want different quotas, different policies and separate lines in a cost
  report, even though the same people own both.
- **Tag at creation.** A tag added later does not relabel spend that already happened.
- **Narrow `CreateInference` from `project/*` to a specific ARN** in any policy that matters.
  That single change is what makes the boundary real.
- **Give each project its own credential.** A project boundary with one shared role that can
  reach every project is a boundary on paper.
- **Archive rather than abandon.** An unused active project is not billed, but it is one more
  thing in a list someone has to reason about during a review.
- **Cost attribution needs the tags to be activated** as cost allocation tags in Billing before
  they appear in Cost Explorer. Creating the project is half the job.

## Data handling and security

- **No credential is handled by the recipe.** botocore and the Bedrock provider both read the
  AWS credential chain; nothing is passed, stored or printed.
- **Account identifiers are masked** from every printed ARN, so the output is safe to paste
  into a document or a ticket.
- **`store=False` on both model calls**, so AWS retains neither request nor response.
- **The project is archived in the final step**, unless you ask to keep it.
- **The project name and tags are fabricated**, and the two prompts contain no personal data.

## Limitations and non-goals

- **It does not show Cost Explorer.** Activating cost allocation tags and reading a cost report
  are Billing console tasks, and the numbers only appear after usage accrues.
- **It does not set a budget or an alarm.** Projects make spend attributable; acting on that
  attribution is a separate exercise, and the production group is where it belongs.
- **It does not update or re-tag an existing project.** The API supports it; the recipe covers
  create, use and archive.
- **It does not set account-level retention.** The recipe sets the project scope only;
  `PUT /v1/data_retention` and the SCP condition key are described rather than exercised.

## Clean up

The recipe archives the project it created, in its final step. If you set `KEEP_PROJECT=1`, or
a run dies partway, archive it yourself:

```bash
curl -X POST "https://bedrock-mantle.us-east-1.api.aws/v1/organization/projects/<id>/archive" \
  --aws-sigv4 "aws:amz:us-east-1:bedrock-mantle" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY"
```

An active project with no usage costs nothing, so a forgotten one is untidy rather than
expensive.

## Next steps

- [`cookbooks/01-foundations/01-first-call/`](../01-first-call/) — the four permissions, one of
  which is the `CreateInference` grant this recipe scopes down.
- [`cookbooks/01-foundations/03-bedrock-api-key-auth/`](../03-bedrock-api-key-auth/) — credentials, including
  why a long-term key cannot create a project without extra permissions.
- [`cookbooks/05-production/`](../../05-production/) — the other two levers a launch is judged
  on: what a stable prefix costs once it is cached, and keeping identifiers out of the model.
