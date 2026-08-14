"""Let the model call your systems: the Responses tool loop, end to end.

A field service engineer needs answers that live in a parts system and a contract
system. The model cannot reach either, so it asks — and your code answers. That is the
whole of tool calling, and on the Responses API it has a specific shape worth learning
exactly once.

  A. declare      the flat tool schema, and why it is flat
  B. one round    function_call out, function_call_output back, answer
  C. in parallel  one question, two lookups, issued together
  D. tool_choice  auto, none, and forcing a specific tool
  E. the loop     keep going until the model stops asking

The functions here read a committed JSON file. In production they would be your API
calls; nothing else about the shape changes. See README.md.
"""

import json
import os
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Terra: deciding which of three tools to call, and reading the results back into
# a recommendation, is exactly the mid-tier's job.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

DATA = Path(__file__).resolve().parent.parent / "data"
RECORDS = json.loads((DATA / "service_records.json").read_text())

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

# --- The tools your code actually runs ---------------------------------------


def find_part(description: str, machine_model: str = "") -> dict:
    """Search the catalogue by free-text description, optionally for one model."""
    matches = {
        number: part for number, part in RECORDS["parts"].items()
        if any(w in part["description"].lower() for w in description.lower().split())
        and (not machine_model or machine_model in part["machine_models"])
    }
    return {"matches": [
        {"part_number": n, "description": p["description"], "on_hand": p["on_hand"]}
        for n, p in matches.items()
    ]}


def get_part_availability(part_number: str) -> dict:
    """Stock, lead time and price for one part number."""
    part = RECORDS["parts"].get(part_number)
    if part is None:
        return {"error": f"no such part number: {part_number}"}
    return {"part_number": part_number, "on_hand": part["on_hand"],
            "lead_time_days": part["lead_time_days"],
            "stocking_location": part["stocking_location"],
            "unit_price_pence": part["unit_price_pence"]}


def get_machine_cover(serial_number: str) -> dict:
    """Warranty and service-contract position for one machine."""
    machine = RECORDS["machines"].get(serial_number)
    if machine is None:
        return {"error": f"no such serial number: {serial_number}"}
    return {"serial_number": serial_number, "model": machine["model"],
            "warranty_expires": machine["warranty_expires"],
            "service_contract": machine["service_contract"],
            "contract_covers_parts": machine["contract_covers_parts"]}


TOOL_FUNCTIONS = {
    "find_part": find_part,
    "get_part_availability": get_part_availability,
    "get_machine_cover": get_machine_cover,
}

# The Responses API tool schema is FLAT: type, name, description and parameters sit at
# the top level of the entry. The Chat Completions shape nests all of that under a
# "function" key, and sending that here is rejected outright — see README.md.
TOOLS = [
    {
        "type": "function",
        "name": "find_part",
        "description": "Search the parts catalogue by description. Use when the "
                       "engineer describes a component but has no part number.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string",
                                "description": "Free text, e.g. 'rod seal 45mm'"},
                "machine_model": {
                    "type": "string",
                    "description": "Optional model filter, e.g. 'VL-880S'",
                },
            },
            "required": ["description"],
        },
    },
    {
        "type": "function",
        "name": "get_part_availability",
        "description": "Stock, lead time, location and price for a part number.",
        "parameters": {
            "type": "object",
            "properties": {"part_number": {"type": "string"}},
            "required": ["part_number"],
        },
    },
    {
        "type": "function",
        "name": "get_machine_cover",
        "description": "Warranty expiry and service-contract position for a machine "
                       "serial number, including whether parts are covered.",
        "parameters": {
            "type": "object",
            "properties": {"serial_number": {"type": "string"}},
            "required": ["serial_number"],
        },
    },
]

INSTRUCTIONS = (
    "You support field service engineers at an industrial press manufacturer. Use the "
    "tools to check parts and cover before answering — never state stock, lead time, "
    "price or warranty position from memory. Give the engineer a short recommendation "
    "with the numbers you retrieved."
)


def run_tools(response) -> list[dict]:
    """Execute every function_call in a response and build the results to send back.

    A function_call carries a `call_id`, and the result must quote it so the model can
    match answer to question. That pairing is the only bookkeeping in the protocol.
    """
    outputs = []
    for item in response.output:
        if item.type != "function_call":
            continue
        arguments = json.loads(item.arguments)
        result = TOOL_FUNCTIONS[item.name](**arguments)
        shown = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        print(f"   ↳ ran {item.name}({shown})")
        print(f"     → {json.dumps(result)[:96]}")
        outputs.append({
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": json.dumps(result),
        })
    return outputs


print(f"Tool calling  ·  {MODEL_ID} in {REGION}")
print(f"{len(TOOLS)} tools over a committed JSON file, all synthetic")
print("store=False on every call\n")

# --- A. The declaration -----------------------------------------------------

print("=" * 78)
print("A. The tool declaration")
print("=" * 78)
for tool in TOOLS:
    params = ", ".join(tool["parameters"]["properties"])
    print(f"   {tool['name']:22} ({params})")
print("\n   Note the shape: type, name, description and parameters are all at the")
print("   top level of the entry. There is no nested 'function' object here — that")
print("   is the Chat Completions shape, and it is rejected on this API.\n")

# --- B. One round trip ------------------------------------------------------

question = ("The rod seal has failed on press VLC-880-01192. Can I get a replacement "
            "today, and is it covered?")

print("=" * 78)
print("B. One question, start to finish")
print("=" * 78)
print("→ request")
print(f"   model             {MODEL_ID}")
print(f"   tools             {len(TOOLS)} declared")
print("   tool_choice       auto (the default) — the model decides")
print("   max_output_tokens 900")
print(f"   input             {question}")

