"""Carry reasoning across turns, and know what the default re-bills.

A reasoning model returns a reasoning item alongside its answer. On a multi-turn or
tool-calling conversation you can carry that item forward so the model keeps its own
train of thought — and on GPT-5.6 the parameter controlling this defaults to replaying
**every** earlier turn's reasoning, re-billed as input each time.

  A. two patterns   previous_response_id, and stateless replay of response.output
  B. the transcript  three turns of a problem that needs real reasoning
  C. the cost        what each reasoning.context setting adds to your input bill
  D. the carrier     encrypted_content, and how to opt out for a single turn
  E. choosing        which setting suits which workload

Both settings are sent the same fixed transcript, so the numbers in C compare like with
like. See README.md.
"""

import os

from openai import OpenAI
from openai.providers import bedrock

from cookbook_utils import delete_stored_responses

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Enough effort that there is reasoning worth carrying. On an easy question the model
# barely reasons, nothing accumulates, and there is nothing to measure.
EFFORT = "medium"

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

# A constraint problem, extended over three turns. Each turn adds a constraint that
# invalidates part of the previous answer, so later turns depend on earlier deduction.
CHAIN = [
    "Five maintenance crews A-E each take one night shift, Monday to Friday, one "
    "crew per night. A cannot work Monday or Friday. B must work the night "
    "immediately before D. C must work Wednesday or later. E cannot work a night "
    "adjacent to A. D cannot work Tuesday. Give the unique assignment and say why each "
    "alternative fails.",
    "Now D also refuses Thursday. Is there still a valid assignment? Show working.",
    "Drop the constraint that B must be immediately before D, and instead require that "
    "B and D are never adjacent. How many valid assignments are there now?",
]

FINAL_QUESTION = ("Summarise the three scenarios and which constraint did most to "
                  "narrow the options.")

print(f"Carrying reasoning across turns  ·  {MODEL_ID} in {REGION}")
print(f"reasoning.effort {EFFORT}  ·  store=False except where a pattern needs it\n")

# --- A. The two continuity patterns -----------------------------------------

print("=" * 78)
print("A. Two ways to continue a conversation")
print("=" * 78)
print("→ request   pattern 1: previous_response_id")
print("   store=True        required — you are referencing a response AWS kept")
print("   note              a stored response means AWS retains input and output")
print("                     for 30 days, which is a data decision, not a detail")

stored_first = client.responses.create(
    model=MODEL_ID,
    input=CHAIN[0],
    reasoning={"effort": EFFORT},
    max_output_tokens=3000,
    store=True,
)
stored_second = client.responses.create(
    model=MODEL_ID,
    previous_response_id=stored_first.id,
    input=CHAIN[1],
    reasoning={"effort": EFFORT},
    max_output_tokens=3000,
    store=True,
)
print("← response")
print(f"   turn 1  {stored_first.usage.input_tokens:>5} in / "
      f"{stored_first.usage.output_tokens:>5} out")
print(f"   turn 2  {stored_second.usage.input_tokens:>5} in / "
      f"{stored_second.usage.output_tokens:>5} out   (references turn 1 by id)")
print("   The second call sent one sentence and was billed for the whole context:")
print("   a stateful turn is not a free turn, it is one you did not re-upload.")

# Those two turns are the only thing this recipe leaves on the service, so they go
# now rather than sitting in the 30-day window for the sake of a demonstration.
removed = delete_stored_responses(client, stored_first.id, stored_second.id)
print(f"   deleted {len(removed)} stored turn(s) — the rest of this recipe uses")
print("   store=False, so nothing else is retained.\n")

print("→ request   pattern 2: stateless replay")
print("   store=False       nothing retained; you hold the transcript")
print("   note              response.output is carried forward UNMODIFIED, which")
print("                     is what keeps the reasoning item intact")
print("   (A Conversations API is a third pattern on the first-party OpenAI API.")
print("    It is not available here, so these two are the whole set.)\n")

# --- B. Build one transcript ------------------------------------------------

print("=" * 78)
print("B. Build a transcript that has reasoning in it")
print("=" * 78)

transcript: list = []
for turn_number, question in enumerate(CHAIN, 1):
    transcript.append({"role": "user", "content": question})
    response = client.responses.create(
        model=MODEL_ID,
        input=transcript,
        reasoning={"effort": EFFORT},
        max_output_tokens=3000,
        store=False,
    )
    transcript += response.output
    reasoning_items = [i for i in response.output if i.type == "reasoning"]
    blob_size = sum(len(getattr(i, "encrypted_content", "") or "")
                    for i in reasoning_items)
    print(f"←  turn {turn_number}  {response.usage.input_tokens:>6} in  "
          f"{response.usage.output_tokens:>5} out  "
          f"{response.usage.output_tokens_details.reasoning_tokens:>5} reasoning  "
          f"blob {blob_size:>5} chars")

