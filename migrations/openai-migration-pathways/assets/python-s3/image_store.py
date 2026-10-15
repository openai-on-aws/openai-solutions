"""S3 image uploads with caller-configured task credentials and bounded IO.

No buckets, policies or public ACLs are created. Each blocking SDK operation owns
and closes its client in the worker thread; cancellation joins that operation.
Presigned URLs are bearer credentials. Never log them or treat a key as identity.
"""
import asyncio
import base64
import binascii
import os
import re
import uuid


class ImageStorageError(ValueError):
    pass


class S3ImageStore:
    def __init__(self, bucket, region, prefix, *, kms_key=None, expires_in=900, max_bytes=20 * 1024 * 1024, client_factory=None):
        if not isinstance(bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise ImageStorageError("Invalid S3 image bucket")
        if not isinstance(region, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", region):
            raise ImageStorageError("Invalid S3 region")
        if not isinstance(prefix, str) or not prefix or any(part in {"", ".", ".."} for part in prefix.split("/")) or any(ord(c) < 32 for c in prefix):
            raise ImageStorageError("Invalid S3 image prefix")
        if type(expires_in) is not int or not 1 <= expires_in <= 3600:
            raise ImageStorageError("Image URL lifetime must be between 1 and 3600 seconds")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 20 * 1024 * 1024:
            raise ImageStorageError("Invalid image size limit")
        if kms_key is not None and (not isinstance(kms_key, str) or not kms_key.strip()):
            raise ImageStorageError("Invalid image KMS key")
        self.bucket, self.region, self.prefix = bucket, region, prefix
        self.kms_key, self.expires_in, self.max_bytes = kms_key, expires_in, max_bytes
        self._client_factory = client_factory

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get("S3_IMAGE_BUCKET"), os.environ.get("AWS_REGION"), os.environ.get("S3_IMAGE_PREFIX"), kms_key=os.environ.get("S3_IMAGE_KMS_KEY_ID"))

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import boto3
        from botocore.config import Config
        # A per-operation Session avoids sharing the implicit default session
        # while multiple image uploads construct clients in different threads.
        return boto3.session.Session().client("s3", region_name=self.region, config=Config(
            signature_version="s3v4", s3={"addressing_style": "virtual"},
            connect_timeout=5, read_timeout=30, retries={"mode": "standard", "total_max_attempts": 3},
        ))

    def _decode(self, encoded):
        if not isinstance(encoded, (bytes, str)) or len(encoded) > 4 * ((self.max_bytes + 2) // 3) + 64:
            raise ImageStorageError("Invalid or oversized image encoding")
        declared = None
        if isinstance(encoded, str) and encoded.startswith("data:"):
            header, separator, encoded = encoded.partition(",")
            if not separator or not header.endswith(";base64"):
                raise ImageStorageError("Expected a base64 image data URL")
            declared = header[5:-7]
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ImageStorageError("Invalid image encoding") from None
        if not data or len(data) > self.max_bytes:
            raise ImageStorageError("Invalid image size")
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            extension, mime = "png", "image/png"
        elif data.startswith(b"\xff\xd8\xff"):
            extension, mime = "jpg", "image/jpeg"
        elif data.startswith((b"GIF87a", b"GIF89a")):
            extension, mime = "gif", "image/gif"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            extension, mime = "webp", "image/webp"
        else:
            raise ImageStorageError("Unsupported image format")
        if declared is not None and declared != mime:
            raise ImageStorageError("Image content type mismatch")
        return data, extension, mime

    def _upload(self, encoded):
        # Decode in the worker thread too; malformed input makes no AWS call.
        data, extension, mime = self._decode(encoded)
        key = f"{self.prefix}/{uuid.uuid4().hex}.{extension}"
        client = self._client()
        try:
            parameters = dict(Bucket=self.bucket, Key=key, Body=data, ContentType=mime, CacheControl="private, no-store")
            if self.kms_key:
                parameters.update(ServerSideEncryption="aws:kms", SSEKMSKeyId=self.kms_key)
            client.put_object(**parameters)
            return client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.expires_in, HttpMethod="GET")
        finally:
            client.close()

    async def upload_image_async(self, encoded):
        task = asyncio.create_task(asyncio.to_thread(self._upload, encoded))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Closing resources from the cancelled caller would race SDK IO.
            # Retain ownership until the synchronous operation has unwound.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if task.done() and not task.cancelled():
                task.exception()
            raise
        except Exception:
            raise ImageStorageError("S3 image upload failed") from None
