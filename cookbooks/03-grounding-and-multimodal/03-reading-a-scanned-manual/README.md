---
title: "Reading a scanned manual: photos, tables and figures"
capabilities: [MMD-02, MMD-01, MMD-03]
primary_capability: MMD-02
industry: MFG
industry_scenario: >
  A field service engineer at a press manufacturer needs a torque specification for a
  machine in front of them. The identity is on a stainless nameplate they can photograph,
  the specification is in a manual scanned in 2019, and the decision also depends on the
  plant's own inspection readings — so the answer needs three sources, none of which is
  queryable text.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-14
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Reading a scanned manual: photos, tables and figures

Industrial documentation is old, visual, and rarely typed. The specification you need is
in a table on page 4-1 of a scan, the machine's identity is riveted to its frame, and the
reason you are asking is a reading somebody wrote into a maintenance system last month.

| | |
|:--|:--|
| **What you will learn** | How to send photographs and scanned documents to a model on Bedrock, and what they cost |
| **Capability** | Image and document input on the Responses API |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Intermediate |
| **Cost** | Medium — five calls, four of which carry a four-page document or a photograph |
| **You will need** | Inference permission only |

> **What it does.** Reads a nameplate photograph into a strict schema, answers a question
> from a four-page scanned manual, then combines both with a tool call to decide whether a
> bolt needs replacing. **What it creates.** Nothing — inference only, `store=False`
> throughout.

## The documents are synthetic, and generated rather than scanned

`data/nameplate.jpg` and `data/service-manual.pdf` are fabricated. AnyCompany Industries does
not exist, the press does not exist, and no page here was scanned from a real manual — a
real one is copyrighted, and a real nameplate photograph identifies a real machine on a
real site.

They are also **deliberately imperfect**, because that is the whole difficulty of the
task. The manual's pages are skewed by a fraction of a degree, speckled with scanner
dust, and shadowed down one edge where the lid did not close flat. The nameplate is a
phone photograph taken at an angle under a flash, and the asset tag has been worn away by
years of hands. A clean render would make this recipe look better and teach less.

## Two input types, one shape

An image goes in an `input_image` block and a document in an `input_file` block, both
inlined as base64 data URLs alongside the text of your question:

```python
{"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}
{"type": "input_file", "filename": "service-manual.pdf",
 "file_data": f"data:application/pdf;base64,{b64}"}
```

**The Files API is not the path here.** `client.files.create(...)` raises `OpenAIError:
Bedrock SigV4 authentication requires a replayable request body`, because a multipart
upload cannot be signed the way Bedrock needs. That leaves two ways in, and this recipe
uses the first because it needs no setup from you.

### Inline base64, or an S3 URI

Bedrock accepts **`s3://` in place of the data URL**, for both block types, and this is
the one place where a Bedrock workload has an option the first-party API does not:

```python
{"type": "input_image", "image_url": "s3://my-bucket/nameplate.jpg"}
{"type": "input_file", "filename": "service-manual.pdf",
 "file_url": "s3://my-bucket/service-manual.pdf"}
```

The token cost is identical — the same photograph billed 938 input tokens inline and 938
from S3 — so this is not a saving on inference. What it changes is everything around it:
the bytes never enter the request body, so you are not paying a 33% base64 expansion on
the wire or working against a request-size limit, and access to the object is governed by
your bucket policy and the caller's IAM rather than by whoever can see the payload. For a
document pipeline whose inputs already live in S3, it also removes a download step.

Two things to know before you reach for it.

**`filename` is required on `input_file` when you use `file_url`.** Without it the service
cannot infer the type and returns `400 validation_error: Unsupported file type: 'unknown'`.
The same error names the full list it accepts, which is worth knowing: PDF, DOCX, XLSX,
CSV, TXT, MD and HTML.

**An `https://` URL is not an option, and the two block types fail differently.** The
first-party vision guide leads with a public image URL; here `input_image` rejects it
cleanly with `400 validation_error: unsupported image_url scheme: must be 'data:' or
's3://'`. An `input_file` pointing at `https://` is worse: the request returns **200 with
an empty answer**, because the document was never fetched and the model had nothing to read.
If you are porting code that passes URLs, that is the case to grep for.

## What you will build

```
A. the nameplate photo    a strict schema, and a field that must come back null
B. the scanned manual     a table on one page, a figure on another
C. all three sources      photo + document + a tool call, to reach a decision
D. what it cost           and the one lever that exists for lowering it
```

