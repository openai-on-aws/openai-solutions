"""Pay for a long stable prefix once instead of on every turn.

An agent loop sends the same runbook on every turn and a different customer question
each time. That is the shape explicit prompt caching is built for: mark the boundary
between what repeats and what changes, and the repeated part is billed at a discount
from the second call onwards.

  A. the prefix     what is stable, and how big it has to be
  B. implicit       the default, with no parameters at all
  C. explicit       mark the boundary yourself, and watch it write then read
  D. the cache key  a partition, not a label — the mistake that costs the most
  E. where the prefix lives  instructions= versus a marked content part
  F. the session    what six turns cost with and without

Everything here is measured from `usage.input_tokens_details`, which is the
authoritative source — CloudWatch has no cache metric. See README.md.
"""

import os
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Explicit caching is a GPT-5.6 capability: 5.5 and 5.4 reject the parameters.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Names what the prefix IS, never what the request is. See step D.
CACHE_KEY = "northlink-runbook-v1"

DATA = Path(__file__).resolve().parent.parent / "data"
RUNBOOK = (DATA / "runbook.md").read_text()

QUESTIONS = [
    "Customer reports a LOS alarm and the ONT shows no optical reading. First action?",
    "DYING-GASP overnight, mains power is fine. Is this a network fault?",
    "SD alarm only, service still working. Do I dispatch?",
    "LOA after an ONT swap last week. What is the likely cause?",
    "FEC alarm on its own, customer has not complained. Action?",
    "Two subscribers on the same PON both showing SF. What do I raise?",
]

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)


def usage_of(response) -> tuple[int, int, int]:
    """Pull the three numbers that matter: total input, cache reads, cache writes."""
    details = response.usage.input_tokens_details
    return (
        response.usage.input_tokens,
        details.cached_tokens,
        getattr(details, "cache_write_tokens", 0),
    )


def show(label: str, response) -> tuple[int, int, int]:
    total, cached, written = usage_of(response)
    flag = "READ " if cached else ("write" if written else "  —  ")
    print(f"←  {label:38} {flag}  in={total:<6} cached={cached:<6} written={written}")
    return total, cached, written


def ask(question: str, *, explicit: bool, key: str | None,
        breakpoint_on_prefix: bool = True):
    """One agent turn. The prefix is identical every time; only the question changes."""
    prefix_part = {"type": "input_text", "text": RUNBOOK}
    if explicit and breakpoint_on_prefix:
        # The breakpoint goes at the END of what repeats. Everything before it is
        # the cacheable prefix; everything after is the changing suffix.
        prefix_part["prompt_cache_breakpoint"] = {"mode": "explicit"}

    kwargs = {}
    if key:
        kwargs["prompt_cache_key"] = key
    if explicit:
        # ttl accepts only "30m" — 5m and 1h are rejected with a 400.
        kwargs["extra_body"] = {
            "prompt_cache_options": {"mode": "explicit", "ttl": "30m"}
        }

    return client.responses.create(
        model=MODEL_ID,
        input=[
            {"type": "message", "role": "developer", "content": [prefix_part]},
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": question}]},
        ],
        reasoning={"effort": "none"},
        max_output_tokens=200,
        store=False,
        **kwargs,
    )


print(f"Explicit prompt caching  ·  {MODEL_ID} in {REGION}")
print("store=False on every call; caching is independent of response storage\n")

# --- A. The prefix ----------------------------------------------------------

print("=" * 78)
print("A. What is stable, and is it big enough")
print("=" * 78)
probe = ask(QUESTIONS[0], explicit=False, key=None)
prefix_total, _, _ = usage_of(probe)
print(f"→ request   the runbook ({len(RUNBOOK)} chars) plus one question")
print(f"←           {prefix_total} input tokens in total")
print("   The minimum cacheable prefix is 1,024 tokens. Below that nothing")
print("   caches, cached_tokens stays 0, and the request still succeeds — a")
print("   silent no-op, which is why the first thing to check is the size.\n")

# --- B. Implicit -------------------------------------------------------------

print("=" * 78)
print("B. Implicit caching: the default, no parameters")
print("=" * 78)
print("→ request   no prompt_cache_options, no breakpoint, no key")
print("   note      Bedrock places a breakpoint on the latest message itself and")
print("             looks for a reusable prefix. Nothing to configure.")
print("             The probe in step A already sent this prefix, so it is warm")
print("             and both turns below read rather than write.")
for turn in range(2):
    show(f"implicit turn {turn + 1}", ask(QUESTIONS[turn], explicit=False, key=None))
