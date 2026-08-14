"""An agent loop from first principles: a goal, some tools, and a bound.

The tool-calling recipe answered a question. An agent is given a **goal** and
decides for itself how many steps to take. The code is the same protocol —
`function_call` out and `function_call_output` back — wrapped in a loop with three
things a question does not need: a stopping condition, a ceiling, and a record.

  A. the tools     four reads and one write, and why the write is different
  B. the goal       one instruction, no script
  C. the loop       until the agent stops asking, with a hard round limit
  D. the trace      every tool call it made, in order, with what it cost
  E. what to check  the questions to ask before letting a loop act unsupervised

The write tool here only mutates an in-memory dict. In production that is the decision
needing the most thought — see README.md.
"""

import json
import os
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock

from cookbook_utils import delete_stored_responses

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Terra: an agent has to hold constraints across steps, which is more than
# classification and less than research.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# A loop with no ceiling is a way to spend money without a plan.
MAX_ROUNDS = 8

DATA = Path(__file__).resolve().parent.parent / "data"
WORLD = json.loads((DATA / "disruption.json").read_text())

# What the agent changes. Kept separate from WORLD so the writes are visible.
REBOOKINGS: dict[str, dict] = {}

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

# --- A. The tools -----------------------------------------------------------


def get_flight(flight_number: str) -> dict:
    """Status, route and seat availability for one flight."""
    flight = WORLD["flights"].get(flight_number)
    if flight is None:
        return {"error": f"unknown flight {flight_number}"}
    return {"flight_number": flight_number, **flight}


def list_affected_passengers(flight_number: str) -> dict:
    """Everyone booked on a disrupted flight, with their constraints."""
    return {"flight_number": flight_number,
            "passengers": WORLD["passengers"].get(flight_number, [])}


def find_alternatives(origin: str, destination: str) -> dict:
    """Flights that could get someone from origin to destination, direct or not."""
    direct, connecting = [], []
    for number, flight in WORLD["flights"].items():
        route_from, route_to = flight["route"].split("-")
        if flight["status"] != "on time":
            continue
        if route_from == origin and route_to == destination:
            direct.append({"flight_number": number, **flight})
        elif route_from == origin:
            for second_number, second in WORLD["flights"].items():
                second_from, second_to = second["route"].split("-")
                if (second["status"] == "on time" and second_from == route_to
                        and second_to == destination
                        and second["scheduled"] > flight["scheduled"]):
                    connecting.append({"leg_1": {"flight_number": number, **flight},
                                       "leg_2": {"flight_number": second_number,
                                                 **second}})
    return {"direct": direct, "connecting": connecting}


def get_entitlements(tier: str) -> dict:
    """What a loyalty tier is owed during a disruption."""
    entitlement = WORLD["entitlements"].get(tier)
    if entitlement is None:
        return {"error": f"unknown tier {tier}"}
    return {"tier": tier, **entitlement}


def rebook_passenger(passenger_id: str, flight_numbers: str, reason: str) -> dict:
    """THE WRITE. Commit a passenger to one or more flights.

    Seat availability is decremented here, so the agent's own later calls see the
    consequences of its earlier ones — which is what makes this a loop rather than a
    batch of independent questions.
    """
    legs = [leg.strip() for leg in flight_numbers.split(",") if leg.strip()]
    party = 1
    for passenger in WORLD["passengers"].get("AE414", []):
        if passenger["passenger_id"] == passenger_id:
            party = passenger["party_size"]
    for leg in legs:
        flight = WORLD["flights"].get(leg)
        if flight is None:
            return {"error": f"unknown flight {leg}"}
        if flight.get("seats_available", 0) < party:
            return {"error": f"{leg} has {flight.get('seats_available', 0)} seat(s), "
                             f"party of {party} needs {party}"}
    for leg in legs:
        WORLD["flights"][leg]["seats_available"] -= party
    REBOOKINGS[passenger_id] = {"legs": legs, "party_size": party, "reason": reason}
    return {"status": "confirmed", "passenger_id": passenger_id, "legs": legs,
            "seats_taken": party}


TOOL_FUNCTIONS = {
    "get_flight": get_flight,
    "list_affected_passengers": list_affected_passengers,
    "find_alternatives": find_alternatives,
    "get_entitlements": get_entitlements,
    "rebook_passenger": rebook_passenger,
}