## Reading a photograph into a schema

The interesting part of section A is not that the model transcribes the plate. It is the
field it refuses to transcribe.

The asset tag is physically worn — `AC-PR-0` is visible and the rest is scuffed metal. The
model is told to return null for anything damaged and to name it in `unreadable_fields`,
and the field is typed to allow that:

```python
class Nameplate(BaseModel):
    manufacturer: str
    serial_number: str
    asset_tag: str | None          # may be unreadable
    unreadable_fields: list[str]
```

```
   manufacturer       'ANYCOMPANY INDUSTRIES'
   model              'VX-4400-B'
   serial_number      '7731-QA-0042'
   max_pressure       '12.5 bar'
   hydraulic_oil      'ISO VG 46'
   manufacture_date   '2019-04'
   asset_tag          None
   unreadable_fields  ['asset_tag']
   1134 input / 111 output tokens
```

That combination — a nullable field plus an instruction not to complete values from
context — is what makes an extraction pipeline safe to run unattended. A field typed as a
plain `str` gives the model no way to report damage, and an invented asset tag flows into
an asset register where nobody will question it again.

**Note what `str | None` means under `strict`.** The field is still *required*; it is
allowed to be null. There is no way to say "may be absent", so every record accounts for
every field — which is the constraint you want when the records are going into a system of
record rather than a chat window.

### `responses.parse` here, a JSON schema in the claims recipe

This recipe calls `client.responses.parse(..., text_format=Nameplate)` and gets a
`Nameplate` instance back on `response.output_parsed`. The SDK derives the strict JSON
schema from the class, sends it in the same `text.format` field the raw form uses, and
parses the reply. You can confirm what it sent by reading `response.text.format` back:
`strict` is `True` and the schema name is the class name, neither of which you had to
write. `asset_tag` comes back as a real `None` and `unreadable_fields` as a real list, so
there is no `json.loads` and no dictionary to guess your way around. `pydantic` arrives
with the `openai` package, so this costs no extra dependency.

