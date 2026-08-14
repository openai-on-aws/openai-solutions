"""The same rebooking agent, run by the OpenAI Agents SDK against Bedrock.

Recipe 01 wrote the loop by hand: call the model, read the tool calls, execute them,
send the results back, stop at a ceiling. This is the identical scenario — same five
tools, same data, same goal — with the SDK running the loop instead.

The Bedrock integration point is the client. Build an AsyncOpenAI with the Bedrock
provider, hand it to the model, and everything the provider does comes along: SigV4
from the AWS credential chain, the regional mantle endpoint, no token to mint.

One setting has to change for a workload on Bedrock, and it is about where your
prompts go rather than whether the agent works. See the README.

Run it from the cookbooks/ directory:

    uv sync --group agents
    uv run python 04-agents/02-openai-agents-sdk/python/openai_agents_sdk.py
"""

import asyncio
import json
import os
from pathlib import Path

from agents import (
    Agent,
    ModelSettings,
    OpenAIResponsesModel,
    Runner,
    function_tool,
    set_tracing_disabled,
)
from openai import AsyncOpenAI, OpenAI
from openai.providers import bedrock

from cookbook_utils import delete_stored_responses

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# The SDK's ceiling. Recipe 01 counted rounds in a while loop; here the runner raises
# MaxTurnsExceeded, which is the same decision expressed as a parameter.
MAX_TURNS = 8

DATA = Path(__file__).parent.parent / "data"
WORLD = json.loads((DATA / "disruption.json").read_text())
REBOOKINGS: dict[str, dict] = {}

# --- Keep the trace inside AWS ----------------------------------------------

# The SDK exports traces to OpenAI's platform by default, which is the right default
# for a first-party workload and the wrong one here. This agent's prompts and tool
# calls are Bedrock traffic; a workload that chose Bedrock for in-Region processing
# should not ship them to a third party as a side effect of importing a library.
# Export is gated only on an API key being present in the environment, so on a machine
# that also has OPENAI_API_KEY set it happens with no error and no prompt.
set_tracing_disabled(True)

print(f"The same agent, run by the Agents SDK  ·  {MODEL_ID} in {REGION}")
print("Tracing disabled — otherwise traces go to OpenAI, not to CloudWatch\n")

# --- The tools --------------------------------------------------------------

# Identical logic to recipe 01. What disappears is the hand-written JSON schema: the
# decorator derives it from the signature and the docstring, so the docstring is not
# decoration here — it is the tool description the model reads when deciding.

TOOL_TRACE: list[str] = []


@function_tool
def get_flight(flight_number: str) -> dict:
    """Status, route and seat availability for one flight."""
    TOOL_TRACE.append(f"get_flight({flight_number})")
    flight = WORLD["flights"].get(flight_number)
    if flight is None:
        return {"error": f"unknown flight {flight_number}"}
    return {"flight_number": flight_number, **flight}


@function_tool
def list_affected_passengers(flight_number: str) -> dict:
    """Everyone booked on a disrupted flight, with their constraints."""
    TOOL_TRACE.append(f"list_affected_passengers({flight_number})")
    return {"flight_number": flight_number,
            "passengers": WORLD["passengers"].get(flight_number, [])}


@function_tool
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


@function_tool
def get_entitlements(tier: str) -> dict:
    """What a loyalty tier is owed during a disruption."""
    TOOL_TRACE.append(f"get_entitlements({tier})")
    entitlement = WORLD["entitlements"].get(tier)
    if entitlement is None:
        return {"error": f"unknown tier {tier}"}
    return {"tier": tier, **entitlement}


@function_tool
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


def arguments(payload: str) -> str:
    """A tool call's arguments as `name='value'`, short enough for one line.

    They arrive as a JSON string, because that is what the model wrote.
    """
    values = json.loads(payload or "{}")
    return ", ".join(f"{key}={value!r}" for key, value in values.items())[:84]


def summarise_tool_output(output: object) -> str:
    """One line describing what a tool returned, for the live trace.

    A tool here can return a manifest of passengers or a list of connecting itineraries,
    and printing those raw would bury the shape of the loop in JSON. This keeps the
    trace scannable; the full values are in the tools' own return statements above.
    """
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return output[:70]
    if isinstance(output, dict):
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
    return str(output)[:70]


TOOLS = [get_flight, list_affected_passengers, find_alternatives, get_entitlements,
         rebook_passenger]

# --- The agent --------------------------------------------------------------

# Same goal and same instructions as recipe 01, so the comparison is about the
# framework and not about the prompt.

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

