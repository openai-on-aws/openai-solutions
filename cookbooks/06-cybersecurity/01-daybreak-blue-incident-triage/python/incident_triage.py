"""Triage a synthetic cloud identity incident with Daybreak Blue.

The model sees five fabricated events and returns an evidence-linked incident
brief. It has no tools and the script executes no recommended action.

Run from cookbooks/:

    uv run --group cybersecurity python \
      06-cybersecurity/01-daybreak-blue-incident-triage/python/incident_triage.py
"""

import json
import os
from pathlib import Path

from aws_bedrock_token_generator import provide_token
from openai import BedrockOpenAI, OpenAI

REGION = (
    os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "us-east-2"
)
HOST = f"https://bedrock-mantle.{REGION}.api.aws"
CATALOG_ENDPOINT = f"{HOST}/v1"
INFERENCE_ENDPOINT = f"{HOST}/openai/v1"
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-daybreak-blue-5.6-sol")
PROBE_MAX_OUTPUT_TOKENS = 128
MAX_OUTPUT_TOKENS = 1200

DATA = Path(__file__).resolve().parent.parent / "data" / "identity_events.jsonl"
EVENTS = [json.loads(line) for line in DATA.read_text().splitlines() if line]

INSTRUCTIONS = """You are assisting an authorized defensive security team.
Analyze only the synthetic events supplied in this request. Do not infer real identities
or claim access to systems or telemetry that is not shown. Keep evidence, inference, and
recommended action distinct. Prefer reversible containment and human approval."""

TASK = f"""Create a concise incident-triage brief from these synthetic events:

{json.dumps(EVENTS, indent=2)}

Use these headings:
1. Assessment and confidence
2. Evidence timeline (cite event IDs)
3. Plausible alternative explanation
4. Immediate reversible containment
5. Evidence to collect next
6. Human decisions required

Do not execute or claim to execute any action."""


def bedrock_token() -> str:
    """Mint or reuse a short-term Bedrock token for the selected Region."""
    return provide_token(region=REGION)


def verify_model_discovery() -> None:
    """Confirm that the exact model appears on the Mantle Models API."""
    catalog = OpenAI(
        api_key=bedrock_token(),
        base_url=CATALOG_ENDPOINT,
        max_retries=3,
    )
    model_ids = {model.id for model in catalog.models.list().data}
    if MODEL_ID not in model_ids:
        raise RuntimeError(
            f"{MODEL_ID} was not returned by {CATALOG_ENDPOINT}/models. "
            "Confirm model approval, AWS identity, and Region."
        )
    print(f"Model discovery passed: {MODEL_ID}")


def verify_model_access(client: BedrockOpenAI) -> None:
    """Make a small real inference request before starting the recipe."""
    probe = client.responses.create(
        model=MODEL_ID,
        input="Reply with READY to confirm that basic inference is working.",
        max_output_tokens=PROBE_MAX_OUTPUT_TOKENS,
        store=False,
    )
    probe_text = probe.output_text.strip()
    if probe.status != "completed" or not probe_text:
        raise RuntimeError(
            f"Model check did not complete successfully: id={probe.id}, "
            f"status={probe.status!r}"
        )
    print(f"Model check passed: {probe_text}")


print(f"Daybreak Blue incident triage  ·  {MODEL_ID} in {REGION}")
print(f"Discovery endpoint: {CATALOG_ENDPOINT}")
print(f"Inference endpoint: {INFERENCE_ENDPOINT}")
print(f"Input: {len(EVENTS)} fabricated events; no customer data")
print("Boundary: analysis only; no tools, network calls, or automated containment")
print(f"Output cap: {MAX_OUTPUT_TOKENS} tokens  ·  store=False\n")

verify_model_discovery()
client = BedrockOpenAI(
    aws_region=REGION,
    bedrock_token_provider=bedrock_token,
    max_retries=3,
)
verify_model_access(client)
print("\nRunning incident-triage request...")

response = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=TASK,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=False,
)

output_text = response.output_text.strip()
if response.status != "completed" or not output_text:
    raise RuntimeError(
        f"Incident-triage request did not complete: id={response.id}, "
        f"status={response.status!r}, details={response.incomplete_details!r}"
    )
print(output_text)

usage = response.usage
reasoning_tokens = getattr(usage.output_tokens_details, "reasoning_tokens", None)
print("\nUsage")
print(f"  input:     {usage.input_tokens}")
print(f"  output:    {usage.output_tokens}")
print(f"  reasoning: {reasoning_tokens}")
print(f"  total:     {usage.total_tokens}")
