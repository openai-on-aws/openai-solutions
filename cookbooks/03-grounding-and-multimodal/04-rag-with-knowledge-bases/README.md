---
title: "RAG with Bedrock Knowledge Bases: retrieve then generate with citations"
capabilities: [GRD-03, GRD-04]
primary_capability: GRD-03
industry: research
industry_scenario: >
  A research team maintains a corpus of scientific papers in a Bedrock Knowledge Base
  and needs a question-answering interface that grounds every claim in a source document.
  An unsourced assertion is worthless in a research context, so the system must produce
  inline citations that trace back to specific documents.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock:Retrieve
level: intermediate
estimated_cost: low
status: validated
last_validated: 2026-08-14
validated_with:
  python: "3.12"
  openai: "2.53.0"
---
# RAG with Bedrock Knowledge Bases: retrieve then generate with citations

You have documents in a Bedrock Knowledge Base and you want a GPT-5.6 model to answer
questions grounded in that corpus — with inline citations that trace every claim back to a source. Bedrock offers a coupled `RetrieveAndGenerate` API, but you want control: custom
prompting, citation formatting, model choice independent of retrieval, and room to add
reranking or business logic between the two steps.


|                         |                                                                                                                                    |
| :------------------------ | :----------------------------------------------------------------------------------------------------------------------------------- |
| **What you will learn** | How to separate retrieval (Bedrock Knowledge Bases) from generation (GPT-5.6 via Bedrock Mantle) and produce inline`[n]` citations |
| **Capability**          | Two-step Retrieve-then-Generate with the Responses API                                                                             |
| **Model**               | `openai.gpt-5.6-terra`                                                                                                             |
| **Region**              | `us-east-1`                                                                                                                        |
| **Level**               | Intermediate                                                                                                                       |
| **Cost**                | Low — one retrieval call plus one generation call, capped at 1024 output tokens                                                   |
| **You will need**       | Inference permission, an existing Bedrock Knowledge Base with ingested documents, and`bedrock:Retrieve` permission                 |

> **What it does.** Retrieves the top-k chunks from a Knowledge Base, numbers them, passes
> them as context to GPT-5.6 with instructions to cite sources inline, and prints the
> grounded answer with a reference list. **What it creates.** Nothing — retrieval is
> read-only and generation uses `store=False`, so there is nothing to clean up.

## The pattern

```
┌──────────────┐   query    ┌──────────────────────────────────┐
│    Client    │ ─────────► │  rag_with_knowledge_bases.py     │
│  (CLI/app)   │ ◄───────── │                                  │
└──────────────┘   answer   └──────────────────────────────────┘
                                   │                  │
                          Step 1   │                  │  Step 2
                        (retrieve) │                  │  (generate)
                                   ▼                  ▼
                    ┌──────────────────┐   ┌──────────────────────┐
                    │  Bedrock         │   │  GPT-5.6 via         │
                    │  Knowledge Bases │   │  Bedrock Mantle      │
                    │  (vector search) │   │  (OpenAI Responses)  │
                    └──────────────────┘   └──────────────────────┘
                            │                         │
                            ▼                         ▼
                    ┌──────────────────┐   ┌──────────────────────┐
                    │  Your documents  │   │  Grounded answer     │
                    │  (S3, Web, etc.) │   │  with [n] citations  │
                    └──────────────────┘   └──────────────────────┘
```

The two-step separation means you can independently tune retrieval (number of results,
hybrid search, metadata filters) and generation (model choice, system prompt, reasoning
effort) without either side affecting the other.

## Why two steps instead of `RetrieveAndGenerate`

Bedrock's `RetrieveAndGenerate` couples both halves into one API call, which is
convenient but limits you:

- You cannot choose the generation model independently — it uses a Bedrock-managed model.
- You cannot inspect or filter chunks between retrieval and generation.
- You cannot format citations your way, inject business logic, or add a reranking step.
- You cannot use the OpenAI Responses API features (structured output, reasoning effort).

The two-step pattern gives you the managed vector search of Knowledge Bases with the full power of GPT-5.6 on generation, authenticated through the same AWS credential chain.

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md).
- **An existing Bedrock Knowledge Base** with documents already ingested. You need its
  Knowledge Base ID (looks like `XXXXXXXXXX`).
- **`bedrock:Retrieve` permission** on the Knowledge Base ARN. This is separate from the
  inference permission.
- **`boto3`** for the Retrieve API call. It is already in the base cookbook dependencies —
  `uv sync` installs it.

## Run it

```bash
uv sync
cp .env.example .env   # set KNOWLEDGE_BASE_ID and AWS_REGION

uv run --env-file .env python \
  03-grounding-and-multimodal/04-rag-with-knowledge-bases/python/rag_with_knowledge_bases.py

```

Pass a custom query as a positional argument:

```bash
uv run python \
  03-grounding-and-multimodal/04-rag-with-knowledge-bases/python/rag_with_knowledge_bases.py \
  "What are the effects of vessel noise on marine communication?"
```

## How it works

### Step 1: Retrieve

