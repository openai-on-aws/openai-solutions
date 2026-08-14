"""Grounded regulatory change monitoring with native Web Search on Bedrock.

A compliance team needs to know what changed and where each claim came from. Bedrock's
Web Search is a server-side built-in tool: you declare it, and Bedrock runs the whole
retrieval lifecycle against an AWS-operated web index — no search provider to contract
with, no API key to rotate, no client-side tool loop to write. The model searches when
it needs to, and the answer comes back with citations attached.

This script asks the same question without the tool and with it, shows the retrieval
steps and citations the response carries, and builds a sourced digest over a watchlist.
Each phase ends with what it cost.

Synthetic data: data/watchlist.json — a fabricated watchlist for a fictional bank. The
regulations named are real public instruments; the institution and owners are invented.

Web Search is billed per retrieval operation, separately from tokens.

Run it from the cookbooks/ directory:

    uv run python \\
      03-grounding-and-multimodal/01-grounded-regulatory-monitoring/python/grounded_monitoring.py

See README.md for the narrative.
"""

import json
import os
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Web Search is available in us-east-1, us-east-2 and us-west-2, and is strictly
# regional: queries, fetches and index data do not cross Regions.
# https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html

# A grounded turn runs several retrieval steps server-side, so it takes longer than a
# plain call. Give it a timeout that reflects that.
TIMEOUT_SECONDS = 300.0

# The retrieval budget for one turn. Each web_search_call item is one billed operation,
# so this is the cost control on a grounded turn.
MAX_TOOL_CALLS = 8

ANALYST_INSTRUCTIONS = (
    "You are a regulatory change analyst at a retail bank. Search for current "
    "information, then write the answer. Do not run more than two rounds of "
    "searches. Every factual claim must come from a retrieved source. If the "
    "retrieved sources do not settle the question, say so explicitly and do not "
    "estimate, infer or fill the gap from memory."
)

# The control in phase A has no tool, so it gets the same role without the instruction
# to search. Telling a model to search when it cannot only produces a hedge, which
# would not be a fair comparison.
UNGROUNDED_INSTRUCTIONS = (
    "You are a regulatory change analyst at a retail bank. Answer the question as "
    "precisely as you can."
)

WATCHLIST = json.loads(
    (Path(__file__).parent.parent / "data" / "watchlist.json").read_text()
)
TOPICS = WATCHLIST["topics"]

# external_web_access defaults to *true*, matching the OpenAI Responses API so a ported
# call does not have to change. At true, search and fetch are permitted to reach the
# live external web directly, which requires the request identity to hold
# bedrock-websearch:ExternalWebAccess.
#
# false keeps retrieval inside the AWS boundary, served from the Bedrock web index and
# cache. That is the posture a regulated workload wants, and it needs no permission
# beyond the two Web Search actions.
#
# search_context_size controls how many tokens of retrieved content are injected per
# search: low | medium | high, and it is the main lever on what a grounded turn costs.
# See https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html
WEB_SEARCH = {
    "type": "web_search",
    "external_web_access": False,
    "search_context_size": "medium",
}

client = OpenAI(provider=bedrock(region=REGION), timeout=TIMEOUT_SECONDS, max_retries=2)

print(f"Model: {MODEL_ID}    Region: {REGION}")
print(f"Watchlist: {WATCHLIST['institution']} / {WATCHLIST['register_owner']}, "
      f"{len(TOPICS)} topics")

first_topic = TOPICS[0]


def citations_of(response) -> list:
    """Every url_citation annotation on the message content."""
    found = []
    for message in [item for item in response.output if item.type == "message"]:
        for part in message.content:
            found.extend(getattr(part, "annotations", []) or [])
    return found


# --- A. Without the tool: the answer you cannot file ------------------------

# A model asked about current regulation answers from what it was trained on. The answer
# reads well; what it does not have is a source, which for a compliance digest is the
# only thing that matters.

print(f"\nA. Ungrounded — {first_topic['id']} {first_topic['subject']}")
print("→ request")
print(f"   model             {MODEL_ID}")
print("   tools             none        (the control: what the model knows unaided)")
print(f"   question          {first_topic['question'][:72]}…")

ungrounded = client.responses.create(
    model=MODEL_ID,
    instructions=UNGROUNDED_INSTRUCTIONS,
    input=first_topic["question"],
    # Generous, because a "what changed recently" question makes the model reason hard
    # before it writes anything — see the printed reasoning-token count.
    max_output_tokens=2500,
    store=False,
)
print("← response")
print(f"   {ungrounded.output_text.strip()[:220]}...")
print(f"   cost: {ungrounded.usage.input_tokens} input tokens, "
      f"{ungrounded.usage.output_tokens} output "
      f"({ungrounded.usage.output_tokens_details.reasoning_tokens} reasoning), "
      f"0 searches, {len(citations_of(ungrounded))} citations")

# --- B. With the tool: one declaration, and Bedrock does the rest -----------

# No tool implementation, no search API key, and no loop that receives a call, runs it
# and sends the result back. Bedrock decides when to search, issues the queries, fetches
# pages when it wants them, and grounds the answer.

