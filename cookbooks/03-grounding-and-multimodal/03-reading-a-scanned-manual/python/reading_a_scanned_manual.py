"""Reading a scanned manual and a nameplate photo, then deciding from both.

A field service engineer stands in front of a press. The machine's identity is on a
stainless nameplate they can photograph, and the torque specification is in a service
manual that was scanned in 2019. Neither is text you can query, and the answer they need
depends on both plus the plant's own inspection record.

This script sends the photo, then the manual, then all three sources together with a
tool the model can call, and ends on what a page of document costs.

Run it from the cookbooks/ directory:

    uv run python \\
      03-grounding-and-multimodal/03-reading-a-scanned-manual/python/reading_a_scanned_manual.py

See README.md for the narrative.
"""

import base64
import json
import os
from pathlib import Path

from openai import OpenAI
from openai.providers import bedrock
from pydantic import BaseModel

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Terra reads these scans reliably. Luna is cheaper and worth trying on a clean
# document; a skewed, speckled scan is where the stronger model earns its price.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

DATA = Path(__file__).parent.parent / "data"
NAMEPLATE = DATA / "nameplate.jpg"
MANUAL = DATA / "service-manual.pdf"
HISTORY = json.loads((DATA / "service_history.json").read_text())

# store=False on every call. These are single-turn questions about a document, so there
# is nothing to refer back to, and the inputs are a customer's maintenance records.
client = OpenAI(provider=bedrock(region=REGION), max_retries=3)


def as_data_url(path: Path, mime: str) -> str:
    """Inline a local file as a base64 data URL.

    The Files API is not reachable with SigV4 on this endpoint — a multipart upload is
    not a replayable request body, so the client refuses to sign it — and inlining is
    the documented alternative. It also keeps the recipe to the standard library.
    """
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


nameplate_url = as_data_url(NAMEPLATE, "image/jpeg")
manual_url = as_data_url(MANUAL, "application/pdf")

print(f"Model: {MODEL_ID}    Region: {REGION}    store=False on every call")
print(f"Nameplate: {NAMEPLATE.name}, {NAMEPLATE.stat().st_size // 1024} KB   "
      f"Manual: {MANUAL.name}, {MANUAL.stat().st_size // 1024} KB")
print("Both are synthetic: AnyCompany Industries is invented, and the documents were")
print("generated rather than scanned from anything real.")

# --- A. The nameplate photo -------------------------------------------------

# The photo is deliberately imperfect — taken at an angle, lit by a phone flash, and
# with the asset tag worn away by hands. The schema below allows null for exactly that
# reason: a field that cannot be read must come back empty rather than plausible.

# A Pydantic model rather than a hand-written JSON schema, because here the schema is
# not the lesson — the photograph is. responses.parse() derives the strict schema from
# this class, sends it, and gives the answer back as an instance of it. pydantic arrives
# with the openai package, so this costs no extra dependency.
#
# `str | None` is how a field says "this may be unreadable". Note what strict mode does
# with it: the field is still *required*, it is simply allowed to be null. There is no
# way to say "may be absent", which is the right constraint for an extraction pipeline —
# every field is accounted for on every record.


class Nameplate(BaseModel):
    manufacturer: str
    model: str
    serial_number: str
    max_pressure: str
    hydraulic_oil: str
    manufacture_date: str
    asset_tag: str | None
    unreadable_fields: list[str]

print("\nA. Read the nameplate photo")
print("→ request")
print(f"   model              {MODEL_ID}")
print("   input_image        the phone photo, inlined as a base64 data URL")
print("   text_format        the Nameplate model, whose asset_tag is str | None")
print("                      because that field is physically worn away on the plate")

plate = client.responses.parse(
    model=MODEL_ID,
    store=False,
    max_output_tokens=600,
    instructions=(
        "You read equipment nameplates from photographs. Transcribe only what is "
        "legible. If a field is damaged, obscured or partially worn, return null for "
        "it and name it in unreadable_fields. Never complete a value from context."
    ),
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": "Transcribe this machine nameplate."},
        {"type": "input_image", "image_url": nameplate_url},
    ]}],
    text_format=Nameplate,
)

# A Nameplate instance, not a dict: asset_tag is None rather than the string "null",
# and unreadable_fields is a list you can iterate without checking.
nameplate = plate.output_parsed

print("← response")
for field, value in nameplate.model_dump().items():
    print(f"   {field:<18} {value!r}")
print(f"   {plate.usage.input_tokens} input / {plate.usage.output_tokens} "
      "output tokens")
print("   The photo is most of that input. A 1080x720 JPEG is priced as image tokens,")
print("   so an intake pipeline's cost scales with how large the photographs are.")

# --- B. The scanned manual --------------------------------------------------

# Four scanned pages, skewed and speckled, sent as one input_file block. The question
# needs a value from a table on page 4-1 and a sequence from a figure on page 5-1, so
# the answer is only correct if the whole document is legible to the model.

print("\nB. Read the scanned manual")
print("→ request")
print("   input_file         the 4-page scan, inlined the same way")
print("   the question       needs a table on one page and a figure on another, so")
print("                      a partial read shows up as a wrong answer")