TOOLS = [
    {
        "type": "function",
        "name": "get_flight",
        "description": "Status, route and seat availability for one flight number.",
        "parameters": {
            "type": "object",
            "properties": {"flight_number": {"type": "string"}},
            "required": ["flight_number"],
        },
    },
    {
        "type": "function",
        "name": "list_affected_passengers",
        "description": "Passengers booked on a disrupted flight, with tier, party "
                       "size, onward connections and any notes.",
        "parameters": {
            "type": "object",
            "properties": {"flight_number": {"type": "string"}},
            "required": ["flight_number"],
        },
    },
    {
        "type": "function",
        "name": "find_alternatives",
        "description": "Available direct and one-stop options between two airports.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "IATA code, e.g. LIS"},
                "destination": {"type": "string", "description": "IATA code"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "type": "function",
        "name": "get_entitlements",
        "description": "What a loyalty tier is entitled to during a disruption.",
        "parameters": {
            "type": "object",
            "properties": {"tier": {"type": "string",
                                    "enum": ["gold", "silver", "standard"]}},
            "required": ["tier"],
        },
    },
    {
        "type": "function",
        "name": "rebook_passenger",
        "description": "Commit a passenger to one or more flights. This changes seat "
                       "availability. Call it once per passenger, only after checking "
                       "seats and constraints.",
        "parameters": {
            "type": "object",
            "properties": {
                "passenger_id": {"type": "string"},
                "flight_numbers": {
                    "type": "string",
                    "description": "One flight number, or two comma-separated for a "
                                   "connection, e.g. 'AE688,AE702'",
                },
                "reason": {"type": "string",
                           "description": "One line justifying this choice"},
            },
            "required": ["passenger_id", "flight_numbers", "reason"],
        },
    },
]

GOAL = (
    "Flight AE414 has been cancelled. Rebook every affected passenger onto the best "
    "available option, then report what you did and anything a human needs to decide. "
    "Respect each passenger's constraints and their tier's rebooking priority, and "
    "check seats are actually available before you commit a rebooking."
)

INSTRUCTIONS = (
    "You are a disruption manager for an airline. You work by calling tools: read "
    "before you write, and never state a flight time, seat count or entitlement you "
    "have not retrieved. Rebook the highest-priority passengers first. If a passenger "
    "cannot be accommodated within their constraints, leave them unbooked and say why "
    "— do not invent a flight, and do not put someone on an option that misses their "
    "stated deadline or connection."
)

print(f"The agent loop  ·  {MODEL_ID} in {REGION}")
print(f"{len(TOOLS)} tools ({len(TOOLS) - 1} read, 1 write)  ·  "
      f"ceiling {MAX_ROUNDS} rounds  ·  store=True, deleted in step F\n")

print("=" * 78)
print("A. The tools, and the one that is different")
print("=" * 78)
for tool in TOOLS:
    kind = "WRITE" if tool["name"] == "rebook_passenger" else "read "
    print(f"   {kind}  {tool['name']}({', '.join(tool['parameters']['properties'])})")
print("\n   Four reads are safe to retry, idempotent, and cheap to get wrong. The")
print("   write changes seat availability, so the agent's own later reads see the")
print("   consequences of its earlier writes. That feedback is what makes this a")
print("   loop rather than a batch of independent questions — and it is also why a")
print("   write tool deserves a different level of scrutiny than a read.\n")

print("=" * 78)
print("B. The goal")
print("=" * 78)
print("→ request")
print(f"   model             {MODEL_ID}")
print(f"   tools             {len(TOOLS)}")
print("   tool_choice       auto — the agent decides what to call and when")
print("   max_output_tokens 1500")
print(f"   goal              {GOAL[:66]}…")
print("   why a goal        there is no script here. The order of operations, the")
print("                     number of steps and the priority calls are the model's")
print("                     to make, which is the difference between an agent and")
print("                     a tool call.\n")

print("=" * 78)
print("C. The loop")
print("=" * 78)

# The first request carries the goal. Every one after it carries only the new tool
# results and points at the round before with previous_response_id, so the transcript
# lives on the service rather than being resent. STORED holds what to delete afterwards.
turn_input: list | str = [{"role": "user", "content": GOAL}]
previous_id: str | None = None
STORED: list[str] = []
trace: list[tuple[int, str, str]] = []
rounds = 0
total_in = total_out = total_reasoning = 0
final_answer = ""

while rounds < MAX_ROUNDS:
    rounds += 1
    response = client.responses.create(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=turn_input,
        previous_response_id=previous_id,
        tools=TOOLS,
        max_output_tokens=1500,
        store=True,
    )
    STORED.append(response.id)
    previous_id = response.id
    usage = response.usage
    total_in += usage.input_tokens
    total_out += usage.output_tokens
    total_reasoning += usage.output_tokens_details.reasoning_tokens

    calls = [item for item in response.output if item.type == "function_call"]
    print(f"←  round {rounds}  {len(calls)} tool call(s)  "
          f"{usage.input_tokens:>6} in / {usage.output_tokens:>5} out")

    if not calls:
        final_answer = response.output_text.strip()
        break

    results = []
    for call in calls:
        arguments = json.loads(call.arguments)
        outcome = TOOL_FUNCTIONS[call.name](**arguments)
        shown = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        trace.append((rounds, call.name, shown))
        marker = "✎" if call.name == "rebook_passenger" else "·"
        print(f"     {marker} {call.name}({shown[:64]})")
        print(f"       → {json.dumps(outcome)[:88]}")
        results.append({"type": "function_call_output", "call_id": call.call_id,
                        "output": json.dumps(outcome)})
    # Only the results go up next round. The reasoning items and the earlier turns are
    # already on the service, referenced by previous_response_id.
    turn_input = results
else:
    print(f"\n   Hit the {MAX_ROUNDS}-round ceiling without finishing. That is the")
    print("   ceiling doing its job, and in production it is an alert, not a retry.")

if final_answer:
    print("\n←  final answer")
    for line in final_answer.splitlines():
        if line.strip():
            print(f"   {line.strip()[:92]}")

print("\n" + "=" * 78)
print("D. What it actually did")
print("=" * 78)
for round_number, name, arguments in trace:
    print(f"   round {round_number}  {name:26} {arguments[:52]}")

print(f"\n   {len(REBOOKINGS)} of "
      f"{len(WORLD['passengers'].get('AE414', []))} passengers rebooked:")
for passenger_id, booking in REBOOKINGS.items():
    print(f"     {passenger_id}  {'+'.join(booking['legs']):16} "
          f"party {booking['party_size']}  {booking['reason'][:44]}")

print("\n   seats remaining after the agent's writes:")
for number, flight in WORLD["flights"].items():
    if "seats_available" in flight:
        print(f"     {number}  {flight['seats_available']:>3}")

print(f"\n   {rounds} round(s)  ·  {total_in} input tokens  ·  {total_out} output "
      f"({total_reasoning} reasoning)  ·  {len(trace)} tool calls")
print(
    "\n   Input grows every round even though this loop resends nothing: the model\n"
    "   receives the whole transcript either way, and previous_response_id changes\n"
    "   who transmits it, not what is billed. That is the cost model of an agent —\n"
    "   not the number of tool calls but the transcript they accumulate, which is\n"
    "   why a stable instruction prefix is worth caching and why a round ceiling is\n"
    "   a cost control as much as a safety one."
)

print("\n" + "=" * 78)
print("E. Before you let a loop act unsupervised")
print("=" * 78)
print(
    "   Can every write be undone, and by what?      here: nothing undoes a rebooking\n"
    "   What happens at the ceiling?                 here: it stops and reports\n"
    "   Is a partial run safe to leave?              here: some passengers rebooked\n"
    "   Who reads the trace?                         print it, store it, or both\n"
    "   What is the blast radius of one bad call?     one passenger, one flight\n"
    "\n   Those five answers, not the model choice, are what decides whether a loop\n"
    "   like this runs with a human in front of it or behind it."
)
print("\n" + "=" * 78)
print("F. Clean up")
print("=" * 78)

# store=True is the Bedrock default and it is what previous_response_id needs, but a
# stored response is retained for 30 days. The loop kept every id, so it can delete
# them here.
removed = delete_stored_responses(client, *STORED)
print(f"   deleted {len(removed)} of {len(STORED)} stored response(s) — one per round.")
print("   The write tool's changes were in memory and go with the process.")

print("\nPer-token rates by model: https://aws.amazon.com/bedrock/pricing/")
