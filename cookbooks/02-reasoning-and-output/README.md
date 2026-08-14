# Reasoning and output control

> **How much thinking do I buy, and how do I shape what comes back?**

These five recipes are about the request, not the platform. Once a call works, the next
questions are how much deliberation to pay for, how to make the reply a shape your code can
rely on, and how to let the model reach your own systems. All of it is ordinary Responses API
work — what is specific to Bedrock is what each choice costs, and these recipes measure that.

Start with structured outputs if you are extracting data, or with reasoning effort if you are
watching a bill grow.

## What these recipes decide for you

- **`text.format`** turns a reply into a shape you can trust, so a downstream system does not
  have to guess what came back.
- **`reasoning.effort`** buys deliberation. Measuring it on your own task is usually more
  valuable than reasoning about it, because the cheap tier saturates earlier than people expect.
- **`text.verbosity`** controls length independently of effort, which means "think hard, answer
  briefly" is a combination you can actually ask for.
- **`tools`** let the model call your code, either from your loop or from Bedrock's.
- **`reasoning.context`** decides how much earlier thinking is replayed on each turn, and it is
  the parameter most likely to surprise you on an agent loop.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-structured-claims-intake/`](01-structured-claims-intake/) | Structured outputs: three levels of guarantee on an extracted record | beginner | low |
| [`02-reasoning-effort-and-verbosity/`](02-reasoning-effort-and-verbosity/) | Right-sizing reasoning effort and verbosity against a quality bar | intermediate | medium |
| [`03-tool-calling/`](03-tool-calling/) | Tool calling: the flat schema, and the loop around it | intermediate | low |
| [`04-reasoning-across-turns/`](04-reasoning-across-turns/) | Carrying reasoning across turns | advanced | medium |
| [`05-server-side-tools/`](05-server-side-tools/) | Server-side tools: Bedrock as the MCP client | advanced | low |
<!-- END GENERATED: group-index -->

## Running these

```bash
uv sync
uv run python \
  02-reasoning-and-output/01-structured-claims-intake/python/claims_intake.py
```

One recipe deploys a Lambda function, so it needs permission to create and delete one — its
README says so, and it cleans up after itself. Every other recipe here is inference only.

## Where to go next

- [`cookbooks/03-grounding-and-multimodal/`](../03-grounding-and-multimodal/) — giving the model
  information it was not trained on, and checking that its answer is faithful to it.
- [`cookbooks/04-agents/`](../04-agents/) — the tool loop turned into an agent with a goal.
- [`cookbooks/05-production/`](../05-production/) — what these choices cost at volume.
