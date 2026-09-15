"""RAG with Bedrock Knowledge Bases: retrieve then generate with citations.

Two-step Retrieve-then-Generate pattern that separates retrieval (Bedrock
Knowledge Bases vector search) from generation (GPT-5.6 via Bedrock Mantle).
The model answers only from retrieved context and cites sources inline as [n].

Run it from the cookbooks/ directory:

    uv run python \
      03-grounding-and-multimodal/04-rag-with-knowledge-bases/python/rag_with_knowledge_bases.py

Pass a custom query as a positional argument:

    uv run python \
      03-grounding-and-multimodal/04-rag-with-knowledge-bases/python/rag_with_knowledge_bases.py \
      "How was the Tiltrotor Test Rig tested in the Wind Tunnel?"

See README.md for prerequisites and the permissions this needs.
"""

import os
import re
import sys

import boto3
from openai import OpenAI
from openai.providers import bedrock

# --- Configuration ----------------------------------------------------------
# All tunables come from environment variables with sensible defaults.
# KNOWLEDGE_BASE_ID has no default — you must set it.

REGION = os.environ.get("AWS_REGION", "us-east-1")


def _require_knowledge_base_id() -> str:
    """Return KNOWLEDGE_BASE_ID, or exit listing the account's knowledge bases.

    When the variable is unset we can't retrieve anything, so instead of a bare
    KeyError we list the knowledge bases in this Region (via the bedrock-agent
    control plane) to help the user pick one and set it.
    """
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if kb_id:
        return kb_id

    lines = ["KNOWLEDGE_BASE_ID is not set. Set it to one of the knowledge bases"]
    lines.append(f"available in {REGION}:")
    try:
        control = boto3.client("bedrock-agent", region_name=REGION)
        found = False
        for page in control.get_paginator("list_knowledge_bases").paginate():
            for kb in page["knowledgeBaseSummaries"]:
                found = True
                lines.append(
                    f"  {kb['knowledgeBaseId']}  {kb['name']}  ({kb['status']})"
                )
        if not found:
            lines.append(
                "  (none found — create one with utils/create_knowledge_base.py)"
            )
    except Exception as err:  # noqa: BLE001 - best-effort hint, never mask the real cause
        lines.append(f"  (could not list knowledge bases: {err})")

    lines.append("")
    lines.append("Then re-run with, e.g.:  KNOWLEDGE_BASE_ID=XXXXXXXXXX uv run ...")
    sys.exit("\n".join(lines))


KNOWLEDGE_BASE_ID = _require_knowledge_base_id()
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")
RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "12"))
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "1024"))

DEFAULT_QUERY = (
    "How much did the acoustic improvement program reduce background noise "
    "in the wind tunnel test?"
)

# --- Clients ----------------------------------------------------------------

# Bedrock Agent Runtime for the Retrieve API (vector search).
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=REGION)

# OpenAI client with the Bedrock provider — no API key, no base URL.
# The provider derives the regional endpoint and signs with SigV4.
oai = OpenAI(provider=bedrock(region=REGION))


# --- Step 1: Retrieve -------------------------------------------------------

def retrieve(query: str, k: int = RETRIEVAL_K) -> list[dict]:
    """Pull the most relevant chunks from the Bedrock Knowledge Base.

    Returns a list of dicts with text, score, and source URI for each chunk.
    """
    resp = bedrock_agent.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": k}
        },
    )

    hits = []
    for result in resp["retrievalResults"]:
        # Prefer the source_url metadata attribute (attached at ingestion via a
        # .metadata.json sidecar — see utils/create_knowledge_base.py) so
        # citations point at the real document URL. Fall back to the physical
        # location (S3, web, Confluence, ...) when no source_url is present.
        source_url = result.get("metadata", {}).get("source_url")
        location = result.get("location", {})
        source = (
            source_url
            or location.get("s3Location", {}).get("uri")
            or location.get("webLocation", {}).get("url")
            or "unknown"
        )
        hits.append({
            "text": result["content"]["text"],
            "score": result.get("score"),
            "source": source,
        })

    return hits


# --- Step 2: Build numbered context -----------------------------------------

def build_context(hits: list[dict]) -> str:
    """Number each chunk so the model can cite [1], [2], ..."""
    blocks = []
    for i, hit in enumerate(hits, 1):
        blocks.append(f"[{i}] (source: {hit['source']})\n{hit['text']}")
    return "\n\n".join(blocks)


# --- Step 3: Generate -------------------------------------------------------

SYSTEM_PROMPT = (
    "Answer ONLY from the numbered context below. "
    "Cite sources inline as [n] matching the context block numbers. "
    "If the context does not contain enough information to answer, say so explicitly."
)


def generate(query: str, hits: list[dict]) -> object:
    """GPT-5.6 generates a grounded answer via Bedrock Mantle.

    Returns the full response object so the caller can inspect usage.
    """
    context = build_context(hits)

    response = oai.responses.create(
        model=MODEL_ID,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
    )

    return response


# --- Step 4: Orchestrate ----------------------------------------------------

def rag(query: str) -> dict:
    """Full RAG pipeline: retrieve, generate, return answer + citations."""
    # Print the request before making it — every recipe here does this.
    print("→ request")
    print(f"   model             {MODEL_ID}")
    print(f"   region            {REGION}")
    print(f"   knowledge_base    {KNOWLEDGE_BASE_ID}")
    print(f"   query             {query}")
    print(f"   retrieval_k       {RETRIEVAL_K}")
    print(f"   max_output_tokens {MAX_OUTPUT_TOKENS}")
    print("   store             False")
    print()

    # Retrieve
    hits = retrieve(query)

    print("← retrieval")
    print(f"   chunks returned   {len(hits)}")
    if hits and hits[0].get("score") is not None:
        print(f"   top score         {hits[0]['score']:.2f}")
    print()

    # Generate
    response = generate(query, hits)

    print("← generation")
    print(response.output_text)
    print()

    # Build citation map from the chunks that were actually cited
    cited_nums = set(int(m) for m in re.findall(r"\[(\d+)\]", response.output_text))
    citations = {}
    for i, hit in enumerate(hits, 1):
        if i in cited_nums:
            citations[i] = hit["source"]

    if citations:
        print("REFERENCES")
        for n, src in sorted(citations.items()):
            print(f"   [{n}] {src}")
        print()

    # Print usage — always, so you know what it cost.
    usage = response.usage
    print("← usage")
    print(f"   Input tokens:     {usage.input_tokens:,}")
    print(f"   Output tokens:    {usage.output_tokens:,}")
    print(f"     of which reasoning: {usage.output_tokens_details.reasoning_tokens:,}")
    print(f"   Total tokens:     {usage.total_tokens:,}")

    return {
        "answer": response.output_text,
        "citations": citations,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "reasoning_tokens": usage.output_tokens_details.reasoning_tokens,
            "total_tokens": usage.total_tokens,
        },
    }


# --- Main -------------------------------------------------------------------

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    rag(query)
