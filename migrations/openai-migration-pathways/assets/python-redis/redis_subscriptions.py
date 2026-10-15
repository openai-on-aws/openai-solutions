"""Owned, serial Redis pub/sub listeners. Delivery remains non-durable.

The caller owns the Redis client and must not close it unless close() succeeds.
No reconnect/replay guarantees are added to those of the configured Redis client.
"""
import asyncio
import math


class RedisSubscriptions:
    def __init__(self, client, logger):
        self._client = client
        self._logger = logger
        self._entries = []
        self._failed = False
        self.stop_requested = asyncio.Event()
        self._close_lock = asyncio.Lock()

    @property
    def healthy(self):
        return (bool(self._entries) and not self._failed
                and not self.stop_requested.is_set()
                and all(entry["ready"].done() and not entry["ready"].cancelled()
                        and entry["ready"].exception() is None
                        and entry["task"] is not None and not entry["task"].done()
                        for entry in self._entries))

    def request_stop(self):
        self.stop_requested.set()

    async def start(self, channels, callback, startup_seconds=10):
        if self.stop_requested.is_set() or self._failed:
            raise RuntimeError("Subscriptions cannot restart after stop or failure")
        if (not isinstance(channels, (list, tuple)) or not channels
                or any(not isinstance(channel, str) or not channel for channel in channels)):
            raise ValueError("Provide nonempty channel names")
        self._deadline(startup_seconds)
        channels = tuple(dict.fromkeys(channels))
        ready = asyncio.get_running_loop().create_future()
        # Observe startup failure even when the start caller has been cancelled.
        ready.add_done_callback(lambda future: None if future.cancelled() else future.exception())
        entry = {"pubsub": self._client.pubsub(), "ready": ready,
                 "task": None, "cleanup_task": None, "closed": False}
        self._entries.append(entry)
        coroutine = self._listen(entry, channels, callback)
        try:
            entry["task"] = asyncio.create_task(coroutine)
        except BaseException:
            coroutine.close()
            ready.cancel()
            self._failed = True
            self.request_stop()
            raise
        entry["task"].add_done_callback(self._completed)
        try:
            await asyncio.wait_for(asyncio.shield(ready), timeout=startup_seconds)
            if self.stop_requested.is_set() or entry["task"].done():
                raise RuntimeError("Subscription stopped during startup")
            return entry["task"]
        except BaseException:
            self._failed = True
            self.request_stop()
            entry["task"].cancel()
            raise

    async def _listen(self, entry, channels, callback):
        pubsub, ready = entry["pubsub"], entry["ready"]
        pending = set(channels)
        try:
            await pubsub.subscribe(*channels)
            while not self.stop_requested.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=False, timeout=0.5)
                if message is None:
                    continue
                if message["type"] == "subscribe":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    pending.discard(channel)
                    if not pending and not ready.done():
                        ready.set_result(None)
                    continue
                if message["type"] != "message":
                    continue
                try:
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await callback(data)
                except Exception:
                    # A malformed delivery must not disable all other sessions.
                    self._logger.error("Subscription callback failed")
        finally:
            if not ready.done():
                ready.set_exception(RuntimeError("Subscription ended before acknowledgment"))
            await pubsub.aclose()
            entry["closed"] = True

    def _completed(self, task):
        error = None if task.cancelled() else task.exception()
        if error is not None or not self.stop_requested.is_set():
            self._failed = True
            self.request_stop()
            self._logger.error("Redis subscription stopped unexpectedly")

    @staticmethod
    def _deadline(value):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Subscription deadlines must be finite and nonnegative")

    async def _close_entry(self, entry):
        await entry["pubsub"].aclose()
        entry["closed"] = True

    async def close(self, grace_seconds=5, cancel_seconds=5):
        self._deadline(grace_seconds)
        self._deadline(cancel_seconds)
        async with self._close_lock:
            self.request_stop()
            tasks = [entry["task"] for entry in self._entries if entry["task"] is not None]
            if asyncio.current_task() in tasks:
                raise RuntimeError("A subscription callback cannot join itself")
            try:
                if tasks:
                    _, pending = await asyncio.wait(tasks, timeout=grace_seconds)
                    for task in pending:
                        task.cancel()
                    if pending:
                        _, pending = await asyncio.wait(pending, timeout=cancel_seconds)
                    if pending:
                        self._logger.error("Subscription callbacks remain active; retain their resources")
                        return False
                # Includes handles acquired before task creation and failed cleanup.
                success, cleanup = True, []
                for entry in self._entries:
                    if not entry["closed"]:
                        task = entry["cleanup_task"]
                        if task is None or task.done():
                            coroutine = self._close_entry(entry)
                            try:
                                task = asyncio.create_task(coroutine)
                            except BaseException:
                                coroutine.close()
                                raise
                            entry["cleanup_task"] = task
                            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
                        cleanup.append(task)
                if cleanup:
                    done, pending = await asyncio.wait(cleanup, timeout=cancel_seconds)
                    success = not pending and all(not task.cancelled() and task.exception() is None for task in done)
                    if not success:
                        self._logger.error("Redis subscription cleanup incomplete; retain its handles")
                return success
            except asyncio.CancelledError:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise
