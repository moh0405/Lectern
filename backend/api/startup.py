"""Bring the API up after it starts listening, for hosts that limit how long startup may take.

AWS Lambda allows 10 seconds for init, and the Lambda Web Adapter ends init only when `/health` answers. Restoring
the index from S3 and importing PyTorch take longer than that, so on Lambda the server starts listening first and
this loader does the heavy work during the first real request.

Lambda freezes the process between requests, so a background thread only makes progress while a request is open.
That is why callers wait here (for a bounded time) rather than returning at once and hoping the work continues.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import Callable, Optional

logger = logging.getLogger("ai-study-mentor.api")

# Sent by the Lambda Web Adapter on every forwarded invocation and absent from its own readiness check.
LAMBDA_INVOKE_HEADER = "x-amzn-lambda-context"


class DeferredStartup:
    """Runs `load` once, however many requests ask at the same time. A failed load is tried again on the next ask."""

    def __init__(self, load: Callable[[], None]) -> None:
        self._load = load
        self._lock = threading.Lock()
        self._future: Optional[Future] = None

    @property
    def ready(self) -> bool:
        future = self._future
        return bool(future and future.done() and future.exception() is None)

    @property
    def failed(self) -> bool:
        future = self._future
        return bool(future and future.done() and future.exception() is not None)

    def begin(self) -> Future:
        with self._lock:
            if self._future is None or self.failed:
                future: Future = Future()
                self._future = future
                threading.Thread(target=self._run, args=(future,), name="api-startup", daemon=True).start()
            return self._future

    def _run(self, future: Future) -> None:
        try:
            self._load()
        except BaseException as e:  # reported through the future; the next request tries again
            logger.exception("API startup failed")
            future.set_exception(e)
        else:
            future.set_result(None)

    async def wait(self, timeout: float) -> bool:
        """Start loading if needed and wait up to `timeout` seconds. True once the API is ready."""
        future = self.begin()
        if not future.done():
            loop = asyncio.get_running_loop()
            finished = asyncio.Event()

            def wake(_: Future) -> None:
                try:
                    loop.call_soon_threadsafe(finished.set)
                except RuntimeError:  # the waiting request's event loop has closed
                    pass

            future.add_done_callback(wake)
            try:
                await asyncio.wait_for(finished.wait(), timeout)
            except asyncio.TimeoutError:
                return False
        return self.ready