manual_question = (
    "For the main frame bolt: give the torque, the tolerance, and what the manual "
    "says to do if a reading is below the tolerance band. Then give the tightening "
    "order from figure 5-1. Cite the page number for each answer."
)
manual = client.responses.create(
    model=MODEL_ID,
    store=False,
    max_output_tokens=700,
    instructions=(
        "You answer maintenance questions strictly from the supplied document. Quote "
        "the value as printed and give the page number. If the document does not "
        "contain an answer, say so rather than supplying general engineering practice."
    ),
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": manual_question},
        {"type": "input_file", "filename": MANUAL.name, "file_data": manual_url},
    ]}],
)

print("← response")
for line in manual.output_text.strip().split("\n"):
    print(f"   {line}")
print(f"\n   {manual.usage.input_tokens} input / {manual.usage.output_tokens} "
      "output tokens for four pages")

# --- C. Photo, document and the plant's records, in one decision -------------

# This is the part that needs all three. The nameplate gives the serial, the tool gives
# the readings recorded against that serial, and the manual gives the tolerance and the
# rule. Any two of the three produce a confident wrong answer.


def get_service_history(serial_number: str) -> dict:
    """The plant's maintenance record for one machine, by serial."""
    record = HISTORY.get(serial_number)
    if record is None:
        return {"error": f"no machine with serial {serial_number}"}
    return {"serial_number": serial_number, **record}


TOOLS = [{
    "type": "function",
    "name": "get_service_history",
    "description": "Inspection readings recorded against a machine serial number.",
    "parameters": {
        "type": "object",
        "properties": {"serial_number": {"type": "string"}},
        "required": ["serial_number"],
        "additionalProperties": False,
    },
}]

print("\nC. Decide from the photo, the document and the maintenance record")
print("→ request")
print(f"   input_image        the nameplate again, whose serial reads "
      f"{nameplate.serial_number}")
print("   input_file         the manual, for the tolerance and the rule")
print("   tools              get_service_history, which it must call with that serial")

conversation: list = [{"role": "user", "content": [
    {"type": "input_text", "text": (
        "This is the machine in front of me and its service manual. Look up its "
        "maintenance history, then tell me whether the main frame bolt needs "
        "replacing or re-torquing, and why. Name the readings you relied on."
    )},
    {"type": "input_image", "image_url": nameplate_url},
    {"type": "input_file", "filename": MANUAL.name, "file_data": manual_url},
]}]

decision_input_tokens = 0
model_calls = 0
for _ in range(4):
    response = client.responses.create(
        model=MODEL_ID,
        store=False,
        max_output_tokens=1200,
        instructions=(
            "You are a maintenance engineer's assistant. Read the serial number from "
            "the photograph, retrieve that machine's history, and apply the manual's "
            "own rule. Do not state a torque value or an interval you have not read "
            "from the document."
        ),
        input=conversation,
        tools=TOOLS,
    )
    decision_input_tokens += response.usage.input_tokens
    model_calls += 1

    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        break

    conversation += response.output
    for call in calls:
        arguments = json.loads(call.arguments)
        print(f"   ← tool call  {call.name}({arguments['serial_number']})")
        result = get_service_history(**arguments)
        readings = [i for i in result.get("inspections", []) if i["reading_nm"]]
        print(f"     returned {len(result.get('inspections', []))} inspections, "
              f"readings {[i['reading_nm'] for i in readings]} Nm")
        conversation.append({"type": "function_call_output", "call_id": call.call_id,
                             "output": json.dumps(result)})

print("← response")
for line in response.output_text.strip().split("\n"):
    print(f"   {line}")
print(f"\n   {decision_input_tokens} input tokens across {model_calls} model calls")
print("   The photo and the manual are resent on every call in the loop, which is")
print("   what makes a media-carrying tool loop expensive rather than the tool.")

# --- D. What a document costs, and how to keep the bill down ----------------

# The manual cannot be cached, so the lever is how many questions you ask per request.
# Four questions in one request against the same four pages, measured.

print("\nD. Ask everything at once, because the document cannot be cached")
print("→ request")
print("   one call           four questions about the same four pages")

batch = client.responses.create(
    model=MODEL_ID,
    store=False,
    max_output_tokens=900,
    instructions="Answer strictly from the document. Number your answers.",
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": (
            "1. What is the revision letter on the cover?\n"
            "2. What is the seal kit replacement interval?\n"
            "3. What size is the guard bracket bolt?\n"
            "4. What must be done before loosening any fastener in section 4?"
        )},
        {"type": "input_file", "filename": MANUAL.name, "file_data": manual_url},
    ]}],
)

print("← response")
for line in batch.output_text.strip().split("\n"):
    print(f"   {line}")

one_request = batch.usage.input_tokens
print(f"\n   {one_request} input tokens for four answers.")
print("   The same four questions asked separately would resend the document four")
print(f"   times: about {one_request * 4:,} input tokens for the same information.")
print()
print("   Prompt caching does not help here. A request carrying an image or a")
print("   document block writes nothing to the cache and reads nothing from it, so")
print("   batching the questions is the lever that exists. The README records the")
print("   measurement behind that.")
