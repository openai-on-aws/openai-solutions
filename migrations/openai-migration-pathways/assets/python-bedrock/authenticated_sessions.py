"""Bind verified ALB identity, revocable grants and document ownership."""
from urllib.parse import urlsplit

from .alb_identity import AuthenticationError


class AuthenticatedDocumentSessions:
    def __init__(self, verifier, grants, document_factory, *, allowed_origins):
        if not isinstance(allowed_origins, frozenset) or not allowed_origins:
            raise ValueError("Explicit browser origins are required")
        for origin in allowed_origins:
            parsed = urlsplit(origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment
                    or parsed.username or parsed.password or any(c.isspace() for c in origin)):
                raise ValueError("Use exact HTTPS browser origins without paths")
        self.verifier, self.grants, self.document_factory = verifier, grants, document_factory
        self.allowed_origins = allowed_origins

    @staticmethod
    def _header(headers, name):
        # aiohttp's case-insensitive multidict preserves duplicate headers.
        values = headers.getall(name, []) if hasattr(headers, "getall") else [headers.get(name)]
        if len(values) != 1 or not isinstance(values[0], str) or not values[0]:
            raise AuthenticationError("Missing or duplicate authentication header")
        return values[0]

    async def identity(self, headers):
        return await self.verifier.verify(self._header(headers, "x-amzn-oidc-data"))

    async def open(self, headers, session):
        if self._header(headers, "Origin") not in self.allowed_origins:
            raise AuthenticationError("Browser origin is not allowed")
        identity = await self.identity(headers)
        scope = await self.grants.issue(identity, session)
        try:
            documents = self.document_factory(scope, self.grants.authorize)
            if documents.scope != scope:
                raise AuthenticationError("Document factory changed the conversation owner")
            return documents
        except BaseException:
            await self.grants.revoke(scope)
            raise

    async def close(self, documents):
        await self.grants.revoke(documents.scope)

    async def download(self, headers, documents, handle):
        identity = await self.identity(headers)
        if identity.principal != documents.scope.principal:
            raise AuthenticationError("Document owner does not match authenticated identity")
        result = await documents.download(handle)
        # Recheck token expiry as well as the document's revocable grant before
        # returning bytes; never forward the storage URL or credentials.
        identity = await self.identity(headers)
        if identity.principal != documents.scope.principal:
            raise AuthenticationError("Document owner changed")
        await documents.require_conversation_access()
        return result
