"""Environment-configured authenticated AWS session runtime for application ingress."""
import json
import os
import re

from .alb_identity import AlbIdentityVerifier
from .authenticated_sessions import AuthenticatedDocumentSessions
from .conversation_grants import ConversationGrants
from .document_uploads import ConversationDocuments, ConversationScope, DocumentUploadError


class RekognitionAdmission:
    def __init__(self, region, *, client_factory=None):
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region):
            raise ValueError("Explicit moderation Region is required")
        self.region, self._client_factory = region, client_factory

    def _check(self, data):
        if self._client_factory is None:
            import boto3
            from botocore.config import Config
            client = boto3.session.Session().client("rekognition", region_name=self.region, config=Config(
                connect_timeout=5, read_timeout=30, retries={"mode": "standard", "total_max_attempts": 1}))
        else:
            client = self._client_factory()
        try:
            result = client.detect_moderation_labels(Image={"Bytes": data}, MinConfidence=80)
            labels = result.get("ModerationLabels")
            if not isinstance(labels, list) or result.get("HumanLoopActivationOutput"):
                raise DocumentUploadError("Content admission requires review")
            return len(labels) == 0
        finally:
            client.close()

    async def approve(self, data, media_type):
        # The bytes-based moderation route has a stricter limit than Textract.
        if not isinstance(data, bytes) or not 1 <= len(data) <= 5_000_000 or media_type not in {"image/png", "image/jpeg"}:
            raise DocumentUploadError("AWS content admission accepts PNG/JPEG images up to 5 MB")
        try:
            return await ConversationDocuments._owned_call(self._check, data)
        except Exception:
            raise DocumentUploadError("Document content admission failed") from None


def create_aws_session_runtime(registry, environment=None):
    environment = os.environ if environment is None else environment
    names = ("ALB_SIGNER_ARN", "OIDC_ISSUER", "OIDC_CLIENT_ID", "APPLICATION_ORIGINS", "DOCUMENT_REGISTRY_NAMESPACE",
             "AWS_REGION", "AWS_ACCOUNT_ID", "S3_IMAGE_BUCKET", "S3_IMAGE_PREFIX", "S3_IMAGE_KMS_KEY_ID")
    if any(not isinstance(environment.get(name), str) or not environment[name] for name in names):
        raise ValueError("Configure AWS ingress identity, origins, registry and document storage")
    origins = json.loads(environment["APPLICATION_ORIGINS"])
    if not isinstance(origins, list) or not origins or len(origins) > 16 or any(not isinstance(value, str) for value in origins):
        raise ValueError("APPLICATION_ORIGINS must be a bounded JSON list")
    verifier = AlbIdentityVerifier(signer_arn=environment["ALB_SIGNER_ARN"], issuer=environment["OIDC_ISSUER"], client_id=environment["OIDC_CLIENT_ID"])
    grants = ConversationGrants(registry, namespace=environment["DOCUMENT_REGISTRY_NAMESPACE"], allowed_operations=ConversationGrants.OPERATIONS)
    moderator = RekognitionAdmission(environment["AWS_REGION"])
    # Capture configuration once; later environment changes cannot retarget a
    # conversation or its storage boundary while the service is running.
    settings = {key: environment[key] for key in names}
    def documents(scope, authorize):
        return ConversationDocuments(scope, registry, namespace=settings["DOCUMENT_REGISTRY_NAMESPACE"],
            bucket=settings["S3_IMAGE_BUCKET"], region=settings["AWS_REGION"], prefix=settings["S3_IMAGE_PREFIX"],
            bucket_owner=settings["AWS_ACCOUNT_ID"], kms_key=settings["S3_IMAGE_KMS_KEY_ID"],
            authorize=authorize, approve_content=moderator.approve)
    documents(ConversationScope("validation", "validation", "validation"), grants.authorize)
    return AuthenticatedDocumentSessions(verifier, grants, documents, allowed_origins=frozenset(origins))
