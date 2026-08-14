---
title: Grounded regulatory change monitoring with native Web Search
capabilities: [GRD-01, GRD-02, GOV-05]
primary_capability: GRD-01
industry: FSI
industry_scenario: >
  A retail bank's regulatory change working group maintains a watchlist of instruments
  affecting its payments platform and has to produce a periodic digest of what changed.
  An unsourced claim in that digest is an audit finding, so every sentence has to be
  traceable to a document.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
level: intermediate
estimated_cost: medium
status: validated
last_validated: 2026-08-11
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# Grounded regulatory change monitoring with native Web Search

A compliance digest needs two things: what changed, and where each claim came from. The
second is the hard one, and it is what
[Web Search on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html)
gives you directly.

| | |
|:--|:--|
| **What you will learn** | How to ground an answer with Bedrock's own web index, read the citations, and control what a grounded turn costs |
| **Capability** | Native Web Search on the Responses API |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1`, `us-east-2` or `us-west-2` |
| **Level** | Intermediate |
| **Cost** | Medium — around a dozen billed retrieval operations plus ~70,000 input tokens |
| **You will need** | The two `bedrock-websearch` actions alongside inference |

> **What it does.** Answers watchlist questions with and without the tool, shows the retrieval
> steps and citations, then builds a sourced digest. **What it creates.** Nothing —
> `store=False` throughout, and retrieval is served from the AWS index.

Web Search is a **server-side built-in tool**. You add one entry to `tools` and Bedrock
runs the entire retrieval lifecycle against an AWS-operated web index and knowledge
graph: it decides when to search, issues the queries, reformulates them if the first
results are thin, fetches cached pages when it needs them, and returns an answer with
`url_citation` annotations attached. What you do not build is the part that usually takes
the week — a search provider contract, an API key to rotate, a retrieval service, and the
client-side tool loop to drive it.

The same watchlist question, without the tool and with it:

| | Input tokens | Output tokens | Retrieval steps | Citations |
| --- | --- | --- | --- | --- |
| No tool | 65 | 2,318 (1,552 of them reasoning) | — | 0 |
| Web Search | 19,577 | 2,033 | 3 | 22, from 3 distinct sources |

Both answers read like a competent analyst wrote them. Only one can be filed — and note
the first row: asked what changed recently, the ungrounded model spent 1,552 tokens
*thinking* before producing something no one can check. Grounding replaces that guesswork
with retrieval.

## What you will build

```
A. no tool        the answer you cannot cite
B. Web Search     one tool declaration, and Bedrock does the retrieval
C. show its work  the retrieval steps and citations on the response
D. the digest     one sourced entry per watchlist topic
```

Each phase ends by printing what it cost — input tokens, output tokens, retrieval steps
and citations — because on a grounded turn those four numbers move independently.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md), plus **Web Search
  permissions**: `bedrock-websearch:InvokeSearch` and `bedrock-websearch:InvokeFetch`.
  The `AmazonBedrockMantleInferenceAccess` managed policy grants both
  ([policy document](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockMantleInferenceAccess.html)),
  and there are dedicated `AmazonBedrockWebSearch*` policies if you would rather grant
  them separately
  ([Web Search security](https://docs.aws.amazon.com/bedrock/latest/userguide/security-web-search.html)).
- **A Region where Web Search is available**: `us-east-1`, `us-east-2` or `us-west-2`. It
  is strictly regional — queries, fetches, index data and results are not routed across
  Regions.
- Synthetic data in [`data/watchlist.json`](data/watchlist.json) — a fabricated watchlist
  for a fictional bank. The regulations named are real public instruments; the
  institution, owners and reference numbers are invented.

**Cost: medium, and this is the first recipe here where the fee is not only tokens.** Web
Search is billed **per retrieval operation**, separately from tokens; this run performs
around a dozen operations plus roughly 70,000 input tokens. Nothing in `response.usage`
reports the search fee — count the `web_search_call` items.

Budget for one more thing that is easy to miss: **attaching the tool costs input tokens
before any search happens.** The same trivial prompt billed 13 input tokens without the
tool and 2,920 with it and zero searches — a fixed overhead of 2,907 tokens per request.
That is the tool definition entering context, and it is charged on every request that
carries the tool, so attach it to the calls that may need
grounding rather than to every call in an application. Rates are on the
[pricing page](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python \
  03-grounding-and-multimodal/01-grounded-regulatory-monitoring/python/grounded_monitoring.py
```

Expect two to three minutes. A grounded turn runs several retrieval steps server-side, so
give the client a timeout that reflects that — this recipe sets 300 seconds, well above
the SDK default.

## The whole declaration

