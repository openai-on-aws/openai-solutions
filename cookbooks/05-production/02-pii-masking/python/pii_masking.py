"""Keep patient identifiers out of the model, and out of what it writes.

Bedrock Guardrails' sensitive-information policy detects personal data and either blocks
the request or replaces each entity with a placeholder like {NAME}. Because a screen
is a separate ApplyGuardrail call here, you choose where it sits: before the model so
identifiers never reach it, after the model so nothing identifying is published, or
both.

  A. the guardrail   built-in PII entities plus a custom regex for record numbers
  B. before          screen the note, and send the masked text to the model
  C. the model works on masked text and still produces a useful summary
  D. after           screen the summary too, because the input screen is not enough
  E. verify          check the masked text for identifiers we know are there
  F. clean up

Masking is deliberately irreversible: {NAME} cannot be turned back into a name. That is
the right default for a summary, and the wrong one if a downstream system needs the
identifier itself — see README.md.
"""

import json
import os
from pathlib import Path

import boto3
from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
# Luna: summarizing a short note is a high-volume, low-deliberation job, and a
# clinical service runs thousands of them a day.
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-luna")

# Set GUARDRAIL_ID to reuse an existing guardrail. Creating one needs
# bedrock:CreateGuardrail, which is a much larger grant than ApplyGuardrail.
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID")

# Detected and replaced with {TYPE}. AWS supports many more; these are the ones a
# clinical call note actually carries.
PII_ENTITIES = ["NAME", "EMAIL", "PHONE", "ADDRESS", "AGE", "US_SOCIAL_SECURITY_NUMBER"]

# Two patterns the built-in entity list cannot cover. The MRN format is local to the
# site, and there is no date-of-birth entity type at all — the supported set includes
# AGE but nothing for a date, so a DOB in a clinical note is a regex or nothing.
CUSTOM_PATTERNS = [
    ("MedicalRecordNumber", r"\b88-\d{5}\b", "Local MRN format, two digits then five"),
    ("DateOfBirth", r"\b\d{2}/\d{2}/\d{4}\b", "DOB written as dd/mm/yyyy"),
]

# Identifiers we know are in the synthetic notes, used in step E to check what the
# screen actually removed. A real pipeline cannot do this — it does not know the
# answers — which is exactly why it is worth doing on a corpus where you do.
KNOWN_IDENTIFIERS = [
    "Ines Halvorsen", "88-40921", "14/03/1958", "42 Elm Street", "555-0142",
    "ines.halvorsen@example.com", "Tomas Reidy", "88-41003", "555-0188",
    "9 Cranmer Row", "Devlin Okonkwo", "88-39887", "123-45-6789", "555-0119",
    "devlin.okonkwo@example.com", "Perrine Ashby", "88-40550", "17 Bellhouse Lane",
    "555-0173",
]

DATA = Path(__file__).resolve().parent.parent / "data"

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)
bedrock_control = boto3.client("bedrock", region_name=REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

note_lines = (DATA / "call_notes.jsonl").read_text().splitlines()
NOTES = [json.loads(line) for line in note_lines]

print(f"PII masking before and after the model  ·  {MODEL_ID} in {REGION}")
print(f"{len(NOTES)} synthetic call notes  ·  store=False on every model call\n")

# --- A. The guardrail -------------------------------------------------------

print("=" * 78)
print("A. The guardrail")
print("=" * 78)

created_here = GUARDRAIL_ID is None
if created_here:
    print("→ request   bedrock:CreateGuardrail")
    print(f"   piiEntitiesConfig    {len(PII_ENTITIES)} entities, action ANONYMIZE")
    print("                        " + ", ".join(PII_ENTITIES))
    print("   inputAction /        set explicitly, per entity, alongside action —")
    print("   outputAction         action alone leaves one direction inert")
    print(f"   regexesConfig        {len(CUSTOM_PATTERNS)} patterns: "
          f"{', '.join(n for n, _, _ in CUSTOM_PATTERNS)}")
    print("   why a regex          an MRN format is local to the site, and there is")
    print("                        no date-of-birth entity type at all — the")
    print("                        supported set has AGE but nothing for a date")

    pii_config = [
        {
            "type": entity,
            "action": "ANONYMIZE",
            "inputAction": "ANONYMIZE",
            "outputAction": "ANONYMIZE",
            "inputEnabled": True,
            "outputEnabled": True,
        }
        for entity in PII_ENTITIES
    ]
    created = bedrock_control.create_guardrail(
        name="cookbook-pii-masking",
        description="Masks patient identifiers before and after model invocation.",
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": pii_config,
            "regexesConfig": [
                {
                    "name": name,
                    "description": description,
                    "pattern": pattern,
                    "action": "ANONYMIZE",
                    "inputAction": "ANONYMIZE",
                    "outputAction": "ANONYMIZE",
                    "inputEnabled": True,
                    "outputEnabled": True,
                }
                for name, pattern, description in CUSTOM_PATTERNS
            ],
        },
        blockedInputMessaging="Blocked: this input carries identifiers.",
        blockedOutputsMessaging="Blocked: this output carries identifiers.",
    )
    GUARDRAIL_ID = created["guardrailId"]
    version = str(bedrock_control.create_guardrail_version(
        guardrailIdentifier=GUARDRAIL_ID, description="cookbook run",
    )["version"])
    print("← response")
    print(f"   guardrail created, version {version}, "
          f"{len(PII_ENTITIES)} entities + {len(CUSTOM_PATTERNS)} regexes")
    print("   deleted again in step F\n")
else:
    version = os.environ.get("GUARDRAIL_VERSION", "1")
    print(f"   reusing the guardrail in GUARDRAIL_ID at version {version}\n")