print(f"\nB. Grounded — {first_topic['id']}")
print("→ request   the same question, plus one tool")
print(f"   tools             {json.dumps(WEB_SEARCH)}")
print(f"   max_tool_calls    {MAX_TOOL_CALLS}         cap on billed retrieval steps")
print("   instructions      analyst role: search, cite every claim, refuse if the")
print("                     sources do not settle it")

grounded = client.responses.create(
    model=MODEL_ID,
    instructions=ANALYST_INSTRUCTIONS,
    input=first_topic["question"],
    tools=[WEB_SEARCH],
    max_tool_calls=MAX_TOOL_CALLS,
    max_output_tokens=3000,
    store=False,
)
searches = [item for item in grounded.output if item.type == "web_search_call"]
grounded_citations = citations_of(grounded)

print("← response")
print(f"   {grounded.output_text.strip()[:220]}...")
print(f"   cost: {grounded.usage.input_tokens} input tokens, "
      f"{grounded.usage.output_tokens} output, {len(searches)} searches, "
      f"{len(grounded_citations)} citations")
print("   Retrieved content enters the input, so a grounded turn is bigger on input")
print("   tokens as well as carrying a per-operation search fee.")

# --- C. The response shows its work ----------------------------------------

# Retrieval steps and citations are first-class items on the response, which is what
# makes a grounded answer auditable rather than merely confident.

print("\nC. What the response carries")

for call in searches:
    action = call.action
    queries = getattr(action, "queries", None) or []
    print(f"   {call.status:10s} {action.type:10s} {len(queries)} query string(s)")
    for query in queries[:2]:
        print(f"      {query[:84]}")
    if getattr(action, "url", None):
        print(f"      fetched: {action.url[:84]}")

print(f"\n   {len(grounded_citations)} citation annotation(s), "
      f"{len({c.url for c in grounded_citations})} distinct sources")
for url in sorted({c.url for c in grounded_citations}):
    print(f"      {url[:100]}")
print("   Each annotation carries a title, a URL and the character span of the answer")
print("   it is attached to, so a reader can be shown the source in place.")
print("   cost of this phase: 0 extra calls — it is all on the response from B")

# --- D. The digest ---------------------------------------------------------

# The deliverable: one sourced entry per watchlist topic, with the retrieval steps and
# sources recorded next to each so the digest can be reviewed and filed.

print("\nD. Digest for the rest of the watchlist")
print(f"→ request   one grounded call per topic, search_context_size="
      f"{WEB_SEARCH['search_context_size']}")
print("            each answer capped at three sentences, so the digest stays short")

for topic in TOPICS[1:]:
    response = client.responses.create(
        model=MODEL_ID,
        instructions=ANALYST_INSTRUCTIONS,
        input=f"{topic['question']} Answer in at most three sentences.",
        tools=[WEB_SEARCH],
        max_tool_calls=MAX_TOOL_CALLS,
        max_output_tokens=3000,
        store=False,
    )
    topic_searches = [i for i in response.output if i.type == "web_search_call"]
    topic_citations = citations_of(response)

    print(f"\n   {topic['id']}  {topic['subject']}  (owner: {topic['internal_owner']})")
    print(f"      {response.output_text.strip()[:200]}")
    for url in sorted({c.url for c in topic_citations})[:3]:
        print(f"      source: {url[:96]}")
    print(f"      cost: {response.usage.input_tokens} input tokens, "
          f"{response.usage.output_tokens} output, {len(topic_searches)} searches, "
          f"{len(topic_citations)} citations")

print("\n   Count the web_search_call items to budget: one item is one billed")
print("   operation, however many query strings it carries. Rates are on")
print("   https://aws.amazon.com/bedrock/pricing/")

# --- E. The lever that decides what a grounded turn costs -------------------

# Retrieved content is injected into the input, so input tokens dominate a grounded
# turn's token bill. search_context_size sets how much gets injected per search, and the
# range is wide enough to be a real design choice rather than a tuning detail.
#
# The question is held constant here on purpose: input tokens also scale with how many
# searches the model runs, so comparing different questions tells you nothing.

print("\nE. search_context_size, on one question")

CONTEXT_QUESTION = (
    "What are the verification of payee obligations under the EU Instant Payments "
    "Regulation? Answer in two sentences."
)
ONE_ROUND = (
    "Search once, then answer from the retrieved sources. Do not run more than one "
    "round of searches."
)

print(f"→ request   {CONTEXT_QUESTION[:70]}…")
print("            one question, three settings, max_tool_calls=2 — held constant")
print("            because input tokens also scale with the number of searches")

for size in ("low", "medium", "high"):
    sized = client.responses.create(
        model=MODEL_ID,
        instructions=ONE_ROUND,
        input=CONTEXT_QUESTION,
        tools=[{**WEB_SEARCH, "search_context_size": size}],
        max_tool_calls=2,
        max_output_tokens=2000,
        store=False,
    )
    sized_searches = [i for i in sized.output if i.type == "web_search_call"]
    print(f"   {size:6s} {sized.usage.input_tokens:6d} input tokens   "
          f"{len(sized_searches)} search(es)   "
          f"{len(citations_of(sized))} citations")

print("   Fewer injected tokens is cheaper per turn and gives the model less to work")
print("   with. medium is a good default; high is worth it when an answer depends on")
print("   detail buried in a long page.")