conversation: list = [{"role": "user", "content": question}]
first = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=conversation,
    tools=TOOLS,
    max_output_tokens=900,
    store=False,
)
calls = [i for i in first.output if i.type == "function_call"]
print("← response  (no answer yet — the model is asking)")
print(f"   output item types: {[i.type for i in first.output]}")
print(f"   {len(calls)} function_call item(s), each with its own call_id")
for call in calls:
    print(f"     {call.name}  call_id={call.call_id[:18]}…  args={call.arguments}")
print(f"   {first.usage.input_tokens} in / {first.usage.output_tokens} out\n")

# Carry the model's own output forward unmodified, then append the results.
print("→ request  (round 2: the same conversation plus the tool results)")
conversation += first.output
conversation += run_tools(first)

# The model may need more than one round: a first answer can raise a second
# question. Keep going until it stops asking, which is the whole protocol.
for extra_round in range(2, 5):
    following = client.responses.create(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=conversation,
        tools=TOOLS,
        max_output_tokens=900,
        store=False,
    )
    still_asking = [i for i in following.output if i.type == "function_call"]
    usage = following.usage
    print(f"←  round {extra_round}  {len(still_asking)} tool call(s)  "
          f"{usage.input_tokens} in / {usage.output_tokens} out")
    conversation += following.output
    if not still_asking:
        for line in following.output_text.strip().splitlines():
            if line.strip():
                print(f"     {line.strip()[:90]}")
        break
    conversation += run_tools(following)
print()

# --- C. Parallel calls ------------------------------------------------------

print("=" * 78)
print("C. Two lookups at once")
print("=" * 78)
parallel_question = ("Compare part VL-4471-SEAL and VL-4472-SEAL for availability — "
                     "which can I fit this week?")
print("→ request")
print(f"   input             {parallel_question}")
print("   why this shape    the two lookups do not depend on each other, so there")
print("                     is no reason to serialize them")

parallel = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=[{"role": "user", "content": parallel_question}],
    tools=TOOLS,
    max_output_tokens=900,
    store=False,
)
parallel_calls = [i for i in parallel.output if i.type == "function_call"]
print(f"← response  {len(parallel_calls)} function_call item(s) in a single response")
for call in parallel_calls:
    print(f"     {call.name}({call.arguments})")
print("   All of them arrive together, so your code can execute them concurrently")
print("   and send every result back in one request.\n")

# --- D. tool_choice ---------------------------------------------------------

print("=" * 78)
print("D. tool_choice: who decides")
print("=" * 78)
simple = "What is a rod seal for, in one sentence?"
for choice, why in [
    ("auto", "the default: the model calls a tool if it judges one is needed"),
    ("none", "answer from context only, tools stay declared but unusable"),
    ("required", "must call something, even for a general question"),
]:
    response = client.responses.create(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=[{"role": "user", "content": simple}],
        tools=TOOLS,
        tool_choice=choice,
        max_output_tokens=600,
        store=False,
    )
    names = [i.name for i in response.output if i.type == "function_call"]
    print(f"←  tool_choice={choice:9} calls={names or 'none'}")
    print(f"      {why}")

forced = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=[{"role": "user", "content": "Check press VLC-920-00447 for me."}],
    tools=TOOLS,
    tool_choice={"type": "function", "name": "get_machine_cover"},
    max_output_tokens=600,
    store=False,
)
forced_names = [i.name for i in forced.output if i.type == "function_call"]
print(f"←  tool_choice=get_machine_cover  calls={forced_names}")
print("      naming one tool pins the first call to it, which is how you keep a")
print("      workflow on rails when you already know what has to happen first\n")

# --- E. The loop ------------------------------------------------------------

print("=" * 78)
print("E. The loop, until the model stops asking")
print("=" * 78)
loop_question = ("Press VLC-880-00031 has a failed rod seal and I need to quote the "
                 "customer. What is the part, what does it cost, and who pays?")
print("→ request")
print(f"   input          {loop_question}")
print("   max rounds     4     a bound is not optional: a loop with no ceiling is")
print("                        a way to spend money without a plan\n")

history: list = [{"role": "user", "content": loop_question}]
rounds = 0
MAX_ROUNDS = 4
total_in = total_out = 0
while rounds < MAX_ROUNDS:
    rounds += 1
    response = client.responses.create(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=history,
        tools=TOOLS,
        max_output_tokens=900,
        store=False,
    )
    total_in += response.usage.input_tokens
    total_out += response.usage.output_tokens
    pending = [i for i in response.output if i.type == "function_call"]
    print(f"←  round {rounds}: {len(pending)} tool call(s), "
          f"{response.usage.input_tokens} in / {response.usage.output_tokens} out")
    history += response.output
    if not pending:
        for line in response.output_text.strip().splitlines():
            if line.strip():
                print(f"     {line.strip()[:92]}")
        break
    history += run_tools(response)
else:
    print(f"   stopped at the {MAX_ROUNDS}-round ceiling without a final answer")

print(f"\n   {rounds} round(s), {total_in} input tokens, {total_out} output tokens.")
print(
    "\n   Input grows every round, because the conversation carries the tool calls\n"
    "   and their results forward. That is the cost model of a tool loop: not the\n"
    "   number of calls, but the transcript they accumulate — which is why a\n"
    "   stable instruction prefix is worth caching in a loop like this."
)
print("\nPer-token rates by model: https://aws.amazon.com/bedrock/pricing/")
