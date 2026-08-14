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
      "How does underwater noise affect marine species?"

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
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]  # no default: must be set
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")
RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "6"))
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "1024"))

DEFAULT_QUERY = (
    "What are the effects of vessel noise on oyster toadfish calling behavior?"
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
        # Source location varies by type (S3, web, Confluence, etc.)
        location = result.get("location", {})
        source = (
            location.get("s3Location", {}).get("uri")
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
    print(f"   store             False")
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
