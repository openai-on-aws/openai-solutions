"""Scoped text retrieval for an existing Bedrock Knowledge Base; no generation.

Uses the normal AWS credential chain and owns each blocking SDK client through
cleanup. This does not create a knowledge base, choose an embedding model, ingest
documents, authenticate users, or execute retrieved links/instructions.
"""
import asyncio
from dataclasses import dataclass
import hashlib
import inspect
import json
import math
import re
import threading
import time
from urllib.parse import urlsplit


class RetrievalError(RuntimeError):
    """Diagnostic without query, document, token or provider-error payloads."""


@dataclass(frozen=True)
class KnowledgeBaseScope:
    arn: str
    metadata: tuple[tuple[str, str], ...] = ()
    shared_corpus: bool = False

    def __post_init__(self):
        if not isinstance(self.arn, str) or not re.fullmatch(
                r"arn:aws(?:-us-gov)?:bedrock:[a-z0-9-]{1,20}:[0-9]{12}:knowledge-base/[A-Za-z0-9]{10}", self.arn):
            raise ValueError("An explicit supported knowledge-base ARN is required")
        if type(self.shared_corpus) is not bool or type(self.metadata) is not tuple or len(self.metadata) > 8:
            raise ValueError("Invalid retrieval scope")
        if not self.metadata and not self.shared_corpus:
            raise ValueError("Bind metadata constraints or explicitly authorize a shared corpus")
        keys = set()
        for pair in self.metadata:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError("Metadata constraints must be immutable key/value pairs")
            key, value = pair
            if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key)
                    or key in keys or not isinstance(value, str) or not 1 <= len(value) <= 256):
                raise ValueError("Invalid metadata constraint")
            keys.add(key)

    @property
    def region(self):
        return self.arn.split(":")[3]


