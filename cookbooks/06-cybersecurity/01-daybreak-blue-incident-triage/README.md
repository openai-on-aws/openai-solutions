---
title: Triage a synthetic cloud identity incident with Daybreak Blue
capabilities: [CYB-01]
primary_capability: CYB-01
industry: TMT
industry_scenario: >
  A security operations team receives a short sequence of cloud identity events and needs
  an evidence-based incident brief before an analyst decides what to contain.
models: [openai.gpt-daybreak-blue-5.6-sol]
region: us-east-2
apis: [responses]
languages: [python]
dependency_groups: [cybersecurity]
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-mantle:CallWithBearerToken
level: beginner
estimated_cost: low
status: validated
last_validated: 2026-09-01
validated_with:
  python: "3.12"
  openai: "2.53.0"
  aws-bedrock-token-generator: "1.1.0"
---

# Triage a synthetic cloud identity incident with Daybreak Blue

Daybreak Blue is the starting tier for most authorized defensive work. This recipe gives it
five fabricated cloud identity events and asks for an incident brief that separates evidence
from inference, recommends reversible containment, and calls out what the analyst still
needs to collect.

| | |
|:--|:--|
| **What you will learn** | How to frame a bounded defensive investigation and obtain an evidence-linked triage brief |
| **Model** | `openai.gpt-daybreak-blue-5.6-sol` |
| **Inference provider** | Amazon Bedrock |
| **Region** | `us-east-2` (Ohio) by default; change `AWS_REGION` to use another approved Region |
| **Discovery endpoint** | `https://bedrock-mantle.us-east-2.api.aws/v1` |
| **Inference endpoint** | `https://bedrock-mantle.us-east-2.api.aws/openai/v1` |
| **Level** | Beginner |
| **Cost** | Low — one small access check plus one request over five short events |
| **You will need** | Daybreak Blue approval, Bedrock model access, `bedrock-mantle:CallWithBearerToken`, and `bedrock-mantle:CreateInference` |

> **What it does.** Verifies basic model inference, reads synthetic events, then requests and
> prints an incident brief. **What it creates.** Nothing; both requests use `store=False`.

## About Daybreak Blue

AWS describes Daybreak Blue as a specialized OpenAI model for verified defenders conducting
advanced, authorized cybersecurity work. Its public
[model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-daybreak-blue-56-sol.html)
lists a 1-million-token context window and supported use cases including vulnerability
discovery, detection engineering, and incident response. The model is multilingual and does
not support fine-tuning.

Blue is the sensible first choice for most defensive workflows: reviewing supplied evidence,
finding and prioritizing vulnerabilities, drafting detections, building incident timelines,
and proposing remediations for a human to verify. Use Red only when the approved task
genuinely requires controlled vulnerability reproduction or similarly advanced research.
Large context can help with substantial evidence sets, but it does not remove the need to
minimize data or keep customer data out of this getting-started example.

## Get access first

Access is not automatic:

1. Read OpenAI's [Trusted Access for Cyber](https://learn.chatgpt.com/docs/cyber-safety)
   guidance.
2. Apply as an [individual](https://chatgpt.com/cyber) or use the
   [enterprise request form](https://openai.com/form/enterprise-trusted-access-for-cyber/).
3. Coordinate Bedrock enablement through OpenAI or your AWS account team, as described in
   the [AWS launch announcement](https://aws.amazon.com/about-aws/whats-new/2026/08/openai-daybreak-red-and-blue-on-amazon-bedrock/).
4. Confirm the model appears for the approved AWS account and Region. The
   [AWS model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-daybreak-blue-56-sol.html)
   is the public reference for the Bedrock model ID.

Approval is tied to the approved identity, organization or project, model, and product
surface. Do not assume approval in one environment carries into another.

## What is in this recipe?

- [`data/identity_events.jsonl`](data/identity_events.jsonl) contains five invented events
  covering a suspicious sign-in, credential changes, and follow-on activity.
- [`python/incident_triage.ipynb`](python/incident_triage.ipynb) derives refreshable
  short-term Bedrock credentials from the standard AWS credential chain, discovers the
  exact model, runs a small inference check, loads the fixture, requests a fixed report
  shape, and provides a manual review checklist.
- [`python/incident_triage.py`](python/incident_triage.py) is the script version of the same
  workflow and also prints token usage. It does not store a long-term API key.

The requested report includes an assessment, evidence-linked timeline, alternative
explanation, reversible containment options, missing evidence, and decisions that remain
with the analyst. This makes the example useful for learning the request pattern without
turning it into an autonomous incident-response system.

## The safe boundary

- The five events are invented. IP addresses use documentation-only ranges.
- **Do not replace them with customer logs or production identifiers.**
- The model receives no credentials and has no tools, filesystem, or network access.
- Recommendations are text for human review. The recipe does not execute containment.

## Run it

```bash
export AWS_REGION=us-east-2
# Optional when using a named local profile:
export AWS_PROFILE=your-profile-name
aws sts get-caller-identity

uv sync --group cybersecurity
uv run --group cybersecurity python \
  06-cybersecurity/01-daybreak-blue-incident-triage/python/incident_triage.py
```

Or open
[`python/incident_triage.ipynb`](python/incident_triage.ipynb) and run its cells in order.
Do not continue if `get-caller-identity` shows an unexpected account or role. The setup cell
prints the selected Region plus the discovery and inference endpoints. Changing
`AWS_REGION` changes both regional Bedrock Mantle endpoints.

The next cell confirms that Mantle discovery returns the exact model ID. A separate cell
then performs a real inference request asking the model to reply with `READY`. Both must
pass before the incident-triage cell is run. The inference check is intentionally small but
is still billable.

## What to look for

The brief should:

- cite event IDs rather than inventing evidence;
- distinguish confirmed facts, likely interpretation, and alternative explanations;
- put reversible containment before destructive action;
- identify missing telemetry and validation steps; and
- leave the final incident declaration and containment decision with a human analyst.

This is triage, not an autonomous response system. Before adapting it, add your own
classification rules, retention controls, audit logging, analyst approval, and evaluation
set. OpenAI's guidance notes that Trusted Access does not automatically grant Zero Data
Retention. `store=False` is not a substitute for that approval; confirm the controls for the
exact environment.