print("   Implicit caching is real and worth having for free. What it does not")
print("   give you is control over WHERE the boundary sits, which matters once")
print("   different parts of your context change at different rates.\n")

# --- C. Explicit -------------------------------------------------------------

print("=" * 78)
print("C. Explicit caching: you mark the boundary")
print("=" * 78)
print("→ request   prompt_cache_options {mode: explicit, ttl: '30m'}")
print("            prompt_cache_breakpoint on the runbook content part")
print(f"            prompt_cache_key '{CACHE_KEY}'")
print("   why      the runbook repeats and the question does not, so the")
print("            boundary belongs between them")
explicit_runs = [show(f"explicit turn {turn + 1}",
                      ask(QUESTIONS[turn], explicit=True, key=CACHE_KEY))
                 for turn in range(2)]
print("   Call 1 writes the prefix, call 2 reads it. This is deterministic on")
print("   GPT-5.6 rather than best-effort — the same numbers come back every")
print("   time, which is what makes it something you can budget against.\n")

# --- D. The cache key is a partition ----------------------------------------

print("=" * 78)
print("D. prompt_cache_key partitions the cache")
print("=" * 78)
print("→ request   the same prefix and breakpoint as step C, but the key now")
print("            carries a per-session suffix, the way a request id or tenant")
print("            id would if you added one 'for observability'")
show("key 'runbook-v1-session-8912'",
     ask(QUESTIONS[2], explicit=True, key=f"{CACHE_KEY}-session-8912"))
show(f"key '{CACHE_KEY}' again", ask(QUESTIONS[3], explicit=True, key=CACHE_KEY))
print("   A different key is a different cache. The prefix was rewritten in full")
print("   at the write rate, and read nothing — so a key that varies per request")
print("   pays the premium on every call and never collects the discount. Key on")
print("   what the prefix is: its identity and its version.\n")

# --- E. Where the prefix lives ----------------------------------------------

print("=" * 78)
print("E. instructions= cannot carry a breakpoint")
print("=" * 78)
print("→ request   the runbook in the top-level instructions field, with")
print("            explicit mode switched on and therefore no breakpoint anywhere")
print("   why this matters   this is what a working implicit workload looks like")
print("                      before someone switches it to explicit mode")
for turn in (4, 5):
    response = client.responses.create(
        model=MODEL_ID,
        instructions=RUNBOOK,
        input=QUESTIONS[turn],
        reasoning={"effort": "none"},
        max_output_tokens=200,
        store=False,
        prompt_cache_key=CACHE_KEY,
        extra_body={"prompt_cache_options": {"mode": "explicit", "ttl": "30m"}},
    )
    show(f"instructions= + explicit, call {turn - 3}", response)
print("   Nothing written, nothing read: explicit mode with no breakpoint is a")
print("   complete opt-out of caching, and a breakpoint cannot be attached to")
print("   instructions. That is strictly worse than leaving it implicit, and it")
print("   raises no error. Move the system text into a marked input_text part,")
print("   which is what step C does.\n")

# --- F. The session ---------------------------------------------------------

print("=" * 78)
print("F. Six turns over one prefix")
print("=" * 78)
print(f"→ request   the same {len(QUESTIONS)} questions, explicit caching, stable key")
print("   note      the prefix is already warm from step C, so every turn here")
print("             reads. A cold session pays one write and then reads.\n")

total_input = total_cached = total_written = 0
for turn, question in enumerate(QUESTIONS, 1):
    total, cached, written = show(f"turn {turn}: {question[:30]}…",
                                  ask(question, explicit=True, key=CACHE_KEY))
    total_input += total
    total_cached += cached
    total_written += written

uncached = total_input - total_cached - total_written
print(f"\n   {len(QUESTIONS)} turns, {total_input} input tokens in total:")
print(f"     {total_cached:>6} read from cache      billed at a large discount")
print(f"     {total_written:>6} written to cache     billed at a premium, once")
print(f"     {uncached:>6} new content          billed at the standard rate")
share = total_cached / total_input
print(f"   {share:.0%} of this session's input arrived through the cache.")
print(
    "\n   The economics: reads are discounted heavily and writes carry a premium,\n"
    "   so the break-even is early — a prefix read even a handful of times has\n"
    "   already paid for its write. Cached input also does not count against the\n"
    "   input-tokens-per-minute quota, which raises the ceiling on a busy loop\n"
    "   as well as lowering the bill."
)
print("\nCurrent cache read and write rates: https://aws.amazon.com/bedrock/pricing/")
