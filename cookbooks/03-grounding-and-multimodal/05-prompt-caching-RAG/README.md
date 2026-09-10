---
title: "Cache-friendly RAG with a frozen-layer working set"
capabilities: [GRD-03, GRD-04, EFF-02, EFF-01]
primary_capability: GRD-03
industry: research
industry_scenario: >
  A research team asks a sequence of related questions against a Bedrock Knowledge Base.
  Many retrieved chunks recur, but ordinary top-k prompt construction changes their order
  and prevents reliable prefix reuse. The team wants a layered working set that holds a
  stable, cacheable prefix so most of each request's input is served from cache without
  weakening grounding.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock:Retrieve
level: advanced
estimated_cost: medium
status: validated
last_validated: 2026-09-09
validated_with:
  python: "3.12"
  openai: "2.53.0"
---
# Cache-friendly RAG with a frozen-layer working set

Traditional RAG inserts the current top-k chunk text into every model request. Even when
successive queries retrieve many of the same chunks, changes in selection or rank change
the prompt prefix and defeat prompt-cache reuse. The apparent fix — accumulate retrieved
chunks into one growing prefix with a single cache breakpoint at its tail — does not work because every turn that appends a chunk moves the breakpoint, produces a novel prefix,
and writes cold. Measured over four queries, that shape read **0%** from cache.

This recipe uses the shape that does work: split the working set into a **frozen layer**
that changes only in batches and a **pending layer** that absorbs new chunks, with a cache
breakpoint after each. The frozen layer stays byte-identical across the turns between
batch commits, so its breakpoint reads on every one of those turns while only the pending
layer and the question are processed fresh.

|                               |                                                                                                                             |
| :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------- |
| **What you will learn** | How layered cache breakpoints keep a stable RAG prefix readable while the working set grows                                 |
| **Capability**          | Two-step Knowledge Base retrieval, stable chunk IDs, layered explicit prompt caching, and citation validation               |
| **Model**               | `openai.gpt-5.6-terra`                                                                                                    |
| **Region**              | `us-east-1`                                                                                                               |
| **Level**               | Advanced                                                                                                                    |
| **Cost**                | Medium — one retrieval call and one generation call per query (four by default); output is capped at 1,024 tokens per turn |
| **You will need**       | An ingested Bedrock Knowledge Base, inference permission, and`bedrock:Retrieve` permission                                |

> **What it does.** Runs several queries in one process, retrieves top-k chunks per query,
> keeps them in a frozen layer (grown in batches) and a pending layer, and reports the
> cache reads and writes returned by GPT-5.6. **What it creates.** No AWS resources. The
> in-memory working set disappears when the script exits, and prompt-cache entries expire
> automatically.

## The pattern

Two explicit breakpoints in one developer message, plus an uncached suffix:

```text
┌──────────────────────── LAYER 1 (breakpoint 1) ──────────────────┐
│ Stable grounding instructions                                    │
│ frozen chunk:A  frozen chunk:B  frozen chunk:C                    │  ← grows only in batches
└──────────────────────────── breakpoint 1 ─────────────────────────┘
┌──────────────────────── LAYER 2 (breakpoint 2) ──────────────────┐
│ pending chunk:D  pending chunk:E                                  │  ← new chunks land here
└──────────────────────────── breakpoint 2 ─────────────────────────┘
┌──────────────────────── DYNAMIC SUFFIX (no breakpoint) ──────────┐
│ Current retrieval ranking: D, C, E                               │  ← changes every turn
│ Question: ...                                                     │
└───────────────────────────────────────────────────────────────────┘
```

Breakpoints are cumulative from the start of the prompt: breakpoint 1 caches instructions
plus the frozen chunks, and breakpoint 2 caches all of that plus the pending chunks.
Because breakpoint 1's prefix does not change between batch commits, it reads even on turns
where new chunks arrive in the pending layer — a later change cannot invalidate the stable
head that precedes it.

New chunks accumulate in the pending layer. When the pending count reaches `FREEZE_BATCH`,
a whole batch is promoted into the frozen layer. That promotion is the only event that
changes the frozen bytes, so it is the only event that forces a cold write of layer 1.

## What the measurement shows

