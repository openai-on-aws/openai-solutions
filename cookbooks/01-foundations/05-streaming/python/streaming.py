"""Streaming on Bedrock: typed events, and what the reasoning ones carry.

The Responses API streams a sequence of *typed events*, not raw text chunks. Each
event says which part of the response it belongs to, so you can render text as it
arrives, show that the model is thinking, and still read exact token counts at the
end.

This script sends one prompt without streaming and again with it, then streams a turn
the model has to reason about, and ends on what the three runs teach.

Run it from the cookbooks/ directory:

    uv run python 01-foundations/05-streaming/python/streaming.py

See README.md for the narrative.
"""

import os
import time

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

PROMPT = (
    "Explain to a new engineer what an AWS Region is, and why choosing one "
    "matters for a production workload. Four short paragraphs."
)
# Deliberately arithmetic-heavy. A question the model can answer straight from
# knowledge produces no reasoning item, and section D would have nothing to show.
REASONING_PROMPT = (
    "A batch job starts every 18 minutes from 08:00. Another starts every "
    "24 minutes from 08:12. What is the first clock time after 12:00 when both "
    "start in the same minute? Answer with the time only."
)
MAX_OUTPUT_TOKENS = 600

# max_retries is the client's bounded backoff for a 429, which on this endpoint means
# a tokens-per-minute quota rather than a request-rate limit.
client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

print(f"Model: {MODEL_ID}    Region: {REGION}    store=False on all three calls")

# --- A. The same prompt, without streaming ----------------------------------

# The comparison section B rests on. Nothing here is wrong or slow: the answer simply
# does not exist until the call returns, so there is nothing to show a reader.

print("\nA. Without streaming")
print("→ request")
print(f"   model              {MODEL_ID}")
print(f"   max_output_tokens  {MAX_OUTPUT_TOKENS}")
print(f"   input              {PROMPT[:58]}…")
print("   no stream          the answer exists only once the call returns")

started = time.perf_counter()
whole = client.responses.create(
    model=MODEL_ID,
    input=PROMPT,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=False,
)
unstreamed_wait = time.perf_counter() - started

print("← response")
print(f"   The screen stayed empty for {unstreamed_wait:.1f}s, then all "
      f"{len(whole.output_text)} characters")
print("   appeared at once. The text is not printed here — you will read it in B.")
print(f"   tokens             {whole.usage.input_tokens} in / "
      f"{whole.usage.output_tokens} out")

# --- B. The same prompt, streamed -------------------------------------------

# responses.stream() is a context manager: it opens the HTTP stream, yields typed
# events, and closes the connection on exit even if the loop raises.

print("\nB. With streaming")
print("→ request")
print("   responses.stream   same model, same prompt, same token cap")
print("   watch for          response.output_text.delta, the one event with text\n")

# One dict does the work of two: it counts each event type and, because dicts keep
# insertion order, it also records the order they first arrived in.
event_counts: dict[str, int] = {}
item_types: list[str] = []
usage_from_event = None
delta_carried_usage = False
first_text_at = None

started = time.perf_counter()
with client.responses.stream(
    model=MODEL_ID,
    input=PROMPT,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=False,
) as stream:
    for event in stream:
        event_counts[event.type] = event_counts.get(event.type, 0) + 1

        # An item is a top-level piece of the response — a message here, a reasoning
        # item in section D, a function_call on a turn that uses tools.
        if event.type == "response.output_item.added":
            if event.item.type not in item_types:
                item_types.append(event.item.type)

        # This is the only event type carrying user-visible text. Everything else is
        # structure, which is why you match on event.type rather than hunting for a
        # payload.
        if event.type == "response.output_text.delta":
            if first_text_at is None:
                first_text_at = time.perf_counter() - started
            if getattr(event, "usage", None) is not None:
                delta_carried_usage = True
            print(event.delta, end="", flush=True)

        # Token counts ride on the final event's response object. Reading them here
        # rather than from the accumulated response shows where they actually come
        # from — every earlier event carries a response with usage still None.
        if event.type == "response.completed":
            usage_from_event = event.response.usage

    # Identical in shape to the object section A returned, so code that consumes a
    # response does not have to know how it was delivered.
    streamed = stream.get_final_response()

streamed_total = time.perf_counter() - started
print("\n")
print("← response  (the text above arrived progressively)")
print(f"   Reading started after {first_text_at:.1f}s instead of "
      f"{unstreamed_wait:.1f}s, and the")
print(f"   answer finished at {streamed_total:.1f}s. Both figures are from this run "
      "on your")
print("   account, not published numbers.")
print(f"   tokens             {usage_from_event.input_tokens} in / "
      f"{usage_from_event.output_tokens} out, read off the response.completed event")
if not delta_carried_usage:
    print("   No delta event carried a usage object, so there is no running total to")
    print("   meter: a per-request cost figure is recorded when the turn ends.")

# --- C. The event types that produced it ------------------------------------

# Printed in arrival order rather than alphabetically, because the order is the
# lesson: the response is announced, an item opens, a content part opens, text
# arrives in deltas, and each of those closes again in reverse.

print(f"\nC. The {len(event_counts)} event types behind that answer, in arrival order")
for event_type, count in event_counts.items():
    print(f"   {count:>4} x  {event_type}")

# --- D. A turn the model has to think about ---------------------------------

# A reasoning item appears as an item that opens and closes with nothing readable in
# between. What it carries is encrypted_content: an opaque blob you cannot read, but
# which you can pass back on the next turn so the model keeps its own train of
# thought. That is what 04-reasoning-across-turns does with it.

print("\nD. A turn with reasoning effort high")
print("→ request")
print("   reasoning.effort   high, because the question is arithmetic and the model")
print("                      has something to deliberate about")
print("   include            reasoning.encrypted_content, to see what the item holds")
print(f"   input              {REASONING_PROMPT[:58]}…\n")

reasoning_counts: dict[str, int] = {}
reasoning_item_types: list[str] = []
blob = ""
blob_arrived_at = None

started = time.perf_counter()
with client.responses.stream(
    model=MODEL_ID,
    input=REASONING_PROMPT,
    reasoning={"effort": "high"},
    include=["reasoning.encrypted_content"],
    max_output_tokens=400,
    store=False,
) as stream:
    for event in stream:
        reasoning_counts[event.type] = reasoning_counts.get(event.type, 0) + 1
        if event.type == "response.output_item.added":
            if event.item.type not in reasoning_item_types:
                reasoning_item_types.append(event.item.type)
            print(f"   {time.perf_counter() - started:5.2f}s  a "
                  f"{event.item.type} item opened")
            # The reasoning item arrives with its encrypted_content already filled
            # in, not built up over later events, so a streaming application can
            # persist it for the next turn as soon as the item opens.
            if event.item.type == "reasoning":
                blob = event.item.encrypted_content or ""
                blob_arrived_at = time.perf_counter() - started
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
    reasoned = stream.get_final_response()

print("\n")
print("← response")
print(f"   answer             {reasoned.output_text.strip()}")
print(f"   reasoning tokens   {reasoned.usage.output_tokens_details.reasoning_tokens},"
      " billed as output and drawn from max_output_tokens")
print(f"   encrypted_content  {len(blob)} characters of ciphertext, not prose, so")
print("                      there is no trace you can show a reader")
print(f"                      It was complete at {blob_arrived_at:.2f}s, on the event")
print("                      that opened the item — you do not wait for the turn to")
print("                      end to save it for the next one.")

# --- E. What the three runs teach -------------------------------------------

# The conclusion is a comparison across sections, so it belongs at the end where the
# reader has seen all three.

print("\nE. What to take from this")
print()
print("   Streaming changed when the first word appeared, not what the turn cost.")
print(f"   Reading began at {first_text_at:.1f}s streamed against "
      f"{unstreamed_wait:.1f}s unstreamed, while the")
print(f"   two answers billed {whole.usage.output_tokens} and "
      f"{streamed.usage.output_tokens} output tokens — a difference that comes")
print("   from the wording the model chose, not from how it was delivered.")
print()
print("   One event type out of nine carries text. You print")
print("   response.output_text.delta and treat the other eight as structure.")
print()
print("   Reasoning did not enlarge that vocabulary. Both streamed turns emitted the")
print(f"   same {len(event_counts)} event types. What told you the second one was "
      "thinking is the kind of")
print("   item inside response.output_item.added:")
print(f"     a plain answer     {', then '.join(item_types)}")
print(f"     a reasoning turn   {', then '.join(reasoning_item_types)}")
print()
print("   So a UI does not learn a second set of events for reasoning. It watches")
print("   response.output_item.added and reads the item type — the same place a")
print("   function_call or a web_search_call appears on a turn that uses tools, which")
print("   means one handler covers all three.")