```python
response = client.responses.create(
    model=MODEL_ID,
    instructions=ANALYST_INSTRUCTIONS,
    input=topic["question"],
    tools=[{"type": "web_search", "external_web_access": False}],
    max_tool_calls=8,
    max_output_tokens=3000,
    store=False,
)
```

That is the integration. No tool implementation, no key, no loop.

Two parameters are worth setting deliberately.

**`max_tool_calls` is the cost control on a grounded turn**, because each retrieval step
is a billed operation. Eight is generous for a watchlist question and keeps a broad
question from fanning out indefinitely. Pair it with an instruction that tells the model
to stop searching and answer — the instructions in this recipe say "do not run more than
two rounds of searches", and the observed turns used two or three steps.

**`external_web_access` is worth setting deliberately.** It defaults to `true`, which
matches the OpenAI Responses API so that a call ported from there behaves the same way —
a sensible default for compatibility. At `true`, search and fetch are permitted to reach the
**live external web**, and that asks the request identity to hold
`bedrock-websearch:ExternalWebAccess`.

This recipe sets it `false`, because a compliance digest wants the narrower posture: retrieval
is then served entirely from the Bedrock web index and cache, request data does not leave the
AWS boundary for retrieval, and it needs no permission beyond the two Web Search actions. The
[documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.html) calls
that configuration safe by default, and for a regulated workload it is the one to reach for.

![A grounded turn inside one AWS Region, us-east-1, marked strictly regional. The application declares web_search with external_web_access false and calls the bedrock-mantle endpoint serving openai.gpt-5.6-terra. A server-side retrieval loop reads from the Bedrock web index and cache, which sit inside the same Region, using InvokeSearch for titles, URLs and snippets and InvokeFetch for cached page content. One arrow leaves the Region towards the live external web, and it opens only if external_web_access is true and the caller holds the ExternalWebAccess permission. With false, retrieval is served entirely from the index and cache and no data leaves the AWS boundary.](images/web-search-path.drawio.svg)

*The index and the cache are inside the Region, which is the fact that makes this posture
defensible: grounding does not imply an outbound call to the web. Only one arrow can leave, and
it takes two conditions to open — the parameter and the IAM permission, together.*

## What the response carries

The retrieval steps are items on the response, so the digest can show its work:

```
completed  search     3 query string(s)
   site:oeil.europarl.europa.eu Payment Services Regulation 2023/0210 COD procedure status
   site:oeil.europarl.europa.eu PSD3 2023/0209 COD procedure status
completed  search     4 query string(s)
   site:consilium.europa.eu "payment services" "2026" PSR PSD3
completed  open_page  fetched: https://www.europarl.europa.eu/legislative-train/…
```

Three things there are worth knowing.

**The model writes better queries than a keyword handoff would.** It scoped searches to
`site:consilium.europa.eu` and to the Parliament's Legislative Observatory, and it
searched by procedure number — `2023/0209(COD)` — which is how a regulatory analyst
actually looks this up.

**A step can fan out.** `action.type` is `search`, `open_page` or `find_in_page`, and a
single `search` item carried three or four query strings. For budgeting that matters:
**one `web_search_call` item is one billed operation however many query strings it
carries.** Count items, not queries.

**Fetches are a separate capability.** The `open_page` step is why `InvokeFetch` is a
distinct IAM action from `InvokeSearch` — searching returns titles, URLs and snippets,
while fetching pulls cached page content for a specific URL.

Citations arrive as `url_citation` annotations on the message content, each with a title,
a URL and the character span of the answer it is attached to:

```
22 citation annotation(s), 3 distinct sources
   https://www.consilium.europa.eu/en/press/press-releases/2025/11/27/payment-services-…
   https://www.europarl.europa.eu/legislative-train/…/file-payment-services
   https://www.europarl.europa.eu/legislative-train/…/file-revision-of-the-payment-services-directive
```

The span is what lets you render a source next to the sentence it supports rather than in
a footnote pile. Note the ratio — 22 annotations resolved to 3 sources, because the same
document is cited repeatedly — so deduplicate before showing a human a source list, which
is what the digest phase does.

**The acceptable-use terms require you to retain and display these citations** in
anything surfaced to end users, and prohibit bulk-extracting results or building a
competing index. For a compliance digest that is no imposition: the citations are the
deliverable.

## `search_context_size` is the lever on what grounding costs

Retrieved content is injected into the input, so input tokens dominate a grounded turn's
token bill — and `search_context_size` sets how much gets injected per search. Measured on
one question held constant, because input tokens also scale with how many searches the
model runs:

| `search_context_size` | Input tokens | Searches |
| --- | --- | --- |
| `low` | 3,730 | 2 |
| `medium` | 6,384 | 2 |
| `high` | 12,852 | 1 |

