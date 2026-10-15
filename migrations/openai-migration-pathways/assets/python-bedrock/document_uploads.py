"""Owned document uploads shared between ingress and an application worker.

The caller binds authenticated identity and a server-owned conversation scope.
Redis is a trusted, access-controlled registry, not an authentication service.
Only opaque handles cross the model boundary. No presigned URLs are created.
"""
import asyncio
import base64
from dataclasses import asdict, dataclass
import hashlib
import inspect
import io
import json
import re
import secrets

from .textract_documents import DocumentReference


class DocumentUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConversationScope:
    principal: str
    session: str
    thread: str

    def __post_init__(self):
        for value in (self.principal, self.session, self.thread):
            if not isinstance(value, str) or not 1 <= len(value) <= 512 or any(ord(c) < 32 for c in value):
                raise ValueError("An authenticated principal and server-owned conversation scope are required")

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ConversationDocuments:
    def __init__(self, scope, registry, *, namespace, bucket, region, prefix, bucket_owner,
                 authorize, approve_content, kms_key=None, ttl_seconds=3600, client_factory=None):
        if not isinstance(scope, ConversationScope):
            raise ValueError("Bind a trusted conversation scope")
        if not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", namespace):
            raise ValueError("Invalid document registry namespace")
        if not isinstance(bucket_owner, str) or not re.fullmatch(r"\d{12}", bucket_owner):
            raise ValueError("Expected S3 bucket account is required")
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region):
            raise ValueError("Explicit S3 Region is required")
        # Reuse the analyzer's document restrictions for the storage boundary.
        DocumentReference(bucket, prefix + "/validation.png", "validation", "utility_bill", 1, "image/png")
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 86400:
            raise ValueError("Document registry lifetime must be between 60 and 86400 seconds")
        if not inspect.iscoroutinefunction(authorize) or not inspect.iscoroutinefunction(approve_content):
            raise ValueError("Async authorization and content approval callbacks are required")
        if kms_key is not None and (not isinstance(kms_key, str) or not kms_key.strip()):
            raise ValueError("Invalid KMS key")
        self.scope, self.registry, self.namespace = scope, registry, namespace
        self.bucket, self.region, self.prefix, self.bucket_owner = bucket, region, prefix, bucket_owner
        self._authorize, self._approve_content = authorize, approve_content
        self.kms_key, self.ttl_seconds, self._client_factory = kms_key, ttl_seconds, client_factory

    def _key(self, handle):
        if not isinstance(handle, str) or not re.fullmatch(r"doc_[a-f0-9]{48}", handle):
            raise DocumentUploadError("Unknown document handle")
        return f"{self.namespace}:document:{handle}"

    async def _require_access(self, operation):
        if await self._authorize(self.scope, operation) is not True:
            raise DocumentUploadError("Document access denied")

    async def require_conversation_access(self):
        """Recheck the bound session before every message, including text-only."""
        await self._require_access("conversation")

    @staticmethod
    async def _owned_call(function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()
            raise

    @staticmethod
    def _decode(encoded):
        if not isinstance(encoded, str) or len(encoded) > 13_333_400:
            raise DocumentUploadError("Invalid or oversized document image")
        declared = None
        if encoded.startswith("data:"):
            header, separator, encoded = encoded.partition(",")
            if not separator or header not in {"data:image/png;base64", "data:image/jpeg;base64"}:
                raise DocumentUploadError("Only PNG and JPEG document images are supported")
            declared = header[5:-7]
        try:
            data = base64.b64decode(encoded, validate=True)
            if not 1 <= len(data) <= 10_000_000:
                raise ValueError("Invalid document length")
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG"} or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Expected one PNG or JPEG image")
                if not 1 <= image.width * image.height <= 40_000_000:
                    raise ValueError("Document dimensions exceed limit")
                media_type = "image/png" if image.format == "PNG" else "image/jpeg"
                image.verify()
            # Verify checks file structure; load also checks the pixel stream.
            with Image.open(io.BytesIO(data)) as image:
                image.load()
            if declared is not None and declared != media_type:
                raise ValueError("Content type mismatch")
        except Exception:
            raise DocumentUploadError("Invalid document image") from None
        return data, media_type

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import boto3
        from botocore.config import Config
        return boto3.session.Session().client("s3", region_name=self.region, config=Config(
            signature_version="s3v4", connect_timeout=5, read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 1}))

    def _put(self, data, media_type, kind, jurisdiction, handle):
        suffix = "png" if media_type == "image/png" else "jpg"
        key = f"{self.prefix}/{self.scope.digest}/{handle}.{suffix}"
        # Reject invalid kinds/jurisdictions before acquiring any SDK client.
        DocumentReference(self.bucket, key, "pending", kind, len(data), media_type, jurisdiction=jurisdiction)
        checksum = base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
        metadata = {"conversation-scope": self.scope.digest}
        client = self._client()
        try:
            parameters = dict(Bucket=self.bucket, Key=key, ExpectedBucketOwner=self.bucket_owner,
                              Body=data, ContentType=media_type, CacheControl="private, no-store",
                              ChecksumSHA256=checksum, Metadata=metadata, IfNoneMatch="*")
            if self.kms_key:
                parameters.update(ServerSideEncryption="aws:kms", SSEKMSKeyId=self.kms_key)
            response = client.put_object(**parameters)
            version = response.get("VersionId")
            reference = DocumentReference(self.bucket, key, version, kind, len(data), media_type, jurisdiction=jurisdiction)
            head = client.head_object(Bucket=self.bucket, Key=key, VersionId=version,
                                      ExpectedBucketOwner=self.bucket_owner, ChecksumMode="ENABLED")
            if (head.get("VersionId") != version or head.get("ContentLength") != len(data)
                    or head.get("ContentType") != media_type or head.get("ChecksumSHA256") != checksum
                    or head.get("Metadata") != metadata):
                raise DocumentUploadError("Uploaded document verification failed")
            return reference
        finally:
            client.close()

    async def upload(self, encoded, kind, *, jurisdiction=None):
        await self._require_access("upload")
        data, media_type = await self._owned_call(self._decode, encoded)
        DocumentReference(self.bucket, self.prefix + "/validation.png", "pending", kind,
                          len(data), media_type, jurisdiction=jurisdiction)
        # The content check is application-owned; no model can self-approve it.
        if await self._approve_content(data, media_type) is not True:
            raise DocumentUploadError("Document content was rejected")
        handle = "doc_" + secrets.token_hex(24)
        try:
            reference = await self._owned_call(self._put, data, media_type, kind, jurisdiction, handle)
            await self._require_access("publish")
            record = json.dumps({"version": 1, "scope": self.scope.digest, "region": self.region,
                                 "document": asdict(reference)}, sort_keys=True, separators=(",", ":"))
            if await self.registry.set(self._key(handle), record, nx=True, ex=self.ttl_seconds) is not True:
                raise DocumentUploadError("Document handle publication failed")
            return handle
        except asyncio.CancelledError:
            raise
        except Exception:
            # A verified or ambiguous upload can remain private in S3. Do not
            # delete a possibly committed object or return an unregistered URL.
            raise DocumentUploadError("Document upload or registration failed") from None

    async def resolve(self, handle):
        await self._require_access("read")
        raw = await self.registry.get(self._key(handle))
        try:
            if not isinstance(raw, (str, bytes)) or len(raw) > 16384:
                raise ValueError("Missing registry record")
            record = json.loads(raw)
            if (set(record) != {"version", "scope", "region", "document"} or type(record["version"]) is not int
                    or record["version"] != 1 or record["scope"] != self.scope.digest or record["region"] != self.region):
                raise ValueError("Wrong document owner")
            reference = DocumentReference(**record["document"])
            suffix = "png" if reference.media_type == "image/png" else "jpg"
            if (reference.bucket != self.bucket or reference.media_type not in {"image/png", "image/jpeg"}
                    or reference.key != f"{self.prefix}/{self.scope.digest}/{handle}.{suffix}"):
                raise ValueError("Wrong document storage boundary")
            return reference
        except Exception:
            raise DocumentUploadError("Document is unavailable for this conversation") from None

    async def authorize_document(self, handle, reference):
        return await self.resolve(handle) == reference

    def _get(self, reference):
        client, body = self._client(), None
        try:
            response = client.get_object(
                Bucket=reference.bucket, Key=reference.key, VersionId=reference.version,
                ExpectedBucketOwner=self.bucket_owner, ChecksumMode="ENABLED")
            body = response.get("Body")
            if (body is None or response.get("VersionId") != reference.version
                    or type(response.get("ContentLength")) is not int
                    or response["ContentLength"] != reference.size_bytes
                    or response.get("ContentType") != reference.media_type
                    or response.get("Metadata") != {"conversation-scope": self.scope.digest}
                    or response.get("ContentEncoding") or response.get("ContentRange")
                    or response.get("DeleteMarker")):
                raise DocumentUploadError("Document download verification failed")
            data = body.read(reference.size_bytes + 1)
            if (not isinstance(data, bytes) or len(data) != reference.size_bytes
                    or response.get("ChecksumSHA256") != base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")):
                raise DocumentUploadError("Document download verification failed")
            return data
        finally:
            try:
                if body is not None:
                    body.close()
            finally:
                client.close()

    async def download(self, handle):
        """Return bounded bytes only after current ownership and integrity checks."""
        try:
            reference = await self.resolve(handle)
            data = await self._owned_call(self._get, reference)
            # Revocation, expiry or registry changes during storage I/O must not
            # turn a stale authorization into a delivered document.
            if await self.resolve(handle) != reference:
                raise DocumentUploadError("Document registration changed")
            return data, reference.media_type
        except asyncio.CancelledError:
            raise
        except Exception:
            raise DocumentUploadError("Document is unavailable for this conversation") from None

    async def load_into(self, analyzer, handles):
        if (not isinstance(handles, list) or len(handles) > 100 or any(not isinstance(h, str) for h in handles)
                or len(set(handles)) != len(handles)):
            raise DocumentUploadError("Provide a bounded list of unique document handles")
        documents = {handle: await self.resolve(handle) for handle in handles}
        analyzer.register_documents(documents)
