"""Score a grounded answer against its sources, and refuse to publish what fails.

A citizen-facing information service can only publish what its documents support. This
recipe answers questions from a small document set, then puts every answer through
Bedrock Guardrails' **contextual grounding** check, which returns two numbers: is the
answer supported by the source, and does it address the question.

  A. the guardrail  created here, with the two filters and their thresholds visible
  B. answer + score four questions, each answer graded for grounding and relevance
  C. the range      what an unsupported answer scores, so you can place a threshold
  D. refusals       why they score low, and what to do about it
  E. clean up       the guardrail is deleted

Guardrails are not applied inline on this endpoint: screening is a separate
ApplyGuardrail call, which is why it can run after the answer and in parallel with
anything else. See README.md for what that buys.
"""

import json
import os
from pathlib import Path

import boto3
from openai import OpenAI
from openai.providers import bedrock

# --- Change these ---------------------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Terra: answering from supplied passages is comprehension, and the interesting
# question here is whether the answer is faithful, not whether it is clever.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Set GUARDRAIL_ID to reuse an existing guardrail and skip creation. Creating one
# needs bedrock:CreateGuardrail, a much larger grant than bedrock:ApplyGuardrail,
# and a restricted role may hold only the second.
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID")

# Below these, the answer is held back. 0.75 is deliberately demanding for a
# citizen-facing service; a lower bar suits an internal draft.
GROUNDING_THRESHOLD = 0.75
RELEVANCE_THRESHOLD = 0.75

DATA = Path(__file__).resolve().parent.parent / "data"

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)
# Guardrails live on bedrock-runtime and are reached with boto3, not the OpenAI SDK.
# ApplyGuardrail never invokes a model, so it does not care which endpoint answered.
bedrock_control = boto3.client("bedrock", region_name=REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

doc_lines = (DATA / "scheme_documents.jsonl").read_text().splitlines()
DOCUMENTS = [json.loads(line) for line in doc_lines]
CORPUS = "\n\n".join(f"[{d['doc_id']}] {d['title']}\n{d['text']}" for d in DOCUMENTS)

QUESTIONS = [
    "I rent privately and my landlord agrees. Can I apply, and what could I get for a "
    "stairlift?",
    "How long will a decision take, and what can I do if I disagree with it?",
    "I live in a council flat. Do I apply through this scheme?",
    "Does the grant cover replacing my garden fence and repainting the hall?",
]

INSTRUCTIONS = (
    "You answer residents' questions about a local authority grant, using only the "
    "scheme documents below. Quote the figures exactly as written. Cite the document "
    "id you relied on, like [HAG-02]. If the documents do not answer the question, say "
    "so plainly and say who to contact instead — never fill the gap from general "
    "knowledge.\n\n" + CORPUS
)

print(f"Scoring a grounded answer  ·  {MODEL_ID} in {REGION}")
print(f"{len(DOCUMENTS)} scheme documents, all synthetic  ·  store=False\n")

# --- A. The guardrail, and what is in it ----------------------------------------------

print("=" * 78)
print("A. The guardrail")
print("=" * 78)

created_here = GUARDRAIL_ID is None
if created_here:
    print("→ request   bedrock:CreateGuardrail")
    print("   contextualGroundingPolicyConfig")
    print(f"     GROUNDING  threshold {GROUNDING_THRESHOLD}   is the answer supported")
    print("                                    by the source text")
    print(f"     RELEVANCE  threshold {RELEVANCE_THRESHOLD}   does the answer address")
    print("                                    the question that was asked")
    print("   why this shape   two filters, because an answer can be highly relevant")
    print("                    and still invented — they are separate failures")

    created = bedrock_control.create_guardrail(
        name="cookbook-grounded-answer-check",
        description="Scores a grounded answer for faithfulness to its sources.",
        contextualGroundingPolicyConfig={"filtersConfig": [
            {"type": "GROUNDING", "threshold": GROUNDING_THRESHOLD},
            {"type": "RELEVANCE", "threshold": RELEVANCE_THRESHOLD},
        ]},
        blockedInputMessaging="Held back: input failed the configured checks.",
        blockedOutputsMessaging="Held back: this answer failed the grounding check.",
    )
    GUARDRAIL_ID = created["guardrailId"]
    version = bedrock_control.create_guardrail_version(
        guardrailIdentifier=GUARDRAIL_ID, description="cookbook run",
    )["version"]
    print("← response")
    print(f"   guardrail created, version {version}, status "
          f"{bedrock_control.get_guardrail(guardrailIdentifier=GUARDRAIL_ID)['status']}")
    print("   deleted again in step E\n")
else:
    version = os.environ.get("GUARDRAIL_VERSION", "1")
    print(f"   reusing the guardrail in GUARDRAIL_ID at version {version}")
    print("   it must carry a contextualGroundingPolicy for this recipe to work\n")


def score(question: str, answer: str) -> dict:
    """Score one answer against the corpus. Returns the two filter results.

    The qualifiers are what make this a grounding check rather than a content scan:
    `grounding_source` marks the text the answer must be faithful to, and `query`
    marks the question it must address.
    """
    result = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=str(version),
        source="OUTPUT",
        content=[
            {"text": {"text": CORPUS, "qualifiers": ["grounding_source"]}},
            {"text": {"text": question, "qualifiers": ["query"]}},
            {"text": {"text": answer}},
        ],
    )
    filters = {
        f["type"]: f
        for assessment in result.get("assessments", [])
        for f in assessment.get("contextualGroundingPolicy", {}).get("filters", [])
    }
    return {"action": result["action"], "filters": filters}


