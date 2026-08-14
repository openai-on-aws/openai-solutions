"""The same rebooking agent again, this time in Strands.

Third pass over one scenario. Recipe 01 wrote the loop by hand, recipe 02 handed it to
the OpenAI Agents SDK, and this one uses Strands — the AWS-native agent SDK, and the
one that composes most naturally with AgentCore deployment.

The interesting difference is not ergonomics, it is authentication. The Agents SDK
reaches mantle through an OpenAI client that signs with SigV4. Strands has its own
first-class mantle config, and it mints a short-term bearer token to get there. The
script prints which path it took.

Run it from the cookbooks/ directory:

    uv sync --group agents
    uv run python 04-agents/03-strands-agents-sdk/python/strands_agents_sdk.py
"""

import asyncio
import json
import os
from pathlib import Path

from strands import Agent, tool
from strands.models.openai_responses import OpenAIResponsesModel

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

DATA = Path(__file__).parent.parent / "data"
WORLD = json.loads((DATA / "disruption.json").read_text())
REBOOKINGS: dict[str, dict] = {}
TOOL_TRACE: list[str] = []

# --- The tools --------------------------------------------------------------

# Identical logic to the previous two recipes. Strands' @tool derives the schema from
# the signature and the docstring, exactly as the Agents SDK does — the decorator name
# is the only difference at this level.


@tool
def get_flight(flight_number: str) -> dict:
    """Status, route and seat availability for one flight."""
    TOOL_TRACE.append(f"get_flight({flight_number})")
    flight = WORLD["flights"].get(flight_number)
    if flight is None:
        return {"error": f"unknown flight {flight_number}"}
    return {"flight_number": flight_number, **flight}


@tool
def list_affected_passengers(flight_number: str) -> dict:
    """Everyone booked on a disrupted flight, with their constraints."""
    TOOL_TRACE.append(f"list_affected_passengers({flight_number})")
    return {"flight_number": flight_number,
            "passengers": WORLD["passengers"].get(flight_number, [])}


@tool
def find_alternatives(origin: str, destination: str) -> dict:
    """Flights that could get someone from origin to destination, direct or not."""
    TOOL_TRACE.append(f"find_alternatives({origin}-{destination})")
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


@tool
def get_entitlements(tier: str) -> dict:
    """What a loyalty tier is owed during a disruption."""
    TOOL_TRACE.append(f"get_entitlements({tier})")
    entitlement = WORLD["entitlements"].get(tier)
    if entitlement is None:
        return {"error": f"unknown tier {tier}"}
    return {"tier": tier, **entitlement}


@tool
def rebook_passenger(passenger_id: str, flight_numbers: str, reason: str) -> dict:
    """THE WRITE. Commit a passenger to one or more flights.

    Seat availability is decremented here, so the agent's own later calls see the
    consequences of its earlier ones — which is what makes this a loop rather than a
    batch of independent questions.
    """
    TOOL_TRACE.append(f"rebook_passenger({passenger_id} -> {flight_numbers})")
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


def arguments(payload: dict) -> str:
    """A tool call's arguments as `name='value'`, short enough for one line."""
    return ", ".join(f"{key}={value!r}" for key, value in payload.items())[:84]


def returned(tool_result: dict) -> str:
    """The text a tool returned, out of the content blocks Strands wraps it in."""
    return "".join(part.get("text", "") for part in tool_result.get("content", []))


def summarise_tool_output(text: str) -> str:
    """One line describing what a tool returned, for the live trace.

    Strands hands back the tool result as the text it was serialised to, so this parses
    it rather than receiving the object the function returned — the one place the two
    framework recipes genuinely differ in their tracing code.
    """
    try:
        output = json.loads(text)
    except json.JSONDecodeError:
        return text[:70]
    if not isinstance(output, dict):
        return str(output)[:70]
    if "error" in output:
        return f"error: {output['error']}"
    if "passengers" in output:
        return f"{len(output['passengers'])} passenger(s)"
    if "direct" in output or "connecting" in output:
        return (f"{len(output.get('direct', []))} direct, "
                f"{len(output.get('connecting', []))} connecting")
    if output.get("status") == "confirmed":
        return f"confirmed on {', '.join(output.get('legs', []))}"
    return ", ".join(f"{k}={v}" for k, v in list(output.items())[:3])


TOOLS = [get_flight, list_affected_passengers, find_alternatives, get_entitlements,
         rebook_passenger]

# --- The model: mantle is a first-class config ------------------------------

# bedrock_mantle_config is what makes this work, and the class matters: Strands'
# BedrockModel is a bedrock-runtime Converse client and cannot reach mantle at all.
# OpenAIResponsesModel lives in strands.models.openai_responses — it is not re-exported
# from strands.models, which is where BedrockModel and OpenAIModel live.
#
# From this config Strands derives the base URL and the credentials itself, and it
# refuses api_key or base_url in client_args rather than letting them conflict.