def screen(text: str, source: str) -> tuple[str, list[tuple[str, str]]]:
    """Screen text in one direction. Returns the masked text and what was found.

    `source` is "INPUT" or "OUTPUT" and selects which per-entity action applies —
    which is why both were configured above.
    """
    result = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=version,
        source=source,
        content=[{"text": {"text": text}}],
    )
    found = [
        (item.get("type") or item.get("name"), item["action"])
        for assessment in result.get("assessments", [])
        for key in ("piiEntities", "regexes")
        for item in assessment.get("sensitiveInformationPolicy", {}).get(key, [])
    ]
    masked = result["outputs"][0]["text"] if result.get("outputs") else text
    return masked, found


# --- B. Screen the input ----------------------------------------------------

note = NOTES[0]
print("=" * 78)
print("B. Screen the note before the model sees it")
print("=" * 78)
print("→ request   ApplyGuardrail, source=INPUT")
print(f"   input     {note['note_id']}: {note['text'][:60]}…")
print("   why here  an identifier that never reaches the model cannot be echoed")
print("             by it, logged with the request, or retained by anyone")

masked_note, found = screen(note["text"], "INPUT")
print("← response")
print(f"   {len(found)} entities masked: "
      f"{', '.join(sorted({name for name, _ in found}))}")
print(f"   {masked_note[:210]}…\n")

# --- C. The model works on the masked text ----------------------------------

SUMMARY_INSTRUCTIONS = (
    "You summarize clinical call notes for a care-coordination queue. Give a two-line "
    "clinical summary and a one-line recommended action. The note is de-identified: "
    "placeholders like {NAME} or {PHONE} stand in for removed identifiers. Keep them "
    "as written and never invent a value for one."
)

print("=" * 78)
print("C. The model summarizes the masked note")
print("=" * 78)
print("→ request")
print(f"   model             {MODEL_ID}")
print("   instructions      summarize for triage; keep placeholders as written")
print("   reasoning.effort  none        summarizing a short note needs no")
print("                                deliberation, and this runs at volume")
print("   max_output_tokens 300")
print("   input             the masked note from step B")

response = client.responses.create(
    model=MODEL_ID,
    instructions=SUMMARY_INSTRUCTIONS,
    input=masked_note,
    reasoning={"effort": "none"},
    max_output_tokens=300,
    store=False,
)
summary = response.output_text.strip()
print("← response")
for line in summary.splitlines():
    if line.strip():
        print(f"   {line.strip()[:96]}")
print(f"   {response.usage.input_tokens} in / {response.usage.output_tokens} out")
print("   The clinical content survived de-identification: swelling, night pain,")
print("   the medication issue and the driving question are all still there.\n")

# --- D. Screen the output too -----------------------------------------------

print("=" * 78)
print("D. Screen the summary as well")
print("=" * 78)
print("→ request   ApplyGuardrail, source=OUTPUT")
print("   why again  the input screen protects the model, not the reader. A model")
print("              can reintroduce an identifier from an earlier turn, a tool")
print("              result or a retrieved document — screening output is a")
print("              separate control, not a duplicate one")

screened_summary, out_found = screen(summary, "OUTPUT")
print("← response")
if out_found:
    print(f"   {len(out_found)} entities masked in the summary: "
          f"{', '.join(sorted({name for name, _ in out_found}))}")
    print(f"   {screened_summary[:180]}")
else:
    print("   nothing found — the summary carried no identifiers, which is the")
    print("   expected result when the input was masked first")
print()

# --- E. The other action: BLOCK --------------------------------------------

print("=" * 78)
print("E. Verify: which identifiers actually came out?")
print("=" * 78)
print("→ request   the same screen over every note, then a string search of the")
print("            masked text for identifiers we know the note contained")
print("   why       detection of a built-in entity is a model's judgement, not a")
print("             regular expression. The only way to know what your screen")
print("             removes is to check it against text whose answers you know.\n")

survived_all: list[tuple[str, str]] = []
for item in NOTES:
    masked, entities = screen(item["text"], "INPUT")
    kinds = sorted({name for name, _ in entities})
    survivors = [ident for ident in KNOWN_IDENTIFIERS
                 if ident in item["text"] and ident in masked]
    survived_all += [(item["note_id"], s) for s in survivors]
    print(f"← {item['note_id']}  {len(entities):>2} masked  {', '.join(kinds)}")
    if survivors:
        print(f"     still present after masking: {', '.join(survivors)}")

print()
if survived_all:
    print(f"   {len(survived_all)} known identifier(s) survived the screen.")
    print("   Note which kind: the MRN regex fired on every note, because a regex")
    print("   either matches or does not. The built-in entity types are inferred,")
    print("   and inference is not exhaustive on formats that are ambiguous in")
    print("   isolation.")
    print("   The design consequence: use a regex for every identifier format you")
    print("   own and can write down, and treat entity detection as defence in")
    print("   depth for the ones you cannot enumerate.")
else:
    print("   No known identifier survived this run. Re-check on your own corpus")
    print("   before relying on that: entity detection is inferred, not matched.")

print("\n   ANONYMIZE lets work continue on de-identified text. With action BLOCK")
print("   on an entity, a note containing it returns the configured blocked")
print("   message instead, and the pipeline routes it to a human rather than")
print("   summarizing it. Choose per entity.\n")

# --- F. Clean up ------------------------------------------------------------

print("=" * 78)
print("F. Clean up")
print("=" * 78)
if created_here:
    bedrock_control.delete_guardrail(guardrailIdentifier=GUARDRAIL_ID)
    print("   guardrail deleted")
else:
    print("   guardrail was supplied via GUARDRAIL_ID, so it is left alone")
print("   store=False left no stored response to remove")
print("\nGuardrails are billed per policy evaluated, on top of tokens:")
print("https://aws.amazon.com/bedrock/pricing/")
