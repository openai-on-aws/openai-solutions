"""Process-local conversation state, scoped by identity and serialized by thread.

This is not authentication, durable state, credential refresh or a distributed
lock. Use one instance on one event loop. Multi-replica workers need shared state
and fenced ownership before they can safely process the same remote thread.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import secrets


@dataclass(repr=False)
class _Entry:
    value: object = None


@dataclass(repr=False)
class _Gate:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class ConversationCache:
    def __init__(self):
        self._entries = {}
        self._gates = {}
        self._key = secrets.token_bytes(32)

    def _scope(self, request):
        scope = {}
        for name in ("session_id", "thread_id", "user_id"):
            value = getattr(request, name, None)
            if not isinstance(value, str) or not value:
                raise ValueError("Missing conversation identity")
            scope[name] = value
        authorization = getattr(request, "authorization", None)
        if authorization is not None and not isinstance(authorization, str):
            raise ValueError("Invalid conversation credential")
        scope["authorization"] = authorization
        for name in ("overrides", "user_profile"):
            value = getattr(request, name, None)
            scope[name] = value.model_dump(mode="json") if value is not None else None
        encoded = json.dumps(scope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return hmac.new(self._key, encoded, hashlib.sha256).digest()

    @asynccontextmanager
    async def lease(self, request):
        scope = self._scope(request)
        # The same remote thread cannot run concurrently even when a request
        # changes its local session, principal or credential scope.
        thread = request.thread_id
        gate = self._gates.setdefault(thread, _Gate())
        gate.users += 1
        try:
            async with gate.lock:
                entry = self._entries.setdefault(scope, _Entry())
                # Initialization and invocation both belong inside this lease.
                # Publish entry.value only after initialization succeeds.
                yield entry
        finally:
            gate.users -= 1
            if gate.users == 0:
                del self._gates[thread]
