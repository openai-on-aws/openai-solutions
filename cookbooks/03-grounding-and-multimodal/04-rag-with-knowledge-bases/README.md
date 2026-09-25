---
title: "RAG with Bedrock Knowledge Bases: retrieve then generate with citations"
capabilities: [GRD-04, GRD-03]
primary_capability: GRD-04
industry: —
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
  # The recipe itself
  - bedrock-mantle:CreateInference
  - bedrock:Retrieve
  # utils/create_knowledge_base.py, only if you use it to build the fixture
  - bedrock:CreateKnowledgeBase
  - bedrock:GetKnowledgeBase
  - bedrock:DeleteKnowledgeBase
  - bedrock:ListKnowledgeBases
  - bedrock:CreateDataSource
  - bedrock:ListDataSources
  - bedrock:StartIngestionJob
  - bedrock:GetIngestionJob
  - s3vectors:CreateVectorBucket
  - s3vectors:GetVectorBucket
  - s3vectors:DeleteVectorBucket
  - s3vectors:CreateIndex
  - s3vectors:GetIndex
  - s3vectors:DeleteIndex
  - s3:CreateBucket
  - s3:PutObject
  - s3:ListBucket
  - s3:DeleteObject
  - s3:DeleteBucket
  - iam:CreateRole
  - iam:GetRole
  - iam:PutRolePolicy
  - iam:ListRolePolicies
  - iam:DeleteRolePolicy
  - iam:DeleteRole
  - iam:PassRole
level: intermediate
estimated_cost: low
status: validated
last_validated: 2026-09-25
validated_with:
  python: "3.12"
  openai: "2.53.0"
---
# RAG with Bedrock Knowledge Bases: retrieve then generate with citations

You have documents in a Bedrock Knowledge Base and you want a GPT-5.6 model to answer
questions grounded in that corpus — with inline citations that trace every claim back to a source. Bedrock offers a coupled `RetrieveAndGenerate` API, but you want control: custom
prompting, citation formatting, model choice independent of retrieval, and room to add
reranking or business logic between the two steps.

|                               |                                                                                                                                      |
| :---------------------------- | :----------------------------------------------------------------------------------------------------------------------------------- |
| **What you will learn** | How to separate retrieval (Bedrock Knowledge Bases) from generation (GPT-5.6 via Bedrock Mantle) and produce inline`[n]` citations |
| **Capability**          | Two-step Retrieve-then-Generate with the Responses API                                                                               |
| **Model**               | `openai.gpt-5.6-terra`                                                                                                             |
| **Region**              | `us-east-1`                                                                                                                        |
| **Level**               | Intermediate                                                                                                                         |
| **Cost**                | Low — one retrieval call plus one generation call, capped at 1024 output tokens                                                     |
| **You will need**       | Inference and`bedrock:Retrieve` permission, plus a Knowledge Base — build one with the included helper, or point at your own       |