agent = Agent(
    name="Disruption manager",
    instructions=INSTRUCTIONS,
    model=OpenAIResponsesModel(
        model=MODEL_ID,
        openai_client=AsyncOpenAI(provider=bedrock(region=REGION), max_retries=3),
    ),
    # store=True is the Bedrock default, and ModelSettings is where the SDK lets you say
    # so. Every model call is then retained for 30 days, which is why this script
    # collects the ids and deletes them at the end.
    model_settings=ModelSettings(store=True),
    tools=TOOLS,
)


async def main() -> None:
    print("→ request")
    print(f"   model             {MODEL_ID}")
    print(f"   tools             {len(TOOLS)} ({len(TOOLS) - 1} read, 1 write)")
    print(f"   max_turns         {MAX_TURNS}         (the runner raises rather than "
          "looping on)")
    print("   store             True      (the Bedrock default; deleted at the end)")
    print("   continuation      server-managed, via auto_previous_response_id")
    print("   streamed          run_streamed, so the work is visible as it happens")
    print(f"   goal              {GOAL[:66]}…\n")

    # auto_previous_response_id is what makes store=True mean something here: the runner
    # chains each turn to the previous response id instead of replaying the transcript.
    # Without it, store=True only retains data — the request is identical either way.
    #
    # run_streamed returns immediately and the work happens as you consume
    # stream_events(). Two families of event arrive, and the difference is the useful
    # part: raw_response_event carries the Responses API events verbatim, while
    # run_item_stream_event is the SDK's own semantic layer — it has already decided
    # that a tool was called and what it returned, so you do not reassemble anything.
    result = Runner.run_streamed(
        agent, GOAL, max_turns=MAX_TURNS, auto_previous_response_id=True
    )

    print("← the agent works")
    tool_names: dict[str, str] = {}
    answering = False

    async for event in result.stream_events():
        if event.type == "run_item_stream_event":
            if event.name == "tool_called":
                call = event.item.raw_item
                # Remember the name so the result can say which call it answers.
                tool_names[call.call_id] = call.name
                print(f"   → {call.name}({arguments(call.arguments)})")
            if event.name == "tool_output":
                name = tool_names.get(event.item.raw_item["call_id"], "tool")
                print(f"   ← {name}: {summarise_tool_output(event.item.output)}")

        if event.type == "raw_response_event":
            if event.data.type == "response.output_text.delta":
                if not answering:
                    print("\n   ", end="")
                    answering = True
                print(event.data.delta, end="", flush=True)
    print()

    # --- What the loop actually did ----------------------------------------

    print("\nThe loop, as the SDK ran it")
    print(f"   model calls   {len(result.raw_responses)} of {MAX_TURNS} allowed")
    print(f"   tool calls    {len(TOOL_TRACE)}")
    for index, call in enumerate(TOOL_TRACE, start=1):
        print(f"     {index:>2}. {call}")

    print(f"\n   rebooked      {len(REBOOKINGS)} passenger(s)")
    for passenger_id, booking in REBOOKINGS.items():
        print(f"     {passenger_id}  {', '.join(booking['legs'])}  "
              f"party of {booking['party_size']}")

    input_tokens = sum(r.usage.input_tokens for r in result.raw_responses)
    output_tokens = sum(r.usage.output_tokens for r in result.raw_responses)
    print(f"\n   {input_tokens} input / {output_tokens} output tokens across "
          f"{len(result.raw_responses)} calls")
    print("   Input grows every round: each call resends the instructions, the five")
    print("   tool definitions and the transcript so far.")

    # --- Carrying the run forward ------------------------------------------

    # Pick one continuation strategy and stay with it: OpenAI's guidance is that mixing
    # local replay with server-managed state can duplicate context. This run is
    # server-managed, so the follow-up sends only the new question and points at the
    # last response id — not result.to_input_list(), which would be the other strategy.

    print("\nAsking a follow-up, still server-managed")
    print(f"   previous_response_id  {result.last_response_id[:28]}…")
    print("   input                 only the new question, no transcript")

    follow_up = await Runner.run(
        agent,
        "Which passengers could not be rebooked, and what does a human need to decide?",
        max_turns=2,
        previous_response_id=result.last_response_id,
    )
    print("← response")
    for line in follow_up.final_output.strip().split("\n"):
        print(f"   {line}")
    print(f"\n   {follow_up.raw_responses[-1].usage.input_tokens} input tokens — the "
          "entire first run is the context for this question")

    # --- Clean up ----------------------------------------------------------

    # Each model call produced a stored response, and raw_responses carries their ids.
    # A sync client is fine for the delete: it is not part of the agent loop.

    print("\nCleaning up")
    stored = [r.response_id for r in result.raw_responses + follow_up.raw_responses
              if r.response_id]
    removed = delete_stored_responses(
        OpenAI(provider=bedrock(region=REGION)), *stored
    )
    print(f"   deleted {len(removed)} of {len(stored)} stored response(s)")
    print("   Nothing else to remove: the write tool mutated an in-memory copy.")


asyncio.run(main())
