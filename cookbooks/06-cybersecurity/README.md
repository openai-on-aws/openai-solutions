# Cybersecurity

> **How do I make a first authorized Daybreak call on Amazon Bedrock?**

These recipes introduce the two Daybreak access tiers with small, controlled examples.
Daybreak Blue handles a defensive incident-triage workflow. Daybreak Red validates and
remediates a vulnerability in a synthetic code fixture. Neither recipe connects to a target,
runs model-generated code, or makes changes outside the process.

## Which model should I start with?

Start with Daybreak Blue unless the approved work specifically requires Daybreak Red.

| Model | What the public model card says | Good fit for |
| --- | --- | --- |
| [Daybreak Blue](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-daybreak-blue-56-sol.html) | A specialized model for verified defenders, with a 1-million-token context window | Broad defensive work such as vulnerability discovery, detection engineering, incident response, secure code review, triage, and remediation planning |
| [Daybreak Red](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-cyber.html) | A highly specialized cyber model with a 272,000-token context window | Advanced vulnerability research, controlled exploit reproduction, mitigation development, and validation where Blue is not sufficient |

Both models are multilingual and neither model card lists fine-tuning support. Red is not a
general quality upgrade over Blue: it has a narrower purpose, a separate approval path, and
should be used only inside an explicit authorization boundary.

## Access comes before code

Daybreak is approval-gated. A model ID alone does not grant access.

- Read OpenAI's public [Models and Trusted Access](https://learn.chatgpt.com/docs/cyber-safety)
  guidance.
- Individuals can submit the
  [Trusted Access application](https://chatgpt.com/cyber).
- Organizations can use the
  [enterprise Trusted Access request](https://openai.com/form/enterprise-trusted-access-for-cyber/)
  and coordinate with their OpenAI representative.
- For Bedrock access, OpenAI enrollment is still required. AWS says eligibility and access
  requests can be handled through OpenAI or your AWS account team in the
  [Daybreak on Amazon Bedrock announcement](https://aws.amazon.com/about-aws/whats-new/2026/08/openai-daybreak-red-and-blue-on-amazon-bedrock/).

Daybreak Red requires its own approval and provisioning. Daybreak Blue approval does not
grant Red access. Confirm the approved identity, AWS account, Region, model, project, and
intended product surface before running either recipe.

The AWS identity also needs `bedrock-mantle:CallWithBearerToken` to derive a short-term
credential and `bedrock-mantle:CreateInference` on the intended project. The
`AmazonBedrockMantleInferenceAccess` managed policy includes both and is a straightforward
starting point; use a narrower customer-managed policy where appropriate.

### Verify the AWS identity first

The recipes use the standard AWS credential chain. If you use a named profile, select it,
then confirm the AWS account and role before continuing:

```bash
export AWS_REGION=us-east-2
# Optional when using a named local profile:
export AWS_PROFILE=your-profile-name
aws sts get-caller-identity
```

Do not continue if the identity is unexpected. Each recipe then calls the Mantle Models API
at `https://bedrock-mantle.us-east-2.api.aws/v1/models` and checks for the exact model ID.
Discovery does not prove inference access, so a small Responses API request follows before
the workload. That successful inference is the definitive access check.

## Keep customer data out

**Do not use customer code, logs, credentials, indicators, personal data, or production
system details in these getting-started examples.** The committed fixtures are fabricated.
Keep using synthetic or explicitly de-identified material until your organization's data
owner, security team, and Daybreak approval all authorize a specific workload.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-daybreak-blue-incident-triage/`](01-daybreak-blue-incident-triage/) | Turning synthetic identity events into an evidence-based incident brief | beginner | low |
| [`02-daybreak-red-vulnerability-validation/`](02-daybreak-red-vulnerability-validation/) | Reproducing a toy path-boundary flaw safely, then designing a patch and tests | intermediate | low |
<!-- END GENERATED: group-index -->

## What is in the notebooks?

The Blue notebook loads five fabricated identity events, asks for an evidence-linked incident
brief, and ends with a short analyst review checklist. The Red notebook reads an intentionally
vulnerable function as text, defines the allowed and prohibited work, and asks for a minimal
reproduction, defensive patch, and focused regression tests. Neither notebook gives the
model tools or executes its recommendations.

Before either workload request, one cell confirms that the exact model is returned by
Mantle discovery and a second sends a short, synthetic `READY` prompt. The latter is a real,
billable inference request using the same model, Region, endpoint, and credentials; an
access or configuration error stops the notebook there. Each recipe also includes a plain
Python script with the same fail-fast checks and workload request. Notebook outputs are
cleared in the repository.

## Run an example

From `cookbooks/`:

```bash
uv sync --group cybersecurity
uv run --group cybersecurity python \
  06-cybersecurity/01-daybreak-blue-incident-triage/python/incident_triage.py
```

Both recipes mint refreshable short-term Bedrock credentials from the standard AWS
credential chain with `aws-bedrock-token-generator`; no key is stored in source. They use
the documented `BedrockOpenAI` client for inference, set `store=False`, and default to
`us-east-2` (Ohio). Set `AWS_REGION` to use another approved Region. The corresponding
Mantle paths are `/v1` for discovery and `/openai/v1` for inference. `store=False` is a
request setting, not a grant of Zero Data Retention. Check current model availability and
retention terms before running.