# Nothing is retained here, and it is the one place these three agent recipes diverge:
# the other two store their turns and delete them afterwards.
#
# Note what is NOT in params below. This provider does not take `store` as a parameter —
# it derives it from `stateful`, which defaults off, and assigns it after params are
# unpacked. So a `"store": True` written here would be silently overridden, and the way
# to store with Strands is `stateful=True`.
#
# That flag is a bigger decision than retention, which is why this recipe leaves it off.
# It hands the transcript to the service: `agent.messages` is emptied after every turn,
# and Strands refuses a conversation_manager or context_manager alongside it, so the
# sliding-window trimming an agent loop eventually needs is unavailable. It also does
# not reduce what you are billed — the model still receives the context either way.
model = OpenAIResponsesModel(
    bedrock_mantle_config={"region": REGION},
    model_id=MODEL_ID,
    params={"max_output_tokens": 4096},
)

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

# callback_handler=None turns off Strands' own printing to stdout. The handler is a
# reasonable default for a terminal, but it interleaves its own account of the run with
# ours; this recipe consumes stream_async() instead and prints one trace.
agent = Agent(model=model, tools=TOOLS, system_prompt=INSTRUCTIONS,
              callback_handler=None)

print(f"The same agent, in Strands  ·  {MODEL_ID} in {REGION}")
print("Auth: Strands mints a short-term bearer token from your IAM credentials,")
print("      rather than signing each request with SigV4 as the OpenAI client does.\n")

print("→ request")
print(f"   model             {MODEL_ID}")
print("   streamed          stream_async, so the work is visible as it happens")
print(f"   tools             {len(TOOLS)} ({len(TOOLS) - 1} read, 1 write)")
print("   stateful          False     the transcript stays in this process, and")
print("                               nothing is retained server-side")
print(f"   goal              {GOAL[:66]}…\n")

async def stream(prompt: str):
    """Print the agent's tool work as it happens, then return the final result.

    Strands yields plain dicts, and this reads three keys of the set it documents:
    `message` for whole messages as they join the transcript, `data` for a chunk of
    answer text, and `result` for the finished AgentResult.

    One key does the heavy lifting. A `message` carries the finished tool calls and,
    a moment later, their results — so both halves of the loop come from the same place
    and the arguments are complete when you read them.
    """
    tool_names: dict[str, str] = {}
    answering = False
    result = None

    async for event in agent.stream_async(prompt):
        if "message" in event:
            for block in event["message"].get("content", []):
                if "toolUse" in block:
                    call = block["toolUse"]
                    # Remember the name so the result can say which call it answers.
                    tool_names[call["toolUseId"]] = call["name"]
                    print(f"   → {call['name']}({arguments(call['input'])})")
                if "toolResult" in block:
                    outcome = block["toolResult"]
                    name = tool_names.get(outcome["toolUseId"], "tool")
                    print(f"   ← {name}: {summarise_tool_output(returned(outcome))}")

        if "data" in event:
            if not answering:
                print("\n   ", end="")
                answering = True
            print(event["data"], end="", flush=True)

        if event.get("force_stop"):
            # The loop gave up rather than finished; this is the only account of why.
            print(f"\n   ! stopped: {event.get('force_stop_reason', 'unknown')}")

        if "result" in event:
            result = event["result"]

    print()
    return result


print("← the agent works")
result = asyncio.run(stream(GOAL))

# --- What the loop did ------------------------------------------------------

print("\nThe loop, as Strands ran it")
print(f"   cycles        {result.metrics.cycle_count}")
print(f"   tool calls    {len(TOOL_TRACE)}")
for index, call in enumerate(TOOL_TRACE, start=1):
    print(f"     {index:>2}. {call}")

print(f"\n   rebooked      {len(REBOOKINGS)} passenger(s)")
for passenger_id, booking in REBOOKINGS.items():
    print(f"     {passenger_id}  {', '.join(booking['legs'])}  "
          f"party of {booking['party_size']}")

usage = result.metrics.accumulated_usage
print(f"\n   {usage['inputTokens']} input / {usage['outputTokens']} output tokens")
print("   Input grows every cycle: the instructions, the five tool definitions and")
print("   the transcript so far are resent each time.")

# --- Where the conversation lives -------------------------------------------

# Strands keeps the transcript on the agent object, so a follow-up is another call to
# the same agent. Nothing is stored server-side, which is why store=False costs nothing
# here: the agent is already the record.

print("\nAsking a follow-up")
print(f"   agent.messages holds {len(agent.messages)} items in this process")

follow_up = asyncio.run(stream(
    "Which passengers could not be rebooked, and what does a human need to decide?"
))
total = follow_up.metrics.accumulated_usage
print(f"\n   {total['inputTokens']} input tokens accumulated over both questions")
