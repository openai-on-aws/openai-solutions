"""Per-attempt reply matching and completion after an awaited socket write.

This is not authentication, browser acknowledgment, durable delivery or replay.
Use one tracker per live connection; always finish an attempt in a finally block.
"""
import asyncio
import math
from types import SimpleNamespace
import uuid


class RequestTracker:
    def __init__(self):
        self._pending = None
        self._delivery_lock = asyncio.Lock()

    def begin(self, *, session_id, dialog_id, thread_id, user_id, timeout):
        if self._pending is not None:
            raise RuntimeError("A request is already active")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Response timeout must be finite and positive")
        loop = asyncio.get_running_loop()
        pending = SimpleNamespace(
            request_id=uuid.uuid4().hex, session_id=session_id, dialog_id=dialog_id,
            thread_id=thread_id, user_id=user_id, deadline=loop.time() + timeout,
            completed=loop.create_future(), closed=False,
        )
        self._pending = pending
        return pending

    async def wait(self, pending):
        remaining = max(0, pending.deadline - asyncio.get_running_loop().time())
        delivered = await asyncio.wait_for(asyncio.shield(pending.completed), timeout=remaining)
        if not delivered:
            raise ConnectionError("Response delivery failed")

    async def deliver(self, response, serialize, send):
        async with self._delivery_lock:
            pending = self._pending
            if (pending is None or pending.closed or pending.completed.done()
                    or asyncio.get_running_loop().time() >= pending.deadline):
                return False
            for field in ("request_id", "session_id", "dialog_id", "thread_id", "user_id"):
                if getattr(response, field, None) != getattr(pending, field):
                    return False
            try:
                # Stay in the owned response task; no orphan write on timeout.
                async with asyncio.timeout_at(pending.deadline):
                    payload = await serialize(response)
                    await send(payload)
                    if asyncio.get_running_loop().time() >= pending.deadline:
                        raise asyncio.TimeoutError("Response deadline elapsed")
            except BaseException:
                pending.closed = True
                if not pending.completed.done():
                    pending.completed.set_result(False)
                raise
            terminal = response.error is not None or bool(getattr(response.answer, "is_final", False))
            if terminal:
                pending.closed = True
                pending.completed.set_result(True)
            return True

    async def finish(self, pending):
        if pending is None:
            return
        async with self._delivery_lock:
            pending.closed = True
            if not pending.completed.done():
                pending.completed.cancel()
            if self._pending is pending:
                self._pending = None