That is a wide enough range to be a design decision rather than a tuning detail: `low`
bought two searches for less than `high` spent on one.

**Set it explicitly.** The value comes back on `response.tools[0]`, so you can confirm what
the service used rather than assuming. `medium` is a sensible default for a digest;
`high` earns its tokens when the answer depends on detail buried in a long page, and `low`
is for high-volume grounding where you want breadth over depth — with the caveat that less
injected context gives the model less to cite, and the `low` run above produced fewer
citations.

## The digest

The last phase produces the thing the working group actually wants — one entry per
watchlist topic, each with its sources and its cost:

```
RCM-021  Digital Operational Resilience Act (DORA)  (owner: Operational Resilience)
   On 8 July 2026, ESMA launched a Common Supervisory Action on crypto-asset service
   providers' digital operational resilience for custody…
   source: https://www.esma.europa.eu/press-news/esma-news/esas-publish-first-report-dora-…
   cost: 10,188 input tokens, 915 output, 2 searches, 4 citations
```

Per-topic cost is printed for a reason: the two topics in this run cost 10,188 and 23,542
input tokens on two retrieval steps each. **How much a grounded turn costs is
decided by how much the model chooses to retrieve**, not by the length of your question,
so a digest's cost scales with the number of topics *and* with how contested each one is.
Budget per operation and measure per topic.

## Production considerations

- **Cost scales per operation.** Ten watchlist topics at two to four steps each is 20 to
  40 billed operations plus six figures of input tokens per run. Pick the cadence
  deliberately: a daily digest is not a seventh of a weekly one if every run re-searches
  everything from scratch.
- **Cache the stable prefix.** The analyst instructions and watchlist framing are
  identical on every call — a long stable prefix with a short changing suffix is exactly
  what prompt caching is for.
- **Check `web_search_call[].status` before publishing.** It is the field that tells you
  retrieval actually happened, and it is more informative than the HTTP status on a turn
  that ran tools server-side.
- **Store the URL, title and retrieval date with the digest, and deduplicate sources.**
  The Bedrock index is a cache, not an archive; if you need the page as it read today,
  keep your own copy.
- **CloudTrail records `InvokeSearch` and `InvokeFetch` as data events, and data events
  are off by default.** Turn them on (resource type `AWS::BedrockWebSearch::Tool`) if the
  digest needs an audit trail, and note that by design they do not record query text,
  returned URLs or page content.
- **Set a generous client timeout** and expect latency proportional to retrieval steps.
  A retry re-runs the searches and bills them again, so prefer a longer timeout to an
  aggressive retry.
- **Keep a human on sufficiency.** Grounding makes an answer traceable; whether the
  retrieved sources are enough to file is a judgement, and the instructions in this
  recipe are written to make the model say so when they are not.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS
  credential chain; nothing is passed, stored or printed.
- **`store=False` on every call**, so AWS retains neither request nor response.
- **`external_web_access: False`**, so retrieval is served from the AWS-operated index and
  cache and request data does not leave the AWS boundary for retrieval.
- **Inference and retrieval stay in the Region you name.** Web Search is strictly
  regional, which is a large part of why it suits a regulated workload.
- **A search query is derived from your input.** These queries are about public
  regulation, but a workflow that grounds on customer-specific text is sending that text
  into a retrieval path — worth reviewing before you enable the tool on such a prompt.
- **The watchlist is fabricated.** No real institution, register, owner or engagement.

## Limitations and non-goals

- **No claim-level provenance.** The annotations locate citations in the answer text;
  joining a specific assertion to a specific sentence of a source is a harder problem.
- **Does not verify that a cited page says what the answer says it says.** Nothing here
  re-fetches a URL and checks it.
- **Does not persist the digest.** A real one goes to a store with a retrieval timestamp;
  this prints to stdout.
- **Does not stream.** Grounded turns emit `response.output_text.annotation.added` events,
  which are useful for a live UI and unnecessary for a batch digest.
- **One Region, one day, one watchlist.** Index coverage and freshness are not something a
  single run establishes.

## Clean up

Nothing to tear down. On-demand inference and Web Search create no resources, and
`store=False` means there is no stored response to delete. If you switched on CloudTrail
data events for `AWS::BedrockWebSearch::Tool` while reading the production notes, they
bill per event — switch them off if the trail was only for this exercise.

## Next steps

- [`cookbooks/01-foundations/05-streaming/`](../../01-foundations/05-streaming/) — the typed
  event stream, where annotations arrive live for a UI.
- [`cookbooks/01-foundations/06-choosing-a-model/`](../../01-foundations/06-choosing-a-model/) —
  whether a digest of this shape needs the mid tier at all.
