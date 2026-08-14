"""Two ways to carry a conversation forward, and what each one retains.

The Responses API lets you either keep the transcript in your own application and
resend the relevant part each turn, or store each response on the service and
reference it by ID. The upstream framing is convenience versus control. On Bedrock
there is a second axis that decides it: store=True means AWS retains the response,
input and output, for 30 days.

This script runs both patterns on the same two-turn conversation, measures them, and
shows the one thing readers most often assume wrongly.

Run it from the cookbooks/ directory:

    uv run python 01-foundations/04-conversation-state/python/conversation_state.py

See README.md for the narrative.
"""

import os

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-luna")

FIRST_QUESTION = "In one sentence, what is Amazon DynamoDB?"
FOLLOW_UP = "Now give one practical ecommerce use case for it."
MAX_OUTPUT_TOKENS = 80

client = OpenAI(provider=bedrock(region=REGION))

print(f"Model: {MODEL_ID}    Region: {REGION}")

# --- Pattern A: your application owns the transcript ------------------------

# Nothing is stored on the service. You hold the messages and decide what to send
# back, which is what lets you redact or summarize before the next turn.

print("\nA. Manual history, store=False")
print("→ request   input = the whole message list you are holding")
print("            turn 1 sends 1 message, turn 2 sends 3 — store=False, so AWS keeps")
print("            nothing and you own the transcript")

history = [{"role": "user", "content": FIRST_QUESTION}]

a_first = client.responses.create(
    model=MODEL_ID, input=history, max_output_tokens=MAX_OUTPUT_TOKENS, store=False
)
print("← response")
print(f"   turn 1  {a_first.usage.input_tokens:>3} input tokens  "
      f" {a_first.output_text.strip()[:66]}")

# Append the answer and the next question. This is the whole mechanism.
history.append({"role": "assistant", "content": a_first.output_text})
history.append({"role": "user", "content": FOLLOW_UP})

a_second = client.responses.create(
    model=MODEL_ID, input=history, max_output_tokens=MAX_OUTPUT_TOKENS, store=False
)
print(f"   turn 2  {a_second.usage.input_tokens:>3} input tokens  "
      f" {a_second.output_text.strip()[:66]}")

# --- Pattern B: the service holds the transcript ----------------------------

# store=True is the default on Bedrock; it is written out here because it is the
# point of this pattern, and because AWS then retains the response for 30 days.

print("\nB. previous_response_id, store=True")
print("→ request   input = only the new question, plus previous_response_id")
print("            store=True is required for that reference to resolve, and AWS then")
print("            retains the response — input and output — for 30 days")

b_first = client.responses.create(
    model=MODEL_ID,
    input=FIRST_QUESTION,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=True,
)
print("← response")
print(f"   turn 1  {b_first.usage.input_tokens:>3} input tokens  "
      f" {b_first.output_text.strip()[:66]}")

# The follow-up sends only the new question. The prior turn is referenced, not resent.
b_second = client.responses.create(
    model=MODEL_ID,
    previous_response_id=b_first.id,
    input=FOLLOW_UP,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=True,
)
print(f"   turn 2  {b_second.usage.input_tokens:>3} input tokens  "
      f" {b_second.output_text.strip()[:66]}")

# --- What that actually cost ------------------------------------------------

# The number to look at. Referencing a stored response saves you from *sending* the
# history; it does not save you from paying for it. Both second turns bill far more
# input than their first turn, because the model receives the prior context either
# way. The two totals are close but not identical — each run produces a slightly
# different answer, and the manual path resends exactly the text it received.

print("\nC. Referencing is not cheaper")
print(f"   manual history        turn 1: {a_first.usage.input_tokens:>3}"
      f"  ->  turn 2: {a_second.usage.input_tokens:>3} input tokens")
print(f"   previous_response_id  turn 1: {b_first.usage.input_tokens:>3}"
      f"  ->  turn 2: {b_second.usage.input_tokens:>3} input tokens")
print("   Both grow by roughly the size of the first exchange. Referencing saves")
print("   bandwidth and bookkeeping, not tokens: a stateful turn is not a free turn.")

# --- Clean up ---------------------------------------------------------------

# Pattern B created two stored responses. Unlike the other recipes, this one leaves
# something behind, so it deletes what it made.

print("\nD. Cleanup: deleting the stored responses")
print("→ request   responses.delete(id) for each response pattern B stored")

for response_id in (b_second.id, b_first.id):
    client.responses.delete(response_id)
    print(f"   deleted {response_id[:26]}...")

# Confirm rather than assume.
try:
    client.responses.retrieve(b_first.id)
    print("   still retrievable after delete (unexpected)")
except Exception as error:
    print(f"   retrieve after delete -> {getattr(error, 'status_code', '?')} "
          f"{type(error).__name__}, as expected")