The script calls the Bedrock Knowledge Bases `Retrieve` API directly with the user's
query. This returns ranked chunks with relevance scores and source locations (S3 URIs or
web URLs). You control `k` (number of results) and can enable hybrid search or metadata
filters.

### Step 2: Build numbered context

Each retrieved chunk is numbered `[1]`, `[2]`, ... and concatenated into a single context
string. The numbering scheme is what enables inline citations — the model can reference a specific chunk by its number.

### Step 3: Generate with citation instructions

The numbered context and the user's question are passed to GPT-5.6 via the Responses API
with a system prompt that constrains the model to:

- Answer only from the provided context
- Cite sources inline as `[n]` matching the context block numbers
- Say so explicitly if the context does not contain the answer

### Step 4: Return answer and citation map

The answer and a mapping from citation numbers to source URIs are returned together, so a caller can render references however it needs.

## Example output

```
→ request
   model             openai.gpt-5.6-terra
   region            us-east-1
   knowledge_base    78NVB3ZXQV
   query             What are the effects of vessel noise on oyster toadfish?
   retrieval_k       6
   max_output_tokens 1024
   store             False

← retrieval
   chunks returned   6
   top score         0.73

← generation
   Vessel noise has been shown to significantly impact oyster toadfish
   acoustic communication. Studies demonstrate that toadfish modify their
   calling behavior in the presence of boat noise [1], reducing call rates
   and shifting dominant frequencies [3].

REFERENCES
   [1] s3://my-bucket/papers/luczkovich-2016.pdf
   [3] s3://my-bucket/papers/stanley-2017.pdf

← usage
   Input tokens:     4,217
   Output tokens:    89
     of which reasoning: 0
   Total tokens:     4,306
```

## Production considerations

- **Cap output tokens.** The generation call should always set `max_output_tokens`. Without
  it, a verbose answer on a large context can bill far more than you expect.
- **Tune `k` deliberately.** More chunks means more grounding material but also more input
  tokens — and on a large corpus, lower-ranked chunks add noise without adding signal.
  Start with 5–6 and measure citation coverage.
- **Consider hybrid search.** For queries with specific terms (product names, error codes),
  adding `"overrideSearchType": "HYBRID"` improves recall by combining keyword and semantic
  search.
- **Add deduplication.** If your corpus has overlapping documents, multiple chunks from the
  same source inflate the context without adding information. Deduplicate by source URI
  before building context.
- **Consider reranking.** A cross-encoder reranker between retrieve and generate can
  significantly improve precision when `k` is high. Bedrock supports this natively via
  reranking configuration.
- **Handle the "I don't know" case.** The system prompt tells the model to say when context
  is insufficient. In production, detect that response and route to a fallback rather than surfacing it raw.
- **Print Region and model.** Explicit logging prevents silent Region drift across
  environments — the same code running in `us-west-2` might hit a different KB or miss a
  model tier.

## Data handling and security

- **No API key in the code.** Both the Retrieve call (boto3) and the generation call
  (OpenAI provider) use the AWS credential chain.
- **`store=False` on generation**, so AWS retains neither the prompt nor the response.
- **Retrieval is read-only.** The `Retrieve` API does not modify your Knowledge Base or its
  source documents.
- **Context stays in-Region.** Both the retrieval and generation calls execute in the Region you configure, and the retrieved chunks are not sent outside it.
- **The Knowledge Base ID is configuration, not a secret.** It identifies a resource in your account but does not grant access — IAM does.
- **Chunks may contain sensitive content** from your corpus. The script prints them to
  stdout for teaching purposes; a production deployment should treat retrieved text as
  potentially sensitive.

## Limitations and non-goals

- **It does not create a Knowledge Base.** You bring one that already has documents
  ingested. The [Bedrock Knowledge Bases documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) covers creation and ingestion.
- **It does not stream.** The answer arrives in one piece. Add `stream=True` to the
  `responses.create` call for token-by-token delivery — the [streaming recipe](../../01-foundations/05-streaming/) covers the event types.
- **It does not maintain conversation history.** Each call is stateless. Appending prior
  Q&A pairs to the context is straightforward but outside this recipe's scope.
- **It does not evaluate answer quality.** The [scoring recipe](../02-scoring-a-grounded-answer/) covers grounding evaluation.
- **Citation accuracy depends on the model following instructions.** The numbered-context
  pattern is reliable but not guaranteed — production systems should validate that cited numbers exist in the context.

## Clean up

There is nothing to tear down. Retrieval is read-only, generation uses `store=False`, and
no resources are created. Your Knowledge Base and its documents are unaffected.

## Next steps

- [`03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](../01-grounded-regulatory-monitoring/)
  — grounding with Bedrock's native Web Search instead of your own corpus.
- [`03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](../02-scoring-a-grounded-answer/)
  — measuring whether an answer is faithful to its sources.
- [`02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
  — adding a structured output schema so you can programmatically detect "I don't know."
- [`01-foundations/05-streaming/`](../../01-foundations/05-streaming/) — streaming the generation for real-time delivery.
