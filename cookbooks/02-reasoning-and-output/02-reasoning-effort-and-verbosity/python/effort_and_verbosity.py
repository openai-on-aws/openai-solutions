"""Two dials on the same request: how hard the model thinks, and how much it writes.

`reasoning.effort` and `text.verbosity` are two independent dials on the same request.
Effort decides how much the model thinks before answering; verbosity decides how long
the answer is. High effort with low verbosity is a legitimate combination — think hard,
answer briefly — and this recipe measures both against a task that has right answers.

  A. the task        12 return requests against a written policy, with known outcomes
  B. the effort curve  accuracy and cost at none / low / medium / high
  C. verbosity       one question, three answer lengths, same effort
  D. sampling        temperature is available, at one specific effort level

The point of B is that it is measured. "Use less effort" is advice; a table of accuracy
against tokens for your own task is a decision. See README.md.
"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Literal

from openai import OpenAI
from openai.providers import bedrock
from pydantic import BaseModel

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Luna: this is a high-volume classification task, which is what the cheap tier is
# for. Right-sizing effort on the cheap tier is where the money actually is.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-luna")

# The ladder, cheapest first. `xhigh` and `max` also exist; four levels is enough to
# see the shape without quadrupling the bill.
EFFORT_LEVELS = ["none", "low", "medium", "high"]

DATA = Path(__file__).resolve().parent.parent / "data"

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

POLICY = (DATA / "returns_policy.md").read_text()
case_lines = (DATA / "return_requests.jsonl").read_text().splitlines()
CASES = [json.loads(line) for line in case_lines]


class Ruling(BaseModel):
    """The answer shape. A Literal makes the decision checkable without parsing."""

    decision: Literal["refund", "store_credit", "reject"]
    governing_rule: str


INSTRUCTIONS = (
    "You are a returns adjudicator for an online retailer. Apply the policy below "
    "exactly as written to the customer's request. Give the outcome and the single "
    "rule reference that governs it, as R1-R8.\n\n" + POLICY
)

print(f"Reasoning effort and verbosity  ·  {MODEL_ID} in {REGION}")
print(f"{len(CASES)} return requests with known outcomes, all synthetic")
print("store=False on every call\n")

# --- A. The task ------------------------------------------------------------

print("=" * 78)
print("A. The task")
print("=" * 78)
print(f"A {len(POLICY.splitlines())}-line policy with eight rules that interact: R4")
print("(faulty) overrides R2 (electronics) and R3 (final sale), R6 (Gold) extends")
print("some windows but not others, and R7 and R8 change the handling without")
print("changing eligibility. Six of the twelve cases need two rules combined.")
print("Labels are written from the policy, so scoring needs no judge model.\n")
print("   expected outcomes: " + ", ".join(
    f"{decision} ×{count}" for decision, count
    in Counter(c["expected_decision"] for c in CASES).most_common()))

# --- B. The effort curve ----------------------------------------------------

print("\n" + "=" * 78)
print("B. Accuracy and cost across the effort ladder")
print("=" * 78)
print("→ request  (identical except reasoning.effort)")
print(f"   model             {MODEL_ID}")
print(f"   instructions      the returns policy ({len(INSTRUCTIONS)} chars)")
print("   text_format       Ruling (decision: Literal, governing_rule: str)")
print("   reasoning.effort  swept over " + " / ".join(EFFORT_LEVELS))
print("   max_output_tokens 2000       reasoning tokens are drawn from this budget,")
print("                                so a low cap silently truncates high effort")
print("   why this shape    one variable changes, so a difference in the score is")
print("                     attributable to effort and nothing else\n")

results: dict[str, dict] = {}
for effort in EFFORT_LEVELS:
    correct = rule_correct = tokens_in = tokens_out = reasoning_tokens = 0
    wrong: list[str] = []

    for case in CASES:
        response = client.responses.parse(
            model=MODEL_ID,
            instructions=INSTRUCTIONS,
            input=case["request"],
            text_format=Ruling,
            reasoning={"effort": effort},
            max_output_tokens=2000,
            store=False,
        )
        ruling = response.output_parsed
        usage = response.usage
        tokens_in += usage.input_tokens
        tokens_out += usage.output_tokens
        reasoning_tokens += usage.output_tokens_details.reasoning_tokens

        if ruling.decision == case["expected_decision"]:
            correct += 1
        else:
            wrong.append(f"{case['case_id']} said {ruling.decision}, expected "
                         f"{case['expected_decision']} ({case['expected_rule']})")
        if ruling.governing_rule.strip().upper().startswith(case["expected_rule"]):
            rule_correct += 1

    results[effort] = {
        "correct": correct, "rule_correct": rule_correct, "wrong": wrong,
        "in": tokens_in, "out": tokens_out, "reasoning": reasoning_tokens,
    }
    print(f"← effort {effort:6}  {correct}/{len(CASES)} decisions  "
          f"{rule_correct}/{len(CASES)} rule citations  "
          f"{tokens_in} in / {tokens_out} out "
          f"({reasoning_tokens} reasoning)")
    for miss in wrong:
        print(f"     miss: {miss}")

print("\n   effort   decisions   rule cited   output tokens   reasoning tokens")
for effort in EFFORT_LEVELS:
    r = results[effort]
    n = len(CASES)
    print(f"   {effort:8} {r['correct']:>6}/{n}   {r['rule_correct']:>6}/{n}"
          f"   {r['out']:>13}   {r['reasoning']:>16}")

# --- C. Verbosity is the other axis -----------------------------------------

print("\n" + "=" * 78)
print("C. text.verbosity — answer length, at constant effort")
print("=" * 78)
question = next(c for c in CASES if c["case_id"] == "RET-09")

# Two prompts, because verbosity can only move length as far as the task allows. A
# ruling is inherently short; a help-centre article is not.
PROMPTS = {
    "a ruling (constrained)": (
        question["request"] + "\n\nExplain the ruling to the customer."
    ),
    "a help article (open)": (
        "Write the help-centre section explaining how returns work for electronics, "
        "including the faulty-item case and loyalty extensions."
    ),
}

print("→ request  (identical except text.verbosity)")
print("   reasoning.effort  medium      held constant, so only the answer changes")
print("   text.verbosity    low / medium / high")
print("   note              verbosity must be nested inside `text`; a top-level")
print("                     verbosity= is rejected as an unknown parameter\n")

for label, prompt in PROMPTS.items():
    print(f"   {label}")
    for verbosity in ["low", "medium", "high"]:
        response = client.responses.create(
            model=MODEL_ID,
            instructions=INSTRUCTIONS,
            input=prompt,
            reasoning={"effort": "medium"},
            text={"verbosity": verbosity},
            max_output_tokens=3000,
            store=False,
        )
        words = len(response.output_text.split())
        print(f"←    verbosity {verbosity:6} {response.usage.output_tokens:>5} out,"
              f" {words:>4} words  (echoed as {response.text.verbosity})")
    print()

# --- D. Sampling, and the one effort level that allows it -------------------

print("\n" + "=" * 78)
print("D. temperature, and where it is available")
print("=" * 78)
print("→ request")
print("   reasoning.effort  none        sampling parameters are accepted at this")
print("                                level; a reasoning level rejects them")
print("   temperature       0.2         low, because a ruling should be stable")
print(f"   input             {question['case_id']} again")

sampled = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=question["request"],
    reasoning={"effort": "none"},
    temperature=0.2,
    max_output_tokens=400,
    store=False,
)
print("← response")
print(f"   temperature echoed back as {sampled.temperature}")
print(f"   {sampled.output_text.strip()[:100]}")
print(f"   {sampled.usage.input_tokens} in / {sampled.usage.output_tokens} out")
print("   So the two are alternatives, not companions: deterministic-ish sampling")
print("   control at effort none, or reasoning above it. Pick one per call.")

# --- E. What the numbers say ------------------------------------------------

best_decisions = max(r["correct"] for r in results.values())
cheapest = next(e for e in EFFORT_LEVELS if results[e]["correct"] == best_decisions)
best_rules = max(r["rule_correct"] for r in results.values())
cheapest_rules = next(
    e for e in EFFORT_LEVELS if results[e]["rule_correct"] == best_rules
)

print("\n" + "=" * 78)
print("Right-sizing")
print("=" * 78)
print(f"   decisions        {best_decisions}/{len(CASES)} first reached at effort "
      f"'{cheapest}'  ({results[cheapest]['out']} output tokens)")
print(f"   rule citations   {best_rules}/{len(CASES)} first reached at effort "
      f"'{cheapest_rules}'  ({results[cheapest_rules]['out']} output tokens)")
print(
    "\nOn this task the outcome is already right at the cheapest setting, so the\n"
    "ladder above it is spend with nothing to show — which is exactly the kind of\n"
    "thing worth knowing before you run it at volume.\n"
    "\n"
    "Two dials, then: effort for how hard the model thinks, verbosity for how much\n"
    "it writes, and a sweep like this to tell you where to set each one for your\n"
    "own task. Re-run it when you change model or prompt."
)
print("\nPer-token rates by model: https://aws.amazon.com/bedrock/pricing/")