Four queries against a Knowledge Base of oyster-toadfish papers, `FREEZE_BATCH=6`, with the
fourth query repeating the first to force a turn that appends nothing:

| Turn | appended          | frozen layer | read from cache | written to cache | what happened                                   |
| :--- | :---------------- | :----------- | :-------------- | :--------------- | :---------------------------------------------- |
| 1    | 6 → frozen       | new (cold)   | 0               | 1,604            | first write of the frozen layer                 |
| 2    | 5 → pending      | unchanged    | **1,591** | 1,695            | frozen layer read; pending layer wrote          |
| 3    | 4, batch promoted | changed      | 0               | 4,508            | promotion enlarged the frozen layer, cold write |
| 4    | 0                 | unchanged    | **4,508** | 0                | nothing new, entire prefix read                 |

Session total: **41% of input served from cache**, against **0%** for the single-tail-
breakpoint shape on the same workload.

Read the pattern, not the exact digits. Two facts generalize:

- **A frozen layer reads on every turn its bytes do not change.** Turn 2 appended five
  chunks and still read the frozen layer, because those chunks went into the pending layer
  *after* breakpoint 1.
- **Each batch promotion costs one cold write of the (now larger) frozen layer,** repaid by
  reads on the turns until the next promotion. `FREEZE_BATCH` tunes how often you pay that
  write against how much uncached pending text each turn carries.

Do not infer a hit from a successful request or the presence of a breakpoint. A hit is
`cached_tokens > 0`. Current behavior and constraints are documented in
[Prompt caching for faster model inference](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html).

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md).
- **An existing Bedrock Knowledge Base** with documents already ingested. You need its
  Knowledge Base ID, which looks like `XXXXXXXXXX`.
- **`bedrock:Retrieve` permission** on that Knowledge Base, in addition to the inference
  permissions used by the other recipes.
- **Several related questions.** Overlapping retrieval results are what let the frozen layer
  stabilize and read.
- **A frozen layer of at least 1,024 tokens.** Each breakpoint has its own GPT-5.6 minimum;
  below it that layer caches nothing. The request still succeeds, and its counters stay
  zero.

The base environment already includes `boto3` and `openai[bedrock]`; no additional
dependency group is required.

## Configuration

Set these values in `cookbooks/.env` or export them in your shell:

| Variable              | Default                  | Purpose                                                 |
| :-------------------- | :----------------------- | :------------------------------------------------------ |
| `KNOWLEDGE_BASE_ID` | required                 | Knowledge Base queried by`Retrieve`                   |
| `AWS_REGION`        | `us-east-1`            | Region for retrieval and generation                     |
| `MODEL_ID`          | `openai.gpt-5.6-terra` | GPT-5.6 model used for generation and caching           |
| `RETRIEVAL_K`       | `6`                    | Results retrieved on each turn                          |
| `MAX_OUTPUT_TOKENS` | `1024`                 | Per-turn output ceiling                                 |
| `FREEZE_BATCH`      | `6`                    | Pending chunks promoted into the frozen layer per batch |
| `PROMPT_CACHE_KEY`  | `kb-frozen-layer-v1`   | Stable name and version of this prefix design           |
| `WORKING_SET_SCOPE` | `local-demo`           | Stable security/session scope included in the cache key |
| `CORPUS_VERSION`    | `v1`                   | Corpus snapshot/version included in the cache key       |

`FREEZE_BATCH` is the central tuning knob. A larger batch means the frozen layer changes
less often — fewer cold writes, longer read streaks — but each turn before a promotion
carries more uncached pending text. A smaller batch commits sooner and keeps the pending
layer small, at the cost of more frequent frozen-layer writes.

`WORKING_SET_SCOPE` must not vary per request. Change it when users, tenants, metadata
filters, or authorization boundaries must not share a working-set lineage. Change
`CORPUS_VERSION` when documents are re-ingested or replaced. Both feed the frozen cache key.

## Run it

From the `cookbooks/` directory:

```bash
uv sync
cp .env.example .env   # set KNOWLEDGE_BASE_ID and AWS_REGION

uv run --env-file .env python \
  03-grounding-and-multimodal/05-prompt-caching-RAG/python/frozen_layer_rag.py
```

The default questions match the marine-research example used by the adjacent Knowledge
Bases recipe. For another corpus, pass related questions as separate quoted arguments:

```bash
uv run --env-file .env python \
  03-grounding-and-multimodal/05-prompt-caching-RAG/python/frozen_layer_rag.py \
  "How much charging current can the outboard produce?" \
  "What are the rectifier and regulator specifications?" \
  "Which components affect battery charging?"
```

All questions must run in the same process. Starting the script again creates a new
in-memory working set, even if the cache-key settings are unchanged.

## How it works

### Step 1: Retrieve for every question

The script uses the Bedrock Agent Runtime `Retrieve` API rather than
`RetrieveAndGenerate`. This leaves generation, prompt shape, caching, and citation handling
under application control.

Each result retains its text, score, source location, and a short deterministic label.
Results without text are skipped.

### Step 2: Derive stable chunk IDs

A chunk ID is the first 16 hexadecimal characters of a SHA-256 digest over:

```text
canonical JSON representation of the source location + newline + exact chunk text
```

Source URI alone is not enough because one source document normally produces many chunks.
Including exact text means a changed chunk gets a new ID rather than silently mutating an
existing entry — the byte-stability the frozen layer depends on. The full digest is
retained in memory to detect an improbable truncated-ID collision. This is also why the
recipe does not key on `x-amz-bedrock-kb-chunk-id`: that identifier is not guaranteed to
track chunk content, so a re-ingested document could leave stale bytes under an unchanged
ID and silently break a cached prefix.

### Step 3: Layer the working set

`LayeredWorkingSet` keeps two lists. On each turn it:

1. deduplicates the current results by stable ID;
2. adds any unseen chunk to the **pending** list, in first-seen order;
3. once pending reaches `FREEZE_BATCH`, promotes a whole batch into the **frozen** list; and
4. bumps a `frozen_generation` counter — carried in the cache key — only when the frozen
   bytes actually change.

Nothing already serialized is ever reordered or rewritten. That is what makes both cached
layers eligible for reads.

### Step 4: Two breakpoints, ranking after both

The developer message holds two `input_text` parts, each ending in:

```python
"prompt_cache_breakpoint": {"mode": "explicit"}
```

The first part is instructions plus the frozen chunks; the second is the pending chunks.
The user message follows both breakpoints and carries only the current ranked IDs,
retrieval scores, labels, and question. The request enables explicit mode with a `30m` TTL,
uses the frozen cache key, caps output, uses no reasoning tokens, and sets `store=False`.

### Step 5: Constrain and validate citations

The model is told to use only IDs returned by the current retrieval, even though older
chunks remain visible in the frozen and pending layers. Citations use the form
`[chunk:0123456789abcdef]`.

After generation, the script resolves only citations that appear in the current result set.
A syntactically valid ID from an earlier turn is rejected and printed under `CITATION VALIDATION`. This keeps the cache optimization from silently broadening the evidence set
beyond the current retrieval policy.

### Step 6: Measure cache behavior

Every response prints:

```text
Input tokens       all input tokens in the request
Read from cache    usage.input_tokens_details.cached_tokens
Written to cache   usage.input_tokens_details.cache_write_tokens
New input          input - cached - written
```

The final session summary aggregates those counts. Worthwhile comparisons against the same
Knowledge Base:

1. a turn that appends nothing (expect a full read of both layers);
2. a turn that adds chunks to pending without a promotion (expect a frozen-layer read);
3. a turn that triggers a batch promotion (expect a cold frozen write); and
4. a larger and smaller `FREEZE_BATCH`, to see the write frequency move.

## Example output shape

Counts and IDs depend on your Knowledge Base; this is the structure to inspect, not a
promised measurement:

```text
TURN 2
→ request
   query               How do calling frequencies change near boat noise?
   freeze_batch        6

← retrieval and working set
   chunks returned     6
   chunks appended     5
   promoted to frozen  0
   frozen chunks       6
   pending chunks      5
   frozen cache key    kb-frozen-layer-v1-254fd49f7815-f2

← generation
   Oyster toadfish generally reduce how often they call ...
   [chunk:d1b9bbb41e1f63f7]

REFERENCES
   [chunk:d1b9bbb41e1f63f7] s3://example-bucket/papers/study.pdf

← usage
   Input tokens:       <measured>
   Read from cache:    <measured, ~= turn 1 frozen write>
   Written to cache:   <measured, pending layer>
   New input:          <measured, the suffix>
```

