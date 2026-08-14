"""One prompt, three models: seeing that Luna, Terra and Sol do not answer the same.

Switching between the GPT-5.6 models is a one-line change — same API, same context
window, same parameters — which makes it easy to assume the choice does not matter much.
It does, and this script is the smallest possible demonstration: one prompt, sent to all
three, with an objectively checkable answer.

The prompt shows the model a committed pricing function and one basket and asks for the
exact total in cents. Ground truth is whatever that function returns, so nothing has to
be adjudicated and the recipe never executes anything a model wrote.

The answer asked for is a single integer, so reading it needs no parsing: one number,
compared against what the function returns. (Constraining a reply to a schema is the
better tool for real work — that is structured output, and it has a recipe of its own in
the reasoning-and-output group. It is deliberately not used here: this is foundations,
and a recipe should not lean on a capability you have not met yet.)

This is deliberately a tiny probe, not an evaluation. One prompt cannot rank models.
What it can do is show that the answers differ, which is the reason to measure on your
own task before picking a tier.

Run it from the cookbooks/ directory:

    uv run python 01-foundations/06-choosing-a-model/python/choosing_a_model.py

See README.md for the narrative.
"""

import json
import os
import sys
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# This recipe is a comparison, so it names all three rather than picking one.
# Sol is served in us-east-1 and us-east-2 only, so run this in one of those.
CANDIDATES = [
    "openai.gpt-5.6-luna",
    "openai.gpt-5.6-terra",
    "openai.gpt-5.6-sol",
]

# Which basket from data/baskets.jsonl to price. Swap it to try another.
BASKET_ID = "BSK-05"

DATA = Path(__file__).parent.parent / "data"

# The pricing module is both the text shown to the model and the oracle scoring it.
sys.path.insert(0, str(DATA))
from pricing_engine import basket_total_cents  # noqa: E402

BASKETS = [
    json.loads(line)
    for line in (DATA / "baskets.jsonl").read_text().splitlines()
    if line.strip()
]
basket = next(b for b in BASKETS if b["id"] == BASKET_ID)
expected = basket_total_cents(basket)


INSTRUCTIONS = (
    "You are given the pricing engine of an online grocery retailer, then one basket "
    "as JSON. Work out exactly what basket_total_cents would return for it. Reply "
    "with the integer number of cents and nothing else — no symbol, no working.\n\n"
    f"```python\n{(DATA / 'pricing_engine.py').read_text()}\n```"
)

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

print(f"Region: {REGION}    store=False on every call (AWS retains nothing)")

print("\n" + "=" * 78)
print("The task the three models are given")
print("=" * 78)
print(
    "Each model receives the source of a real pricing function and one shopping\n"
    "basket, and has to say what that function returns for that basket — as a plain\n"
    "integer number of cents. Nothing is generated or executed: the model reads code\n"
    "and predicts its output.\n"
    "\n"
    "The function is short but its rules interact, which is what makes the task\n"
    "discriminating without making it long:\n"
    "  1. a percentage discount per line, rounded half-up\n"
    "  2. a multibuy credit — but ONLY on lines flagged multibuy — computed from the\n"
    "     already-discounted unit price\n"
    "  3. a free-shipping test on the subtotal BEFORE any voucher is applied\n"
    "  4. the voucher clamped at zero, with shipping added last\n"
    "\n"
    "Each rule is reasonable on its own. Together they are hard to hold in your head,\n"
    "so a model has to read the code precisely rather than pattern-match it.\n"
    "\n"
    "Scoring needs no judge and no rubric: the committed function IS the answer, so\n"
    "each reply is either that integer or it is not."
)
print(f"\nBasket under test: {BASKET_ID} — {basket['note']}")
print(f"Correct answer, from the committed function: {expected} cents")

# --- The request, printed once because all three models get the same one -----

print("\n→ request  (identical for all three models)")
print(f"   instructions      the pricing engine source ({len(INSTRUCTIONS)} chars) and")
print("                     'reply with the integer number of cents'")
print(f"   input             {json.dumps(basket)[:88]}…")
print("   reasoning.effort  default    the task needs real work, so it is not pinned")
print("   max_output_tokens 4000       reasoning tokens come out of this budget too")
print("   why this shape    one prompt, three models, an answer the committed")
print("                     function can check — so a difference is the model")

# --- One prompt, three models ----------------------------------------------

for model_id in CANDIDATES:
    print(f"\n→ {model_id}")
    response = client.responses.create(
        model=model_id,
        instructions=INSTRUCTIONS,
        input=json.dumps(basket),
        max_output_tokens=4000,
        store=False,
    )

    answer = response.output_text.strip().replace(",", "")
    usage = response.usage
    verdict = "correct" if answer == str(expected) else "wrong"

    print(f"← {answer or '<empty>'} cents   {verdict}")
    print(f"   tokens:    {usage.input_tokens} in, {usage.output_tokens} out "
          f"({usage.output_tokens_details.reasoning_tokens} reasoning, invisible)")

print(
    "\nThe answers differ, which is the point: the tier is a real decision rather\n"
    "than a cost dial. One prompt is a probe, not a measurement:\n"
    "before committing to a tier, run your own task across all three and repeat each\n"
    "run, since on a handful of cases the variation within one model can be as large\n"
    "as the gap between two of them.\n"
    "\nPer-token rates differ by tier. See https://aws.amazon.com/bedrock/pricing/"
)
