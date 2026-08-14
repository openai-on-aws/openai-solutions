"""Your first call to an OpenAI model on Amazon Bedrock.

Four lines of setup, one call. No API key, no token to mint, no base URL: the
Bedrock provider works out the regional endpoint and takes credentials from the
AWS credential chain, so if `aws sts get-caller-identity` works, this works.

Run it from the cookbooks/ directory:

    uv run python 01-foundations/01-first-call/python/first_call.py

See README.md for the four IAM permissions this needs, and what each failure
looks like when one is missing.
"""

import os

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# The three GPT-5.6 models. Terra is the sensible default; Luna is cheaper and
# faster, Sol is stronger. Note Sol is not served in us-west-2.
#   openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# --- The call ---------------------------------------------------------------

client = OpenAI(provider=bedrock(region=REGION))

PROMPT = "Explain prompt caching in two sentences."

# Print the request before sending it. Every recipe here does this: an answer with no
# visible request leaves you guessing which parameter produced what you are reading.
print("→ request")
print(f"   model             {MODEL_ID}")
print(f"   region            {REGION}    (explicit — never an ambient default)")
print(f"   input             {PROMPT}")
print("   max_output_tokens 256        the only hard bound on what one call can cost")
print("   store             False      Bedrock defaults to True, and AWS then keeps")
print("                                the response — input and output — for 30 days")

response = client.responses.create(
    model=MODEL_ID,
    input=PROMPT,
    max_output_tokens=256,
    # Responses requests on Bedrock default to store=True, and AWS then keeps the
    # response — input and output — for 30 days. Recipes opt out explicitly.
    store=False,
)

print()
print("← response")
print(response.output_text)

# --- What came back ---------------------------------------------------------

# output_text is a convenience accessor. The real shape is a list of output items:
# a message here, plus a reasoning item when the model works something out before
# answering, which depends on the prompt. reasoning_tokens tells you
# way, and you pay for them.
print()
print("Output items:", [item.type for item in response.output])

usage = response.usage
print(f"Input tokens:     {usage.input_tokens}")
print(f"Output tokens:    {usage.output_tokens}")
print(f"  of which reasoning: {usage.output_tokens_details.reasoning_tokens}")
print(f"Total tokens:     {usage.total_tokens}")
