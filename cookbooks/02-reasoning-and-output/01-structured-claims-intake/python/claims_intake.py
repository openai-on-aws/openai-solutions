"""Turn messy first-notice-of-loss notes into records a claims system can accept.

Four phases, each one a different guarantee about the output:

  A. json_object   valid JSON, but the model chooses the keys
  B. json_schema   your shape, enforced, with nullable fields for what may be absent
  C. parse()       the schema comes from your Python types and you get an instance back
  D. batch         every note through the same contract, with what it cost

Watch what phase D leaves empty. Two notes are deliberately thin, and what the model
does with a field it has no evidence for is the part of schema design that decides
whether a pipeline is trustworthy. See README.md for the full narrative.
"""

import json
import os
from pathlib import Path
from typing import Literal

from openai import OpenAI
from openai.providers import bedrock
from pydantic import BaseModel, Field

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Terra: extraction from messy text needs comprehension, not deliberation.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

DATA = Path(__file__).resolve().parent.parent / "data"

# The client. Three lines, no key, no token: the Bedrock provider signs with the
# AWS credential chain. max_retries covers the 429 you get from a tokens-per-minute
# quota rather than from anything you did wrong.
client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

note_lines = (DATA / "fnol_notes.jsonl").read_text().splitlines()
notes = [json.loads(line) for line in note_lines]

INSTRUCTIONS = (
    "You are an intake assistant at a general insurer. Extract a structured claim "
    "record from the adjuster's free-text note. Use only what the note supports: if "
    "the note does not establish a value, leave it null and name it in "
    "missing_information. Amounts are in pence (multiply currency figures by 100)."
)

print(f"Claims intake  ·  {MODEL_ID} in {REGION}")
print(f"{len(notes)} first-notice-of-loss notes, all synthetic")
print("store=False on every call, so AWS retains neither request nor response\n")

# --- A. json_object: valid JSON, and that is the whole guarantee -------------

first = notes[0]

print("=" * 78)
print("A. text.format = json_object")
print("=" * 78)
print("→ request")
print("   text.format      {'type': 'json_object'}   valid JSON, shape")
print("                    unconstrained")
print(f"   input            {first['note_id']}: {first['text'][:58]}…")
print("   why this shape   the cheapest way to get parseable output, and the")
print("                    reason it is not enough for a pipeline")

loose = client.responses.create(
    model=MODEL_ID,
    instructions="Extract the claim from this note as a JSON object.",
    input=first["text"],
    text={"format": {"type": "json_object"}},
    max_output_tokens=800,
    store=False,
)
parsed_loose = json.loads(loose.output_text)

print("← response")
print(f"   {len(parsed_loose)} keys, named by the model:")
print(f"   {', '.join(parsed_loose)}")
print(f"   {loose.usage.input_tokens} in / {loose.usage.output_tokens} out")
print("   The JSON parses. Nothing promises these key names on the next note,")
print("   so a consumer has to defend against every shape the model might pick.\n")

# --- B. strict json_schema: your shape, enforced -----------------------------

# Nullable on everything the note may not establish. This is the design decision the
# recipe is about: a non-nullable field cannot say "the note does not say".
CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["auto", "property", "liability"]},
        "policy_number": {"type": ["string", "null"]},
        "incident_date": {
            "type": ["string", "null"],
            "description": "ISO 8601 date, or null if the note does not fix one",
        },
        "estimated_amount_pence": {"type": ["integer", "null"]},
        "injuries_reported": {
            "type": ["boolean", "null"],
            "description": "null when the note is silent on injuries",
        },
        "liability_disputed": {"type": ["boolean", "null"]},
        "missing_information": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "claim_type", "policy_number", "incident_date", "estimated_amount_pence",
        "injuries_reported", "liability_disputed", "missing_information",
    ],
    "additionalProperties": False,
}

print("=" * 78)
print("B. text.format = json_schema, strict")
print("=" * 78)
print("→ request")
print("   text.format      json_schema, strict=True, additionalProperties=False")
print(f"   schema           {len(CLAIM_SCHEMA['properties'])} properties, "
      f"6 of them nullable")
print(f"   input            {first['note_id']} (the same note as phase A)")
print("   why this shape   the consumer defines the contract, not the model")

strict = client.responses.create(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=first["text"],
    text={"format": {"type": "json_schema", "name": "claim_record",
                     "strict": True, "schema": CLAIM_SCHEMA}},
    max_output_tokens=800,
    store=False,
)

