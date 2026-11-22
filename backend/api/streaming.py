"""Server-Sent Event streams that always end properly, even when the work behind them is slow or stuck.

A model call can block for a long time (retries, fail-over, a slow provider), and a blocking call cannot be
interrupted. So the work runs in a background thread that hands finished frames to the response through a queue,
and the response:

  * sends a comment frame at once, so headers and the first bytes leave before the first model call returns,
  * sends a keep-alive comment whenever nothing else has been sent for a while, so no proxy treats the stream as idle,
  * stops at an overall deadline with a terminal `error` event (`code: "timeout"`), before the platform's own limit
    (AWS Lambda's function timeout, the Vercel function's maxDuration) cuts the connection with no event at all,
  * sends a terminal `error` if the work ends without one, so a client never waits for a `done` that cannot come.

Comment frames start with ':' and are ignored by SSE readers, including the web app's.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Iterator, Optional

logger = logging.getLogger("ai-study-mentor.api")

TERMINAL_EVENTS = ("done", "error")

Emit = Callable[[str], None]


class StreamCancelled(RuntimeError):
    """Raised inside the work when the response has stopped listening (deadline passed or client gone)."""


def comment(text: str) -> str:
    return f": {text}\n\n"


def _event_name(frame: str) -> Optional[str]:
    if frame.startswith("event: "):
        return frame[7:].split("\n", 1)[0].strip()
    return None


def guarded_stream(
    work: Callable[[Emit, threading.Event], None],
    *,
    deadline: float,
    keepalive_s: float,
    timeout_frame: str,
    fallback_frame: str,
    name: str = "sse-work",
) -> Iterator[str]:
    """Run `work(emit, cancelled)` in a thread and yield what it emits, with keep-alives and a deadline.

    `deadline` is a `time.monotonic()` value. `work` should check `cancelled` (or let a wrapped model raise
    StreamCancelled) before starting another slow step; once the response gives up it no longer reads the queue.
    `timeout_frame` is sent when the deadline passes first; `fallback_frame` when `work` returns or raises
    without having emitted a terminal event.
    """
    frames: "queue.Queue[Optional[str]]" = queue.Queue()
    cancelled = threading.Event()

    def emit(frame: str) -> None:
        if cancelled.is_set():
            raise StreamCancelled("the response stopped listening")
        frames.put(frame)

    def runner() -> None:
        try:
            work(emit, cancelled)
        except StreamCancelled:
            pass
        except Exception:  # work is expected to turn its own failures into events; this is the backstop
            logger.exception("Streamed work failed without reporting an error event")
        finally:
            frames.put(None)

    yield comment("stream open")  # flush headers now; the first model call can take a while
    thread = threading.Thread(target=runner, name=name, daemon=True)
    thread.start()
    ended = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("%s passed its deadline; ending the stream with a timeout error", name)
                yield timeout_frame
                ended = True
                return
            try:
                frame = frames.get(timeout=min(keepalive_s, remaining))
            except queue.Empty:
                yield comment("keep-alive")
                continue
            if frame is None:
                if not ended:
                    yield fallback_frame
                    ended = True
                return
            yield frame
            if _event_name(frame) in TERMINAL_EVENTS:
                ended = True
                return
    finally:
        cancelled.set()  # the deadline passed, the work finished, or the client went away (GeneratorExit)


def deadline_from(started_at: float, budget_s: float) -> float:
    """The monotonic time by which a stream that began at `started_at` must have ended."""
    return started_at + max(1.0, budget_s)