class KnowledgeBaseSearch:
    def __init__(self, scope, *, authorize_query, client_factory=None,
                 max_results=8, max_pages=3, max_output_bytes=49152, timeout_seconds=60):
        if not isinstance(scope, KnowledgeBaseScope) or not inspect.iscoroutinefunction(authorize_query):
            raise ValueError("An immutable scope and async query authorization are required")
        if (type(max_results) is not int or not 1 <= max_results <= 20
                or type(max_pages) is not int or not 1 <= max_pages <= 10
                or type(max_output_bytes) is not int or not 1024 <= max_output_bytes <= 49152
                or type(timeout_seconds) not in {int, float} or not 0 < timeout_seconds <= 120):
            raise ValueError("Invalid retrieval limits")
        self.scope, self._authorize = scope, authorize_query
        self._client_factory = client_factory
        self.max_results, self.max_pages = max_results, max_pages
        self.max_output_bytes, self.timeout_seconds = max_output_bytes, timeout_seconds

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import boto3
        from botocore.config import Config
        return boto3.session.Session().client("bedrock-agent-runtime", region_name=self.scope.region,
            config=Config(connect_timeout=5, read_timeout=30, retries={"mode": "standard", "total_max_attempts": 1}))

    def _request(self, query):
        vector = {"numberOfResults": self.max_results, "overrideSearchType": "SEMANTIC"}
        filters = [{"equals": {"key": key, "value": value}} for key, value in self.scope.metadata]
        if filters:
            vector["filter"] = filters[0] if len(filters) == 1 else {"andAll": filters}
        return {"knowledgeBaseId": self.scope.arn, "retrievalQuery": {"text": query},
                "retrievalConfiguration": {"vectorSearchConfiguration": vector}}

    def _match(self, item):
        if not isinstance(item, dict):
            raise RetrievalError("Malformed knowledge-base result")
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in self.scope.metadata):
            raise RetrievalError("Retrieved document did not match the authorized metadata scope")
        content, location = item.get("content"), item.get("location")
        if not isinstance(content, dict) or content.get("type", "TEXT") != "TEXT" or not isinstance(content.get("text"), str):
            raise RetrievalError("Only text knowledge-base results are supported")
        text = content["text"]
        if not text.strip() or len(text.encode()) > 32768 or not isinstance(location, dict):
            raise RetrievalError("Missing or oversized retrieved text/citation")
        source_type = location.get("type")
        fields = {"S3": ("s3Location", "uri", "s3"), "WEB": ("webLocation", "url", "https")}
        if source_type not in fields:
            raise RetrievalError("This text adapter requires an S3 or HTTPS web citation")
        container, key, scheme = fields[source_type]
        source = location.get(container, {}).get(key)
        if not isinstance(source, str) or len(source) > 2048:
            raise RetrievalError("Invalid retrieved citation")
        parsed = urlsplit(source)
        if parsed.scheme != scheme or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RetrievalError("Invalid retrieved citation")
        score = item.get("score")
        if type(score) not in {int, float} or not math.isfinite(score):
            raise RetrievalError("Invalid retrieval score")
        citation = hashlib.sha256((source + "\0" + text).encode()).hexdigest()
        return {"citation_id": citation, "text": text, "source": source, "score": score}

    def _retrieve(self, query, stop, deadline):
        if stop.is_set() or time.monotonic() >= deadline:
            raise RetrievalError("Retrieval deadline elapsed before SDK acquisition")
        request, results, ids, tokens = self._request(query), [], set(), set()
        client = self._client()
        truncated = False
        try:
            for page in range(self.max_pages):
                if stop.is_set() or time.monotonic() >= deadline:
                    raise RetrievalError("Retrieval cancelled or expired")
                response = client.retrieve(**request)
                if stop.is_set() or time.monotonic() >= deadline:
                    raise RetrievalError("Retrieval cancelled or expired")
                if not isinstance(response, dict) or response.get("guardrailAction", "NONE") != "NONE":
                    raise RetrievalError("Retrieval was blocked or malformed")
                batch = response.get("retrievalResults")
                if not isinstance(batch, list) or len(batch) > 100:
                    raise RetrievalError("Malformed retrieval result collection")
                for item in batch:
                    match = self._match(item)
                    if match["citation_id"] in ids:
                        continue
                    ids.add(match["citation_id"])
                    if len(results) == self.max_results:
                        truncated = True
                    else:
                        results.append(match)
                token = response.get("nextToken")
                if token is not None:
                    if not isinstance(token, str) or not re.fullmatch(r"\S{1,2048}", token) or token in tokens:
                        raise RetrievalError("Invalid or repeated retrieval pagination token")
                    tokens.add(token)
                truncated = truncated or bool(token and (len(results) == self.max_results or page == self.max_pages - 1))
                result = {"matches": results, "truncated": truncated, "status": "matches" if results else "no_matches"}
                if len(json.dumps(result, ensure_ascii=False).encode()) > self.max_output_bytes:
                    raise RetrievalError("Retrieved context exceeds its configured limit")
                if not token or truncated:
                    return result
                request["nextToken"] = token
            raise RetrievalError("Retrieval finished without a result")
        finally:
            client.close()

    async def search(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 20000:
            raise ValueError("A nonempty text retrieval query of at most 20000 characters is required")
        task, stop = None, threading.Event()
        deadline = time.monotonic() + self.timeout_seconds
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if await self._authorize(self.scope, query) is not True:
                    raise RetrievalError("Knowledge-base query was not authorized")
                task = asyncio.create_task(asyncio.to_thread(self._retrieve, query, stop, deadline))
                return await asyncio.shield(task)
        except BaseException as error:
            stop.set()
            if task is not None:
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if task.done() and not task.cancelled():
                    task.exception()
            if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(error, RetrievalError):
                raise
            if isinstance(error, TimeoutError):
                raise RetrievalError("Knowledge-base retrieval timed out after owned cleanup") from None
            raise RetrievalError("Knowledge-base retrieval failed") from None