print("← response")
for key, value in json.loads(strict.output_text).items():
    print(f"   {key:24} {value!r}")
print(f"   echoed back on the response: text.format.type = {strict.text.format.type}, "
      f"strict = {strict.text.format.strict}")
print(f"   {strict.usage.input_tokens} in / {strict.usage.output_tokens} out")
print("   '2,400 to put right' became 240000 pence: the unit conversion is in the")
print("   instructions, and the integer type is what makes it safe to rely on.\n")

# --- C. responses.parse(): the schema is your type ---------------------------


class ClaimRecord(BaseModel):
    """The same contract as CLAIM_SCHEMA, written once as Python.

    `| None` is what lets the model decline to answer a field. Every optional field
    here is optional because a real note might not establish it.
    """

    claim_type: Literal["auto", "property", "liability"]
    policy_number: str | None
    incident_date: str | None = Field(description="ISO 8601, or null if not fixed")
    estimated_amount_pence: int | None
    injuries_reported: bool | None = Field(description="null when the note is silent")
    liability_disputed: bool | None
    missing_information: list[str]


print("=" * 78)
print("C. client.responses.parse(text_format=ClaimRecord)")
print("=" * 78)
print("→ request")
print("   text_format      ClaimRecord (a pydantic BaseModel)")
print("   note             the SDK derives the JSON schema from the model and")
print("                    validates the reply against it")
print(f"   input            {first['note_id']} (the same note again)")

typed = client.responses.parse(
    model=MODEL_ID,
    instructions=INSTRUCTIONS,
    input=first["text"],
    text_format=ClaimRecord,
    max_output_tokens=800,
    store=False,
)
record = typed.output_parsed

print("← response")
print(f"   type(response.output_parsed) = {type(record).__name__}")
print(f"   record.claim_type            = {record.claim_type!r}   "
      f"(a Literal, so this is one of three known values)")
print(f"   record.estimated_amount_pence = {record.estimated_amount_pence!r}   "
      f"(an int, for arithmetic)")
print(f"   {typed.usage.input_tokens} in / {typed.usage.output_tokens} out")
print("   Same contract as phase B with no schema to hand-maintain, and the reply")
print("   arrives as an object rather than a string to json.loads.\n")

# --- D. every note through the same contract --------------------------------

print("=" * 78)
print("D. All five notes, one contract")
print("=" * 78)
print("→ request  (identical for every note except the input)")
print(f"   model            {MODEL_ID}")
print("   text_format      ClaimRecord")
print("   max_output_tokens 800")
print("   why this shape   the same schema over deliberately uneven inputs is how")
print("                    you find out what your schema does under pressure\n")

total_in = total_out = 0
for note in notes:
    result = client.responses.parse(
        model=MODEL_ID,
        instructions=INSTRUCTIONS,
        input=note["text"],
        text_format=ClaimRecord,
        max_output_tokens=800,
        store=False,
    )
    claim = result.output_parsed
    total_in += result.usage.input_tokens
    total_out += result.usage.output_tokens

    amount = ("—" if claim.estimated_amount_pence is None
              else f"{claim.estimated_amount_pence / 100:,.2f}")
    print(f"← {note['note_id']}  {claim.claim_type:9} "
          f"policy {claim.policy_number or '—':11} "
          f"date {claim.incident_date or '—':11} amount {amount:>10}")
    print(f"   injuries_reported={claim.injuries_reported!r:6} "
          f"liability_disputed={claim.liability_disputed!r}")
    if claim.missing_information:
        print(f"   the model says it could not establish: "
              f"{'; '.join(claim.missing_information[:3])}")

print(f"\n   {len(notes)} notes  ·  {total_in} in  ·  {total_out} out")

# --- E. What to take away ---------------------------------------------------

print("\n" + "=" * 78)
print("What the output shows")
print("=" * 78)
print(
    "Every record above is schema-valid, and that is not the same as correct.\n"
    "FNOL-2216 is three sentences of nothing, and it still produced a well-formed\n"
    "record — because a schema constrains shape, never truth. The two fields that\n"
    "carry the weight are the nullable ones and missing_information: they are how\n"
    "the model tells you it had no evidence, and they only work if you left room\n"
    "for that answer in the type.\n"
    "\n"
    "So the routing decision downstream is not 'did it parse'. It is 'how many\n"
    "fields came back null, and which ones'."
)
print("\nPer-token rates by model: https://aws.amazon.com/bedrock/pricing/")