item_kinds = [getattr(i, "type", i.get("role") if isinstance(i, dict) else "?")
              for i in transcript]
print(f"\n   transcript now holds {len(transcript)} items: {item_kinds}")
print("   Three reasoning items, each carrying an encrypted blob. That is what")
print("   the next step is about.\n")

# --- C. The A/B, on one fixed transcript ------------------------------------

print("=" * 78)
print("C. The same transcript, sent twice")
print("=" * 78)
transcript.append({"role": "user", "content": FINAL_QUESTION})
print("→ request   identical input, identical question, identical effort")
print(f"   input             the {len(transcript)}-item transcript above")
print("   varying           reasoning.context only")
print("   why this way      running the chain twice does not work: the model's own")
print("                     answers differ between runs, so the transcripts diverge")
print("                     and you end up measuring answer length. One fixed")
print("                     transcript sent twice isolates the parameter.\n")

measurements = {}
for mode in ("current_turn", "all_turns"):
    response = client.responses.create(
        model=MODEL_ID,
        input=transcript,
        reasoning={"effort": EFFORT, "context": mode},
        max_output_tokens=3000,
        store=False,
    )
    measurements[mode] = response.usage.input_tokens
    print(f"←  context={mode:13} input_tokens={response.usage.input_tokens:>6}  "
          f"echoed={getattr(response.reasoning, 'context', None)!r}")

difference = measurements["all_turns"] - measurements["current_turn"]
print(f"\n   difference: {difference:+} input tokens on a three-turn history")
if measurements["current_turn"]:
    share = difference / measurements["current_turn"]
    print(f"   that is {share:+.1%} on this transcript")
print(
    "\n   all_turns re-renders the reasoning of every earlier turn, so what it adds\n"
    "   grows with the number of turns while current_turn stays flat. On a three-turn\n"
    "   history that is already more than double; in a twenty-turn agent loop it is\n"
    "   the largest single item in the input bill. Worth setting deliberately."
)

# --- D. The carrier ---------------------------------------------------------

print("\n" + "=" * 78)
print("D. What carries the reasoning, and how to drop it")
print("=" * 78)
print("→ request   the same transcript with encrypted_content removed from every")
print("            reasoning item, still asking for context=all_turns")
print("   why       encrypted_content is what carries the reasoning between turns,")
print("             so removing it from an item is a per-turn opt-out — useful when")
print("             you want continuity for recent turns but not the whole history")

stripped: list = []
for item in transcript:
    if getattr(item, "type", None) == "reasoning":
        as_dict = item.model_dump()
        as_dict.pop("encrypted_content", None)
        stripped.append(as_dict)
    else:
        stripped.append(item)

blob_free = client.responses.create(
    model=MODEL_ID,
    input=stripped,
    reasoning={"effort": EFFORT, "context": "all_turns"},
    max_output_tokens=3000,
    store=False,
)
print("← response")
print(f"   all_turns, blob removed      input_tokens={blob_free.usage.input_tokens:>6}")
print(f"   all_turns, blob present      input_tokens={measurements['all_turns']:>6}")
print(f"   current_turn                 input_tokens={measurements['current_turn']:>6}")
print("   With the blob gone there is nothing to replay, so the cost matches")
print("   current_turn. That gives you three levels of control: the parameter for")
print("   the whole request, and the items themselves for individual turns.\n")

# --- E. Choosing ------------------------------------------------------------

print("=" * 78)
print("Choosing")
print("=" * 78)
print(
    "   all_turns    a short chain where later turns genuinely build on earlier\n"
    "                deduction, and correctness matters more than the input bill.\n"
    "   current_turn a long loop — an agent taking twenty tool-calling turns —\n"
    "                where replaying twenty prior traces costs more than it adds.\n"
    "   auto         portable-looking and not portable: it resolves per model, so\n"
    "                changing model can change your cost profile without changing\n"
    "                a line of your code. Pin the value you mean.\n"
    "\n"
    "   One practical note when you try this on your own workload: check\n"
    "   usage.output_tokens_details.reasoning_tokens first. On a straightforward\n"
    "   question the model emits little or no reasoning, so there is nothing to\n"
    "   carry and the setting makes no difference either way."
)
print("\nPer-token rates by model: https://aws.amazon.com/bedrock/pricing/")