[`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
writes the schema out as a dictionary instead, and the difference is not style. There, the
schema **is** the lesson: what `additionalProperties: false` rejects, what `strict` does to
`required`, and what the model sends back when a value is missing. Here the photograph is
the lesson and the schema is how its uncertainty is held, so the shorter form is the one
that keeps the image work in view. Use the model class in your own code; read the
dictionary form when you want to know what goes over the wire.

## Reading four scanned pages

Section B asks one question with four parts, and each part is somewhere different: the
torque and tolerance are in a table on page 4-1, the rule about replacing rather than
re-torquing is in the paragraph under it, and the tightening order is a numbered figure on
page 5-1. Asking for page numbers is not decoration — it is how you tell a real read from
a plausible one.

```
- Torque: 110 Nm. (Page 4-1)
- Tolerance: +/- 5 Nm. (Page 4-1)
- If below the tolerance band: "the bolt [is] to be replaced, not re-torqued." (Page 4-1)
- Tightening order (Figure 5-1): 1, 2, 3, 4 — to 50% of the specified torque,
  then repeat the same order to the full value. (Page 5-1)

2300 input / 190 output tokens for four pages
```

**Four scanned pages cost about the same as a single large photograph.** 2,300 input
tokens for the whole manual, against 1,134 for one 1080x720 JPEG. Document input is
priced far more favourably than rasterising the same pages yourself and sending four
images, which is the naive alternative and would have cost roughly four times as much.

## The decision needs all three sources

Section C is the recipe's reason to exist. The question is whether one bolt needs
replacing, and answering it requires:

- **the photograph**, because the serial number is the key into the maintenance system;
- **the document**, because the tolerance band and the replace-or-re-torque rule are in it;
- **the tool**, because the reading that prompted the question lives in the plant's records.

The model is given the photo, the manual and one function, and works it out:

```
   ← tool call  get_service_history(7731-QA-0042)
     returned 3 inspections, readings [108, 71] Nm

   Replace the main frame bolt (Bolt C); do not simply re-torque it.
   - Machine serial read from the nameplate: 7731-QA-0042 (VX-4400-B).
   - Latest history reading for Main frame bolt C: 71 Nm on 2026-06-02, flagged.
   - The manual lists Bolt C at 110 Nm ±5 Nm, so its acceptable band is 105–115 Nm.
   - The manual's explicit rule is: "A reading below the tolerance band requires the
     bolt to be replaced, not re-torqued." At 71 Nm, this bolt is well below the limit.
```

It also volunteered two things nobody asked for and a service engineer would want: that
the machine is at 1,120 hours since its frame-bolt check against a 1,000-hour interval,
and that the manual's warning box requires relieving hydraulic pressure to 0 bar before
loosening the fastener. Both came from pages the question did not point at.

**A media-carrying tool loop is expensive, and the media is why.** Those two model calls
cost 7,159 input tokens between them on this run, because the photograph and the manual are
resent with every turn — the transcript grows by the tool result, but the attachments are
already the bulk of it. Expect your own figure to land near rather than on that, since the
second turn also carries the model's reply from the first. Two design responses follow: keep
media-carrying loops short, and pass a transcription forward instead of the image where a
later turn only needs the values.

## What it cost, and the one lever that exists

A document you ask ten questions of is sent ten times. The obvious fix is prompt caching,
and it does not work here.

**The document's own tokens never enter the cache. The text around it caches normally.** That
distinction is the whole of it, and it decides how you arrange a request:

| Where the breakpoint goes | `cache_write_tokens` | `cached_tokens` on the next call |
|:--|:--|:--|
| On the `input_file` block itself | 0 | 0 |
| On a text block **before** the document | 1,092 | 1,092 |
| On a text block **after** the document | 1,092 | 1,092 |
| Implicit mode, the identical request sent twice | 0 | 0 |

The two middle rows are the useful ones, and note what is missing from them: the request bills
about 3,290 input tokens, of which roughly 2,200 are the four pages — and only the 1,092 tokens of
text were cached. The prefix up to the breakpoint contains the document either way, and the
document is not what gets written.

So a document workflow can still cache its instructions, its schema and any stable preamble, and
the position of the breakpoint relative to the document does not matter. What you cannot avoid is
paying for the document again on every request, which is why the lever below is about how many
questions you ask per request rather than about caching.

Implicit mode caches nothing here because the only text in that request is a one-line question,
far under the 1,024-token minimum for a cacheable prefix.

The lever that does exist is batching, and here is every figure this recipe measured, in one
place:

| What you send | Input tokens | |
|:--|--:|:--|
| One 1080x720 JPEG photograph | 1,134 | measured |
| The four-page PDF as one `input_file`, with a four-part question | 2,300 | measured |
| The same PDF, four separate questions in one request | 2,270 | measured |
| Those four questions as four requests | ~9,080 | 2,270 × 4 — the document is resent each time |
| The same four pages rasterised into four images | several times the PDF | not measured here |
| The section C loop: photograph + PDF over two turns | 7,159 | one run — see below |

So structure a document workflow around one pass that extracts everything you will need,
rather than a conversation that returns to the same pages.

### A PDF's page size decides both its cost and how well it reads

This is the lever most people do not know they are holding, and it is not the resolution of
the images inside the file. A PDF page is rasterised at **its declared size in points**, and
billed as patches over that: `ceil(width / 32) x ceil(height / 32)` per page. The same
pixels, saved into PDFs that declare three different page sizes, cost twelve times more at
one end than the other:

| Declared page size | Patches over four pages | Input tokens | Read the fastener sizes correctly? |
|:--|--:|--:|:--|
| 1240 x 1754 pt | 8,580 | 8,742 | yes |
| 595 x 842 pt (A4, what this manual ships as) | 2,052 | 2,214 | yes |
| 298 x 421 pt | 560 | 722 | **no — reported M8 where the table says M10** |

The file was byte-identical in all three cases at 325 KB, so nothing about the image data
changed. What changed is how many pixels the model was given to look at.

**The last row is why this is a fidelity control and not a discount.** At the smallest page
size the answer came back confidently and wrongly: the torque and tolerance were right, and
the guard bracket bolt was reported as M8 where the manual says M10. Nothing in the response
signalled a problem — no error, no hedge, no low-confidence note. So treat page size as a
knob you tune with a legibility check on your own documents, and re-run that check when the
documents change. A wrong fastener size is worse than an expensive one.

**Why your numbers may differ, and what will not.** The first three rows are fixed: send the
same bytes and the same text and you get the same count, every run — repeat the request and
check. What moves them is your own prompt — a longer question or a bigger schema adds
tokens on top of the media, which is why the two PDF rows differ by 30 for the same four
pages. The two-turn figure is the one to treat loosely, because the second turn carries the
model's own reply from the first and that varies run to run. And a service-side change to how images or
PDF pages are processed would shift every figure here, so treat them as the shape of the
problem rather than as constants.

The **relationships** are what the design decisions rest on, and those hold either way: a
document sent once always beats the same document sent four times, by close to a factor of
four; `input_file` always beats rasterising the same pages yourself; and a media-carrying loop
always costs more per turn than a single-turn question, because the attachments go again.

For how caching behaves when your prefix is text, see
[`cookbooks/05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/).

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md): a Region with model
  access, and IAM permissions for inference on `bedrock-mantle`.
