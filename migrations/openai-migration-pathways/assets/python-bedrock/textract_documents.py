"""Document extraction for registered, version-pinned S3 uploads; not identity proof."""
import asyncio
from dataclasses import dataclass
import hashlib
import inspect
import json
import math
import re
import threading
from types import MappingProxyType


class DocumentAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentReference:
    bucket: str
    key: str
    version: str
    kind: str
    size_bytes: int
    media_type: str
    pages: int = 1
    jurisdiction: str | None = None

    def __post_init__(self):
        if not isinstance(self.bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise ValueError("Invalid registered document bucket")
        if (not isinstance(self.key, str) or not 1 <= len(self.key.encode()) <= 1024
                or any(part in {"", ".", ".."} for part in self.key.split("/"))
                or any(ord(c) < 32 for c in self.key)):
            raise ValueError("Invalid registered document key")
        if not isinstance(self.version, str) or not 1 <= len(self.version) <= 1024 or self.version == "null":
            raise ValueError("An immutable S3 object version is required")
        if self.kind not in {"utility_bill", "drivers_license", "income_statement"}:
            raise ValueError("Unsupported document kind")
        if type(self.size_bytes) is not int or not 1 <= self.size_bytes <= 10_000_000 or self.pages != 1 or type(self.pages) is not int:
            raise ValueError("This synchronous adapter accepts single-page documents up to 10 MB")
        if self.media_type not in {"image/png", "image/jpeg", "application/pdf", "image/tiff"}:
            raise ValueError("Unsupported Textract document format")
        if self.kind == "drivers_license" and (self.jurisdiction != "US" or self.media_type not in {"image/png", "image/jpeg"}):
            raise ValueError("The reviewed AnalyzeID route requires a US license image")

    @property
    def source_id(self):
        return hashlib.sha256(json.dumps([self.bucket, self.key, self.version]).encode()).hexdigest()


QUERIES = {
    "utility_bill": {
        "first_name": "What is the first name of the customer billed?",
        "last_name": "What is the last name of the customer billed?",
        "address": "What is the complete service address for this utility bill?",
    },
    "income_statement": {
        "employee_name": "What is the name of the employee or income recipient?",
        "employer": "What is the name of the employer or income payer?",
        "gross_income": "What is the gross income amount for this pay period?",
        "pay_period": "What is the pay period covered by this statement?",
    },
}


def field(value=None, confidence=0, status=None):
    if value is not None and (not isinstance(value, str) or len(value) > 4096):
        raise DocumentAnalysisError("Invalid extracted field")
    if type(confidence) not in {int, float} or not math.isfinite(confidence) or not 0 <= confidence <= 100:
        raise DocumentAnalysisError("Invalid extraction confidence")
    value = value.strip() if value else None
    return {"type": "string", "valueString": value, "confidence": confidence / 100,
            "status": status or ("missing" if not value else "low_confidence" if confidence < 80 else "extracted")}


class TextractDocuments:
    def __init__(self, region, documents, *, authorize_document, client_factory=None):
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region):
            raise ValueError("Explicit Textract Region is required")
        if not isinstance(documents, dict) or len(documents) > 100:
            raise ValueError("Provide a bounded conversation-owned document registry")
        for handle, document in documents.items():
            if (not isinstance(handle, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", handle)
                    or not isinstance(document, DocumentReference)):
                raise ValueError("Document handles must refer to registered S3 versions, not URLs")
        if not inspect.iscoroutinefunction(authorize_document):
            raise ValueError("Async document authorization is required")
        self.region, self._documents = region, MappingProxyType(dict(documents))
        self._authorize, self._client_factory = authorize_document, client_factory

    def register_document(self, handle, document):
        """Trusted upload-path hook; never expose this operation as a model tool."""
        if (not isinstance(handle, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", handle)
                or not isinstance(document, DocumentReference) or handle in self._documents or len(self._documents) >= 100):
            raise ValueError("Invalid, duplicate or excessive document registration")
        self._documents = MappingProxyType({**self._documents, handle: document})

    def register_documents(self, documents):
        """Publish a validated trusted batch; repeated identical handles are safe."""
        if not isinstance(documents, dict):
            raise ValueError("Document registration requires a mapping")
        merged = dict(self._documents)
        for handle, document in documents.items():
            if (not isinstance(handle, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", handle)
                    or not isinstance(document, DocumentReference)
                    or (handle in merged and merged[handle] != document)):
                raise ValueError("Invalid or changed document registration")
            merged[handle] = document
        if len(merged) > 100:
            raise ValueError("Excessive document registration")
        self._documents = MappingProxyType(merged)

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import boto3
        from botocore.config import Config
        return boto3.session.Session().client("textract", region_name=self.region,
            config=Config(connect_timeout=5, read_timeout=30, retries={"mode": "standard", "total_max_attempts": 1}))

    @staticmethod
    def _queries(response, kind):
        blocks = response.get("Blocks")
        if not isinstance(blocks, list) or len(blocks) > 10000:
            raise DocumentAnalysisError("Invalid Textract block collection")
        index = {}
        for block in blocks:
            if not isinstance(block, dict) or not isinstance(block.get("Id"), str) or block["Id"] in index:
                raise DocumentAnalysisError("Malformed or duplicate Textract block")
            index[block["Id"]] = block
        found = {}
        for block in blocks:
            if block.get("BlockType") != "QUERY":
                continue
            alias = block.get("Query", {}).get("Alias")
            if alias not in QUERIES[kind] or alias in found:
                raise DocumentAnalysisError("Unknown or duplicate extraction query")
            answers = []
            for relation in block.get("Relationships", []):
                if relation.get("Type") != "ANSWER":
                    continue
                for ident in relation.get("Ids", []):
                    answer = index.get(ident)
                    if not answer or answer.get("BlockType") != "QUERY_RESULT":
                        raise DocumentAnalysisError("Detached extraction answer")
                    answers.append(field(answer.get("Text"), answer.get("Confidence", 0)))
            found[alias] = answers[0] if len(answers) == 1 else field(status="conflicting" if answers else "missing")
        return {name: found.get(name, field()) for name in QUERIES[kind]}

    @staticmethod
    def _license(response):
        documents = response.get("IdentityDocuments")
        if not isinstance(documents, list) or len(documents) != 1:
            raise DocumentAnalysisError("Expected one analyzed identity document")
        entries = documents[0].get("IdentityDocumentFields")
        if not isinstance(entries, list) or len(entries) > 100:
            raise DocumentAnalysisError("Invalid identity field collection")
        values = {}
        for item in entries:
            label = item.get("Type", {}).get("Text")
            if not isinstance(label, str):
                raise DocumentAnalysisError("Invalid identity field label")
            label = label.upper().replace(" ", "_")
            detection = item.get("ValueDetection", {})
            if label in values:
                values[label] = field(status="conflicting")
            else:
                values[label] = field(detection.get("Text"), detection.get("Confidence", 0))
        result = {name: values.get(label, field()) for name, label in {
            "first_name": "FIRST_NAME", "last_name": "LAST_NAME", "drivers_license_number": "DOCUMENT_NUMBER", "expiry_date": "EXPIRATION_DATE"}.items()}
        parts = [values.get(label, field()) for label in ("ADDRESS", "CITY_IN_ADDRESS", "STATE_IN_ADDRESS", "ZIP_CODE_IN_ADDRESS")]
        complete = all(part["status"] == "extracted" for part in parts)
        result["address"] = field(", ".join(part["valueString"] for part in parts if part["valueString"]) or None,
                                  min(part["confidence"] * 100 for part in parts), status=None if complete else "partial")
        return result

    def _analyze(self, document, stop):
        if stop.is_set():
            raise DocumentAnalysisError("Analysis cancelled before SDK acquisition")
        client = self._client()
        try:
            payload = {"S3Object": {"Bucket": document.bucket, "Name": document.key, "Version": document.version}}
            if document.kind == "drivers_license":
                response = client.analyze_id(DocumentPages=[payload])
            else:
                response = client.analyze_document(Document=payload, FeatureTypes=["QUERIES"], QueriesConfig={
                    "Queries": [{"Alias": alias, "Text": query, "Pages": ["1"]} for alias, query in QUERIES[document.kind].items()]})
            if stop.is_set():
                raise DocumentAnalysisError("Analysis cancelled")
            if not isinstance(response, dict) or response.get("DocumentMetadata", {}).get("Pages") != 1:
                raise DocumentAnalysisError("Expected a complete single-page analysis")
            fields = self._license(response) if document.kind == "drivers_license" else self._queries(response, document.kind)
            result = {"extracted_fields": fields, "source_id": document.source_id,
                      "requires_review": any(value["status"] != "extracted" for value in fields.values()),
                      "identity_verified": False}
            if len(json.dumps(result).encode()) > 49152:
                raise DocumentAnalysisError("Extracted result exceeds the configured limit")
            return result
        finally:
            client.close()

    async def analyze(self, handle, kind):
        if not isinstance(handle, str) or handle not in self._documents:
            raise DocumentAnalysisError("Document is not registered for this conversation")
        document = self._documents[handle]
        if kind != document.kind:
            raise DocumentAnalysisError("Document kind does not match its registration")
        task, stop = None, threading.Event()
        try:
            async with asyncio.timeout(60):
                if await self._authorize(handle, document) is not True:
                    raise DocumentAnalysisError("Document analysis was not authorized")
                task = asyncio.create_task(asyncio.to_thread(self._analyze, document, stop))
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
            if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit, DocumentAnalysisError)):
                raise
            raise DocumentAnalysisError("Document analysis failed after owned cleanup") from None
