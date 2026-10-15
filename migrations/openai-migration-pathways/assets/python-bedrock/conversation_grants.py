"""Short-lived, server-issued conversation grants in a private Redis registry."""
import json
import re
import secrets
import time

from .alb_identity import AuthenticatedIdentity
from .document_uploads import ConversationScope


class ConversationGrants:
    OPERATIONS = frozenset({"conversation", "upload", "publish", "read", "form_update", "policy_read"})

    def __init__(self, registry, *, namespace, allowed_operations, max_seconds=3600, clock=time.time):
        if not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", namespace):
            raise ValueError("Invalid authorization registry namespace")
        if (not isinstance(allowed_operations, frozenset) or not allowed_operations
                or not allowed_operations <= self.OPERATIONS):
            raise ValueError("Provide the application's explicit conversation permissions")
        if type(max_seconds) is not int or not 1 <= max_seconds <= 3600:
            raise ValueError("Conversation grant lifetime must be between 1 and 3600 seconds")
        self.registry, self.namespace = registry, namespace
        self.allowed_operations, self.max_seconds, self._clock = allowed_operations, max_seconds, clock

    def _key(self, scope):
        if not isinstance(scope, ConversationScope):
            raise ValueError("A bound conversation scope is required")
        return f"{self.namespace}:conversation:{scope.digest}"

    async def issue(self, identity, session):
        """Ingress-only: identity must come from the configured verifier."""
        if (not isinstance(identity, AuthenticatedIdentity) or not re.fullmatch(r"id_[a-f0-9]{64}", identity.principal)
                or type(identity.expires_at) is not int):
            raise ValueError("A verified identity is required")
        now = int(self._clock())
        expires = min(identity.expires_at, now + self.max_seconds)
        if expires <= self._clock():
            raise PermissionError("Authentication has expired")
        scope = ConversationScope(identity.principal, session, "aws_" + secrets.token_hex(32))
        value = json.dumps({"version": 1, "scope": scope.digest, "expires_at": expires,
                            "operations": sorted(self.allowed_operations)}, sort_keys=True, separators=(",", ":"))
        if await self.registry.set(self._key(scope), value, nx=True, ex=expires - now) is not True:
            raise PermissionError("Conversation admission failed")
        return scope

    async def authorize(self, scope, operation):
        if operation not in self.allowed_operations:
            return False
        try:
            raw = await self.registry.get(self._key(scope))
            if not isinstance(raw, (str, bytes)) or len(raw) > 4096:
                return False
            record = json.loads(raw)
            return (set(record) == {"version", "scope", "expires_at", "operations"}
                    and type(record["version"]) is int and record["version"] == 1
                    and record["scope"] == scope.digest and type(record["expires_at"]) is int
                    and self._clock() < record["expires_at"] <= self._clock() + self.max_seconds
                    and isinstance(record["operations"], list)
                    and set(record["operations"]) <= self.OPERATIONS
                    and operation in record["operations"])
        except Exception:
            return False

    async def revoke(self, scope):
        """Ingress-only: delete this exact server-owned conversation grant."""
        await self.registry.delete(self._key(scope))
