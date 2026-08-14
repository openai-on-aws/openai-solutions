# Grounding and multimodal

> **How do I get answers about things the model was not trained on, and trust them?**

Four recipes, on the two ways a model gets information it was not trained on. Two of them
retrieve through Bedrock's own web index and check what comes back; one retrieves from your
own corpus through a Bedrock Knowledge Base; and the last reads what you
already hold —
a photograph, a scanned document — because plenty of the information a business needs was never
typed.

The reason to do the retrieval half on Bedrock rather than assembling it yourself is
[Web Search](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html): one entry
in `tools` and Bedrock runs the entire retrieval lifecycle against an AWS-operated index, with
no search provider contract, no API key to rotate, and no client-side loop. Citations come back
attached to the text with character offsets, so you can show a source next to the sentence it
supports.

> **The first two recipes do not chain end to end, and it is worth knowing before you plan
> around it.** Retrieve, answer, then score the answer against its sources is the right arc, but
> native Web Search injects retrieved content into the request and does not return it, so there
> is no source text to hand a grounding check as its `grounding_source`. Contextual grounding
> applies to retrieval you control — a corpus you supply, as the second recipe does. Scoring an
> answer grounded in Web Search needs you to fetch and hold the sources yourself.

## What you get, and what it costs

- **Retrieval is managed.** Bedrock decides when to search, writes the queries, reformulates
  them, fetches cached pages, and returns citations.
- **Nothing leaves the AWS boundary by default.** Retrieval is served from the Bedrock index and
  cache, and it is strictly regional.
- **The bill moves to input tokens.** Retrieved content is injected into the request, so a
  grounded turn is dominated by input, and `search_context_size` is the lever on how much.
- **Faithfulness is measurable.** A contextual grounding check scores an answer against the
  source you supplied and returns a number you can gate on.
- **Images and documents go in the same request as the question.** An `input_image` or an
  `input_file` block sits alongside your text, inlined as base64, so reading a scan needs no
  upload step and no OCR stage in front of it.
- **Media is priced by size, and its own tokens never cache.** A document costs far less than the
  same pages rasterised into images, and the text around it — instructions, a schema — caches
  normally. The document itself does not, so ask everything you need in one pass rather than
  returning to the same pages.

## Recipes

<!-- BEGIN GENERATED: group-index -->
| Recipe | What it teaches | Level | Cost |
| --- | --- | --- | --- |
| [`01-grounded-regulatory-monitoring/`](01-grounded-regulatory-monitoring/) | Grounded regulatory change monitoring with native Web Search | intermediate | medium |
| [`02-scoring-a-grounded-answer/`](02-scoring-a-grounded-answer/) | Trusting a grounded answer: scoring it against its sources | intermediate | medium |
| [`03-reading-a-scanned-manual/`](03-reading-a-scanned-manual/) | Reading a scanned manual: photos, tables and figures | intermediate | medium |
| [`04-rag-with-knowledge-bases/`](04-rag-with-knowledge-bases/) | RAG with Bedrock Knowledge Bases: retrieve then generate with citations | intermediate | low |
<!-- END GENERATED: group-index -->

## Running these

```bash
uv sync
uv run python \
  03-grounding-and-multimodal/01-grounded-regulatory-monitoring/python/grounded_monitoring.py
```

The first recipe needs the two `bedrock-websearch` actions alongside inference. The second
creates a guardrail and deletes it, or reuses one you name. The third needs inference only, and
reads its two documents from `data/`. Each README states the permissions it needs.

## Where to go next

- [`cookbooks/02-reasoning-and-output/01-structured-claims-intake/`](../02-reasoning-and-output/01-structured-claims-intake/)
  — a schema with an `answered` field is how you tell a refusal from an answer before you score
  it.
- [`cookbooks/05-production/01-prompt-caching/`](../05-production/01-prompt-caching/) — a long
  stable prefix is exactly what a grounded workload accumulates.