> **What it does.** Retrieves the top-k chunks from a Knowledge Base, numbers them, passes
> them as context to GPT-5.6 with instructions to cite sources inline, and prints the
> grounded answer with a reference list.

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

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md).
- **A Bedrock Knowledge Base**, and its ID (which looks like `XXXXXXXXXX`). If you do not
  have one, [`utils/create_knowledge_base.py`](utils/create_knowledge_base.py) builds one
  from the documents in `assets/` and prints the ID — see
  [Appendix A](#appendix-a---creating-a-knowledge-base). Creating one needs considerably
  more permission than querying it, which is why the two sets are listed separately in the
  front matter above; if your role only allows inference and `bedrock:Retrieve`, point the
  recipe at a Knowledge Base someone else provisioned.
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
  "How was the Tiltrotor Test Rig tested in the NFAC 40- by 80-Foot Wind Tunnel?"
```

## How it works

### Step 1: Retrieve

The script calls the Bedrock Knowledge Bases `Retrieve` API directly with the user's
query. This returns ranked chunks with relevance scores, source locations (S3 URIs or
web URLs), and any document metadata. When a chunk carries a `source_url` metadata
attribute, the script uses it as the citation source in preference to the S3 URI. You
control `k` (number of results) and can enable hybrid search or metadata filters.

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

The example corpus is a set of public-domain NASA wind-tunnel and aerodynamics
reports (see [Appendix A](#appendix-a---creating-a-knowledge-base) and
`utils/create_knowledge_base.py`). Citations resolve to each report's NTRS record
URL because the documents were ingested with a `source_url` metadata attribute.

**If you swap in your own corpus, check what you are allowed to redistribute.** A
document being publicly downloadable is not the same as being free to commit to a
repository. NASA's own catalogue makes this checkable per document:
`https://ntrs.nasa.gov/api/citations/<id>` returns a `copyright` object whose
`determinationType` is the field that matters, alongside `belongsToContractor` and
`containsIndication`. Reports written by contractors rather than civil servants are
routinely copyrighted even when NASA hosts them.

```
→ request
   model             openai.gpt-5.6-terra
   region            us-east-1
   knowledge_base    XXXXXXXXXX
   query             How much did the acoustic improvement program reduce background noise in the wind tunnel test?
   retrieval_k       12
   max_output_tokens 1024
   store             False

← retrieval
   chunks returned   12
   top score         0.85

← generation
   The program reduced one-third-octave background-noise levels by 8 to 18 dB
   over the frequency range of interest. [5] For the 630 Hz-50 kHz bands
   specifically, the reported average reduction was 13 dB, with a minimum
   reduction of 7 dB at 2 kHz. [1]

REFERENCES
   [1] https://ntrs.nasa.gov/citations/20210017002
   [5] https://ntrs.nasa.gov/citations/20210017002

← usage
   Input tokens:     3,560
   Output tokens:    77
     of which reasoning: 0
   Total tokens:     3,637
```

## Production considerations

- **Cap output tokens.** The generation call should always set `max_output_tokens`. Without
  it, a verbose answer on a large context can bill more than you expect.
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

- **The retrieval recipe does not create a Knowledge Base.** It expects one that already
  has documents ingested; [Appendix A](#appendix-a---creating-a-knowledge-base) covers
  creating one (including the `utils/create_knowledge_base.py` helper), and the
  [Bedrock Knowledge Bases documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
  covers creation and ingestion in general.
- **It does not stream.** The answer arrives in one piece. Add `stream=True` to the
  `responses.create` call for token-by-token delivery — the [streaming recipe](../../01-foundations/05-streaming/) covers the event types.
- **It does not maintain conversation history.** Each call is stateless. Appending prior
  Q&A pairs to the context is straightforward but outside this recipe's scope.
- **It does not evaluate answer quality.** The [scoring recipe](../02-scoring-a-grounded-answer/) covers grounding evaluation.
- **Citation accuracy depends on the model following instructions.** The numbered-context
  pattern is reliable but not guaranteed — production systems should validate that cited numbers exist in the context.

## Clean up

The recipe itself has nothing to tear down: retrieval is read-only, generation uses
`store=False`, and it creates no resources — your Knowledge Base and its documents are
unaffected. If you provisioned a Knowledge Base with the helper in
[Appendix A](#appendix-a---creating-a-knowledge-base), delete those resources with its
`--teardown` flag.

## Next steps

- [`03-grounding-and-multimodal/01-grounded-regulatory-monitoring/`](../01-grounded-regulatory-monitoring/)
  — grounding with Bedrock's native Web Search instead of your own corpus.
- [`03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](../02-scoring-a-grounded-answer/)
  — measuring whether an answer is faithful to its sources.
- [`02-reasoning-and-output/01-structured-claims-intake/`](../../02-reasoning-and-output/01-structured-claims-intake/)
  — adding a structured output schema so you can programmatically detect "I don't know."
- [`01-foundations/05-streaming/`](../../01-foundations/05-streaming/) — streaming the generation for real-time delivery.

## Appendix A - Creating a Knowledge Base

Start with a set of documents, either in a zip file or in an S3 bucket. You then have
several options: the included helper script, the console, the API, or Codex. The [Bedrock Knowledge Bases creation documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html) describes how to manually configure a knowledge base using both the console and the API.

### Option 1: The `create_knowledge_base.py` helper (recommended)

This recipe ships a boto3 script, [`utils/create_knowledge_base.py`](utils/create_knowledge_base.py),
that provisions a complete knowledge base from a directory of documents, end to end,
using **Amazon S3 Vectors** as the vector store (the lowest-cost option, with no cluster
to manage). In one command it:

1. Scans the source directory for documents (`.txt`; HTML and other
   non-document files are skipped).
2. Uploads them to an S3 bucket, each with a `.metadata.json` sidecar carrying its public
   `source_url` so retrieval can cite the real link rather than the S3 URI.
3. Creates the S3 Vectors bucket and index.
4. Creates a least-privilege IAM service role for the knowledge base.
5. Creates the knowledge base (Titan embed text v2) and an S3 data source, then runs
   ingestion.

The example corpus is a set of public-domain NASA wind-tunnel and aerodynamics reports.
The documents live in this recipe's `assets/` folder (plain-text extractions), and
[`assets/NASA_Wind_Tunnel_Reports_index.html`](assets/NASA_Wind_Tunnel_Reports_index.html)
lists each report with a link to its NTRS record.

```bash
# Create everything and ingest. Prints KNOWLEDGE_BASE_ID at the end.
uv run --env-file .env python \
  03-grounding-and-multimodal/04-rag-with-knowledge-bases/utils/create_knowledge_base.py
```

Set the printed `KNOWLEDGE_BASE_ID` in your `.env`, then run the retrieval script above.

Every step is idempotent — re-running reuses resources that already exist by name, so a
run interrupted partway (for example a creation that takes longer than the wait timeout)
simply resumes. Configuration is env-driven; the useful knobs are:

| Variable               | Purpose                                                               | Default                          |
| :--------------------- | :-------------------------------------------------------------------- | :------------------------------- |
| `KB_NAME`            | Knowledge base name (also the prefix for the bucket, index, and role) | `nasa-windtunnel-kb`           |
| `KB_SOURCE_DIR`      | Directory of documents to ingest                                      | the recipe's`assets/`          |
| `KB_EMBED_MODEL`     | Embedding model id                                                    | `amazon.titan-embed-text-v2:0` |
| `KB_EMBED_DIMENSION` | Embedding dimension (must match the index)                            | `1024`                         |
| `KB_ACTIVE_TIMEOUT`  | Seconds to wait for the KB to become`ACTIVE`                        | `600`                          |

When you are finished, tear down everything the script created — the knowledge base, S3
Vectors store, IAM role, and documents bucket — with the `--teardown` flag:

```bash
uv run --env-file .env python \
  03-grounding-and-multimodal/04-rag-with-knowledge-bases/utils/create_knowledge_base.py --teardown
```

Teardown is scoped to the resources named after `KB_NAME`, is safe to run repeatedly, and
ignores anything that is already gone. Because S3 Vectors bills for stored vectors and the
documents bucket for stored objects, run teardown when you no longer need the knowledge
base to avoid ongoing charges. Running the script requires broader permissions than
retrieval alone: Bedrock, S3, S3 Vectors, and IAM role creation.

### Option 2: Console or API

The [Bedrock Knowledge Bases creation documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html)
walks through the console's guided flow (including "Quick create" for an S3 Vectors store)
and the equivalent API calls.

### Option 3: Codex

It's also possible to prompt Codex to create the knowledge base on its own, if we have the AWS MCP server configured. The more specific the prompt, the less it has to guess. Here is a sample prompt that spells out the same choices the helper script makes:

> Using the documentation as necessary
> ([docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html)),
> use the AWS MCP tools to create an Amazon Bedrock knowledge base from the attached set of
> documents, in region `us-east-1`, with these settings:
>
> - **Name:** `nasa-windtunnel-kb`
> - **Vector store:** Amazon S3 Vectors (quick-create a new S3 vector bucket and index).
>   Mark `AMAZON_BEDROCK_TEXT` as a non-filterable metadata key so chunk text does not hit
>   the 2 KB filterable-metadata limit.
> - **Embedding model:** `amazon.titan-embed-text-v2:0` with an embedding dimension of
>   `1024` (the index dimension must match).
> - **Data source:** the attached documents in S3. For each document, add a
>   `<name>.metadata.json` sidecar with a `source_url` attribute (set `includeForEmbedding`
>   to false) holding the document's public URL, so retrieval can cite the real source
>   instead of the S3 URI.
> - **IAM:** create a least-privilege service role the knowledge base can assume (invoke the
>   embedding model, read the documents bucket, and write to the S3 vector store).
>
> After creating it, start an ingestion job, wait for it to complete, and print the
> knowledge base ID. Ask me before making any choice not specified above.

Attach the documents, or a link to the S3 bucket where the documents are stored. Refer to [this article](https://builder.aws.com/content/3FY7OE1GSTqbER63FvrJZbNrxA5/deploying-openai-agents-to-bedrock-agentcore-runtime-with-codex-cli) for help configuring the AWS MCP server in Codex.