## Production considerations

- **Benchmark against ordinary top-k RAG.** Compare total standard, cache-write, and
  cache-read input charges, not just cache-read percentage. A layered prefix sends more
  historical text; it wins only when reads outweigh the batch writes.
- **Tune `FREEZE_BATCH` to your query stream.** Frequent revisiting of the same chunks
  favors a larger batch and long read streaks. Highly diverse queries keep promoting new
  batches, and the pattern degrades toward plain RAG.
- **Use real token accounting.** Enforce the model tokenizer and a context budget across
  both layers plus the suffix and output, rather than assuming the working set stays small.
- **Serialize updates per working set.** Concurrent turns can promote different batches or
  order pending chunks differently and fragment the cache. Use a lock or optimistic version
  check around update plus request construction.
- **Reset on corpus or authorization changes.** Never carry cached chunks across users or
  filters with different document access. Query-time filtering cannot remove text already in
  a cached layer. Change `WORKING_SET_SCOPE` or `CORPUS_VERSION` to start a fresh lineage.
- **Evaluate long-range pointer following.** Citation precision and answer quality can fall
  as relevant chunks sit farther from the question. Measure quality by working-set size, not
  only token cost.
- **Keep both layers deterministic.** Timestamps, request IDs, unstable set iteration,
  reordered metadata, or whitespace changes before a breakpoint reduce reuse.
- **Measure at least two calls.** The first turn writes cold; only a later turn can
  demonstrate a read.

## Data handling and security

- **No API key is embedded.** Both boto3 retrieval and the OpenAI Bedrock provider use the
  AWS credential chain.
- **`store=False` disables response storage, not prompt caching.** Both cached layers can
  include retrieved document text and are retained separately for the configured cache TTL.
  Include that path in security and data-retention reviews.
- **Retrieved text is untrusted.** The developer instructions delimit it as evidence and
  explicitly say not to follow instructions found inside chunks. This reduces prompt
  injection risk but does not replace application-layer content controls.
- **The cache key is a security boundary.** `WORKING_SET_SCOPE`, Knowledge Base ID, corpus
  version, and frozen generation all contribute to it. Do not use the default scope for a
  multi-user production service.
- **Retrieval is read-only.** Neither the script nor prompt caching modifies the Knowledge
  Base or source documents.
- **Context stays in the configured Region.** Retrieval and generation clients use the same
  `AWS_REGION` value.

## Limitations and non-goals

- **The working set is process-local.** It is not shared across hosts and is not restored
  after restart. A production state store needs deterministic ordering and concurrency
  control.
- **The frozen/pending split is size-agnostic.** Promotion is by chunk count, not tokens;
  production code should budget real tokens per layer.
- **Savings are workload-dependent.** The 41% figure above is one query stream on one
  corpus. A stream with little chunk overlap will promote batches continuously and save
  little.
- **Only text chunks are loaded.** Non-text Knowledge Base results are skipped.
- **Current-result-only evidence is intentional.** The original idea allows older chunks
  when relevant; this implementation chooses the stricter policy so retrieval remains the
  authority for each answer.
- **Citation syntax is model-generated.** The script validates IDs but does not prove that
  every factual sentence has a citation. Pair it with a grounding evaluator for that.
- **It does not create or ingest a Knowledge Base.** Use the
  [Bedrock Knowledge Bases documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
  to prepare one first.

## Clean up

There is nothing to tear down. Retrieval is read-only, no resources are created, the local
working set disappears at process exit, and prompt-cache entries expire automatically.
Your Knowledge Base and its documents are unaffected.

## Next steps

- [`03-grounding-and-multimodal/04-rag-with-knowledge-bases/`](../04-rag-with-knowledge-bases/)
  — the simpler stateless retrieve-then-generate baseline to benchmark against.
- [`05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/)
  — explicit prompt-caching mechanics, thresholds, cache keys, and usage counters.
- [`03-grounding-and-multimodal/02-scoring-a-grounded-answer/`](../02-scoring-a-grounded-answer/)
  — evaluate whether long-range chunk references remain faithful to their sources.