- Working AWS credentials — `aws sts get-caller-identity` must succeed.
- No extra dependencies. The recipe reads the two committed files with `base64` and
  `pathlib` from the standard library.

**Cost:** medium. Five calls, and four of them carry a four-page document or a
photograph, so image and document tokens dominate the bill rather than the text. See
[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 03-grounding-and-multimodal/03-reading-a-scanned-manual/python/reading_a_scanned_manual.py
```

## Production considerations

- **Size the images you send; `detail` will not do it for you.** On this endpoint the
  `detail` parameter is accepted and the bill does not move: omitted, `low`, `high`,
  `original` and `auto` all billed the same 938 input tokens on the same photograph. Resize
  the image instead, where the saving is arithmetic and certain. A phone camera produces far
  more pixels than a nameplate needs, so downscale before you inline: the
  photograph here is 1080x720 and legible at 1,134 tokens. You can predict the figure
  before you send anything: an image is covered in 32-pixel patches and billed at
  `ceil(width / 32) x ceil(height / 32)`. That is 34 x 23 = 782 for this photograph, and
  halving both sides takes it to 204 — a measured 938 input tokens against 360 for the
  same request, since the text around the image is a constant.
- **Prefer document input to your own rasterisation.** Sending a PDF as `input_file` cost
  2,300 tokens for four pages, where four page images would have cost several times that.
- **Point at S3 rather than inlining, once the inputs live there.** It costs the same in
  tokens and takes the bytes out of the request body, which matters as soon as your
  documents are larger than the two here. Give the model's caller `s3:GetObject` on the
  prefix and nothing wider.
- **Extract once, then work from the extraction.** The document is re-sent and re-billed on
  every request, because its tokens never enter the cache, so a workflow that asks a document
  twenty questions should ask them in one pass and keep the structured result — which is text,
  and does cache.
- **Give every extracted field somewhere to be empty.** A nullable field plus an explicit
  instruction is the difference between a pipeline that reports damage and one that
  invents values.
- **Ask for page numbers or quotations on anything consequential**, so a reviewer can
  check the answer against the source without re-reading the document.
- **Watch `max_output_tokens` on document questions.** A four-part answer with citations
  runs longer than a chat reply, and reasoning tokens come from the same budget.

## Data handling and security

- Credentials come from the AWS credential chain; there is no API key in the code.
- `store=False` on every call. These are single-turn questions with nothing to refer back
  to, and in a real deployment the inputs would be a customer's maintenance records.
- The photograph and the manual are sent as inline base64 in the request body, so they
  are in transit to the Region you name and are not persisted by the recipe.
- The synthetic history file stands in for a maintenance system. A real integration would
  reach it through a tool with its own authorization, which is what makes the tool
  boundary in section C the right shape.
- Nothing here is a real machine, a real site or a real person.

## Limitations and non-goals

- Does not do OCR as a separate step. The model reads the pages directly; if you need a
  text layer to store or search, that is a different pipeline.
- Does not handle handwriting. The inspection notes in this scenario arrive as data from
  the maintenance system, not as scanned annotations.
- Does not split a long document. Four pages fit comfortably in one request; a
  300-page manual needs a retrieval step in front of the model, and the page images are
  not the right unit for that.
- Does not verify the model's reading against a ground-truth transcription. For an
  extraction pipeline you would score a sample against known values before trusting it.
- Does not cover audio or video, which these models do not accept.

## Clean up

Nothing to tear down: the recipe only calls the model, and `store=False` means no
response is retained. The two documents are committed fixtures — leave them in place.

## Next steps

- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
  — strict schemas over messy input, in depth.
- [`cookbooks/02-reasoning-and-output/03-tool-calling/`](../../02-reasoning-and-output/03-tool-calling/)
  — the tool loop used in section C, on its own.
- [`cookbooks/05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/)
  — what caching does for a text prefix, since it does nothing for these.
- [`cookbooks/03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](../01-grounded-regulatory-monitoring/)
  — grounding an answer in the live web rather than in a file you hold.
