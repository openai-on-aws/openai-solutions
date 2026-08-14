"""Authenticate to Bedrock with a Bedrock API key instead of the credential chain.

Every other recipe here uses SigV4 from the AWS credential chain and never handles
a credential. This one takes the other documented path — a Bedrock API key in
AWS_BEARER_TOKEN_BEDROCK — because you will meet it in AWS blog posts, and because
a key in the environment is preferred over your IAM credentials. A short-term key
expires, so a stale one fails with 401 on a machine where the AWS CLI works fine.

Run it from the cookbooks/ directory:

    uv run --group foundations python \\
        01-foundations/03-bedrock-api-key-auth/python/bedrock_api_key_auth.py

See README.md for the narrative.
"""

import base64
import os
import urllib.parse

from openai import OpenAI
from openai.providers import bedrock

REGION = os.environ.get("AWS_REGION", "us-east-1")

# Luna is the cheapest of the three; this recipe is about plumbing, not reasoning.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-luna")

ENV_VAR = "AWS_BEARER_TOKEN_BEDROCK"


def ask(client):
    """Make one tiny call. Returns what happened as a string, never raises."""
    try:
        response = client.responses.create(
            model=MODEL_ID,
            input="Reply with exactly: ok",
            max_output_tokens=16,
            store=False,
        )
        return f"200 {response.output_text.strip()!r}"
    except Exception as error:
        return f"{getattr(error, 'status_code', '?')} {type(error).__name__}"


# Remember whatever the caller already had, so the cleanup at the bottom can put it
# back instead of deleting a key they were using.
key_before_this_script = os.environ.get(ENV_VAR)

try:
    print(f"Region: {REGION}    Model: {MODEL_ID}")

    # --- 1. Baseline: the credential chain, with no key set ----------------------

    print("\n1. Baseline: SigV4 from the credential chain")
    print("   → request   OpenAI(provider=bedrock(region=...))   no key involved; the")
    print("               provider signs with whatever the credential chain gives it")

    os.environ.pop(ENV_VAR, None)
    result = ask(OpenAI(provider=bedrock(region=REGION)))
    print(f"   no key set                              ← {result}")

    if not result.startswith("200"):
        print("\n   Baseline failed, so the rest cannot be interpreted.")
        print("   Check `aws sts get-caller-identity` and model access in this Region.")
        raise SystemExit(1)

    # --- 2. Mint a short-term key from those same credentials -------------------

    print("\n2. Mint a short-term Bedrock API key")
    print("   → request   provide_token(region=...)             derives a key from the")
    print("               credentials this process already has — no console step")

    from aws_bedrock_token_generator import provide_token

    key = provide_token(region=REGION)

    # A key is a base64-encoded pre-signed URL, so its query parameters are
    # readable. They are metadata, not the signing secret. The key itself is a
    # credential and is never printed.
    decoded = base64.b64decode(key.removeprefix("bedrock-api-key-") + "===").decode()
    params = dict(urllib.parse.parse_qsl(decoded.split("?")[1]))

    print(f"   prefix                                  {key[:16]}")
    print(f"   length                                  {len(key)} characters")
    print(f"   action                                  {params['Action']}")
    print(f"   algorithm                               {params['X-Amz-Algorithm']}")
    # The expiry the signed URL asks for. 43200 s is aws-bedrock-token-generator's
    # default, not a property of Bedrock keys: provide_token takes expiry=, and
    # long-term keys from the console do not expire on their own.
    expires = params["X-Amz-Expires"]
    print(f"   requested expiry                        {expires} seconds")

    # --- 3. Authenticate with the key -------------------------------------------

    print("\n3. Authenticate with the key")
    print("   → request   the same call, twice: once with the key in the environment,")
    print("               once passed as api_key= — both bypass SigV4")

    # Setting the environment variable is all it takes.
    os.environ[ENV_VAR] = key
    from_env = ask(OpenAI(provider=bedrock(region=REGION)))
    print(f"   valid key in the environment            ← {from_env}")

    # Passing it explicitly is equivalent, and clearer when a program juggles
    # several credentials.
    explicit = OpenAI(provider=bedrock(region=REGION, api_key=key))
    print(f"   key passed to bedrock(...)              ← {ask(explicit)}")

    # --- 4. The failure mode worth remembering ----------------------------------

    print("\n4. What a stale key looks like")
    print("   → request   a deliberately invalid key in AWS_BEARER_TOKEN_BEDROCK, then")
    print("               the same call with api_key=None inside bedrock(...)")

    os.environ[ENV_VAR] = "bedrock-api-key-deliberately-invalid"
    stale = ask(OpenAI(provider=bedrock(region=REGION)))
    print(f"   stale key in the environment            ← {stale}")

    # api_key=None is the escape hatch, and where you put it matters. At the top
    # level it does nothing, because the provider reads the environment variable
    # before the client sees it.
    top_level = OpenAI(provider=bedrock(region=REGION), api_key=None)
    print(f"   api_key=None at the top level           ← {ask(top_level)}")

    inside = OpenAI(provider=bedrock(region=REGION, api_key=None))
    print(f"   api_key=None inside bedrock(...)        ← {ask(inside)}")

finally:
    # --- 5. Clean up -------------------------------------------------------------

    # A key left behind is preferred by every later call in this process, so
    # skipping this makes the *next* thing you run fail with a 401 that points
    # anywhere but here. In `finally` so it happens even if the run failed halfway.
    if key_before_this_script is None:
        os.environ.pop(ENV_VAR, None)
        print(f"\n5. Cleanup: {ENV_VAR} unset.")
    else:
        os.environ[ENV_VAR] = key_before_this_script
        print(f"\n5. Cleanup: {ENV_VAR} restored to its previous value.")

    print("   This only affects this process. If you exported the variable in your")
    print(f"   shell, run `unset {ENV_VAR}` there too.")