# --- B. Answer, then score ------------------------------------------------------------

print("=" * 78)
print("B. Answer from the documents, then score the answer")
print("=" * 78)
print("→ request  (per question)")
print(f"   model             {MODEL_ID}")
print(f"   instructions      the four scheme documents ({len(CORPUS)} chars) plus")
print("                     'if the documents do not answer it, say so'")
print("   max_output_tokens 700")
print("   then              ApplyGuardrail on the answer, with the same documents")
print("                     passed as the grounding_source\n")

published = held = 0
for question in QUESTIONS:
    response = client.responses.create(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=question,
        max_output_tokens=700,
        store=False,
    )
    answer = response.output_text.strip()
    verdict = score(question, answer)
    grounding = verdict["filters"].get("GROUNDING", {})
    relevance = verdict["filters"].get("RELEVANCE", {})
    ok = verdict["action"] == "NONE"
    published += ok
    held += not ok

    print(f"← Q  {question[:66]}")
    print(f"     {answer.replace(chr(10), ' ')[:150]}")
    print(f"     GROUNDING {grounding.get('score')}  RELEVANCE {relevance.get('score')}"
          f"   → {'publish' if ok else 'HOLD'}")
    usage = response.usage
    print(f"     {usage.input_tokens} in / {usage.output_tokens} out\n")

print(f"   {published} of {len(QUESTIONS)} cleared both thresholds, {held} held\n")

# --- C. Where an unsupported answer lands ---------------------------------------------

print("=" * 78)
print("C. Where an unsupported answer lands")
print("=" * 78)
question = QUESTIONS[0]
# Written by hand, not by the model: plausible prose, wrong figure, invented rule.
# This is the control arm — a check that never fires is not a check.
INVENTED = (
    "Yes, private tenants can apply. The maximum award for a stairlift is 25,000 per "
    "property each year, and there is an additional 3,000 hardship top-up for "
    "applicants over 70. Decisions are issued within 5 working days."
)
print("→ request   ApplyGuardrail, same guardrail, same grounding_source")
print(f"   answer under test   {INVENTED[:64]}…")
print("   why score this       to place a threshold you need to know what both")
print("                        ends of the range look like on your own content")

verdict = score(question, INVENTED)
grounding = verdict["filters"].get("GROUNDING", {})
relevance = verdict["filters"].get("RELEVANCE", {})
print("← response")
print(f"   action     {verdict['action']}")
print(f"   GROUNDING  {grounding.get('score')}  "
      f"(threshold {grounding.get('threshold')}) → {grounding.get('action')}")
print(f"   RELEVANCE  {relevance.get('score')}  "
      f"(threshold {relevance.get('threshold')}) → {relevance.get('action')}")
print("   Note the split: this answer is entirely relevant — it addresses the")
print("   question in the right shape — and scores near zero on grounding. That is")
print("   why both filters are configured: relevance alone would publish it.\n")

# --- D. Refusals need a different path ------------------------------------------------

print("=" * 78)
print("D. Refusals need a different path")
print("=" * 78)
UNANSWERABLE = "Can I get help with my heating costs this winter?"
print("→ request")
print(f"   input      {UNANSWERABLE}")
print("   note       the documents say nothing about heating, so the instructions")
print("              tell the model to decline and redirect rather than guess")

refusal = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=UNANSWERABLE,
    max_output_tokens=400,
    store=False,
).output_text.strip()
print("← response")
print(f"   {refusal.replace(chr(10), ' ')[:140]}")

verdict = score(UNANSWERABLE, refusal)
grounding = verdict["filters"].get("GROUNDING", {})
relevance = verdict["filters"].get("RELEVANCE", {})
print(f"   scored:  action {verdict['action']}   "
      f"GROUNDING {grounding.get('score')}   RELEVANCE {relevance.get('score')}")
print("   A refusal makes no claims *from* the source, so a faithfulness score has")
print("   nothing to measure and comes back low. Apply the grounding gate to answers")
print("   that assert something, and route the ones that decline separately — a")
print("   schema field saying whether the question was answered is enough to tell")
print("   them apart before you decide what to score.\n")

# --- E. Clean up ----------------------------------------------------------------------

print("=" * 78)
print("E. Clean up")
print("=" * 78)
if created_here:
    bedrock_control.delete_guardrail(guardrailIdentifier=GUARDRAIL_ID)
    print("   guardrail deleted")
else:
    print("   guardrail was supplied via GUARDRAIL_ID, so it is left alone")
print("   inference and screening create nothing else; store=False leaves no response")
print("\nGuardrails are billed per policy evaluated, on top of tokens:")
print("https://aws.amazon.com/bedrock/pricing/")
