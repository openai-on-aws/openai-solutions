"""Own cooperative queue workers and expose their lifecycle to a service.

This does not add acknowledgment/replay to an at-most-once queue. A worker must
finish an item acquired before stop was requested, then stop polling.
"""
import asyncio
import math
import inspect


class WorkerPool:
    def __init__(self, worker, count, logger):
        if type(count) is not int or count < 1:
            raise ValueError("Worker count must be a positive integer")
        self._worker = worker
        self._count = count
        self._logger = logger
        self.stop_requested = asyncio.Event()
        self._tasks = []
        self._failed = False
        self._started = False
        self._close_lock = asyncio.Lock()

    def start(self):
        if self._started or self.stop_requested.is_set():
            raise RuntimeError("Worker pool cannot be restarted")
        self._started = True
        try:
            for _ in range(self._count):
                coroutine = self._worker(self.stop_requested)
                try:
                    task = asyncio.create_task(coroutine)
                except BaseException:
                    if inspect.iscoroutine(coroutine):
                        coroutine.close()
                    raise
                self._tasks.append(task)
                task.add_done_callback(self._completed)
        except BaseException:
            self._failed = True
            self.request_stop()
            for task in self._tasks:
                task.cancel()
            raise

    def _completed(self, task):
        # Retrieve exceptions so an unobserved task failure cannot disappear.
        error = None if task.cancelled() else task.exception()
        if error is not None or not self.stop_requested.is_set():
            self._failed = True
            self.request_stop()
            self._logger.error("Background worker stopped unexpectedly")

    @property
    def healthy(self):
        return (self._started and bool(self._tasks) and not self._failed
                and not self.stop_requested.is_set() and all(not task.done() for task in self._tasks))

    def request_stop(self):
        self.stop_requested.set()

    async def close(self, grace_seconds=30, cancel_seconds=5):
        for value in (grace_seconds, cancel_seconds):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Worker shutdown deadlines must be finite and nonnegative")
        async with self._close_lock:
            self.request_stop()
            if not self._tasks:
                return True
            try:
                _, pending = await asyncio.wait(self._tasks, timeout=grace_seconds)
                if pending:
                    self._logger.warning("Worker drain deadline reached; cancelling unfinished work")
                    for task in pending:
                        task.cancel()
                    _, pending = await asyncio.wait(pending, timeout=cancel_seconds)
                if pending:
                    self._logger.error("Workers remain active after cancellation; resources must remain owned")
                    return False
                return True
            except asyncio.CancelledError:
                for task in self._tasks:
                    if not task.done():
                        task.cancel()
                raise
