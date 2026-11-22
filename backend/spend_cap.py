"""A daily ceiling on language-model calls, so a leaked or abused endpoint cannot run up the bill.

Set ``DAILY_LLM_LIMIT`` (0 or unset means no limit). Every request sent to the model counts, whichever feature made it:
each agent turn, and each retry or failover attempt (see ``llm_config.AttemptMeter``). With ``S3_BUCKET`` set the count
lives in S3 (``<prefix>/usage/<UTC date>.json``) so it survives restarts and is shared by every copy of the function;
otherwise it is kept in memory, for this process only.

The S3 update is atomic: it is a compare-and-swap using S3 conditional writes (``If-Match`` on the ETag read, or
``If-None-Match: *`` for the day's first call). When two instances race, one write fails and that instance reads again,
so no increment is lost and the limit cannot be passed. If the count cannot be read or saved, or the race cannot be won
after a few tries, the call is refused: when money is at stake the safe failure is to stop.

What remains: a call is counted before it is made and never given back, so a crash or failed call can use up allowance
without spending anything (the count can only err high). The day rolls over on each instance's clock. A request already
in flight when the limit is reached still finishes. The limit counts requests, not tokens.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

MESSAGE = "Daily limit of {limit} model calls reached. Try again after midnight UTC."
CAS_ATTEMPTS = 12  # how many times one call may lose a race for the counter before it is refused
CAS_MAX_WAIT_S = 0.25
_CONFLICT_CODES = {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}  # someone else wrote first


class DailyLimitReached(RuntimeError):
    pass


def _error_code(exc: Exception) -> str:
    return str((getattr(exc, "response", None) or {}).get("Error", {}).get("Code", ""))


class DailyCap:
    def __init__(self, limit: int, client: Optional[Any] = None, bucket: Optional[str] = None, prefix: str = ""):
        self.limit = limit
        self.s3 = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._memory: Dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _key(self, day: str) -> str:
        return "/".join(p for p in (self.prefix, "usage", f"{day}.json") if p)

    def _load(self, day: str) -> Tuple[int, Optional[str]]:
        """(calls so far, the ETag of that count; None when today has no count yet)."""
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._key(day))
        except Exception as e:
            if _error_code(e) in ("NoSuchKey", "404"):
                return 0, None
            raise
        return int(json.loads(obj["Body"].read()).get("calls", 0)), obj["ETag"]

    def _swap(self, day: str, calls: int, etag: Optional[str]) -> bool:
        """Write `calls` only if the count is still the one that was read. False when another instance got there first."""
        condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            self.s3.put_object(Bucket=self.bucket, Key=self._key(day), Body=json.dumps({"calls": calls}).encode(), **condition)
        except Exception as e:
            if _error_code(e) in _CONFLICT_CODES:
                return False
            raise
        return True

    def _reserve_s3(self, day: str) -> int:
        for attempt in range(CAS_ATTEMPTS):
            used, etag = self._load(day)
            if used >= self.limit:
                raise DailyLimitReached(MESSAGE.format(limit=self.limit))
            if self._swap(day, used + 1, etag):
                return used + 1
            time.sleep(random.uniform(0, min(CAS_MAX_WAIT_S, 0.01 * 2**attempt)))  # full jitter, so racers spread out
        raise RuntimeError("too many concurrent updates")

    def _reserve_memory(self, day: str) -> int:
        used = self._memory.get(day, 0)
        if used >= self.limit:
            raise DailyLimitReached(MESSAGE.format(limit=self.limit))
        self._memory = {day: used + 1}
        return used + 1

    def reserve(self) -> int:
        """Count one call. Raises DailyLimitReached when today's allowance is used up. Returns calls used today."""
        if self.limit <= 0:
            return 0
        with self._lock:  # threads of this instance take turns; other instances are handled by the compare-and-swap
            day = self._today()
            try:
                return self._reserve_s3(day) if self.s3 else self._reserve_memory(day)
            except DailyLimitReached:
                raise
            except Exception as e:
                raise DailyLimitReached(f"Model calls are paused because the daily count could not be checked ({e}).") from e


class CappedLLM:
    """Wraps any provider so each ``generate`` or ``stream`` is counted before it reaches the model. The provider counts
    its own further attempts through ``attempt_guard``."""

    def __init__(self, inner: Any, cap: DailyCap):
        self._inner = inner
        self._cap = cap
        if hasattr(inner, "attempt_guard"):
            inner.attempt_guard = cap.reserve  # so retries and failover attempts inside the provider count as well

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def generate(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            self._cap.reserve()
        except DailyLimitReached as e:
            return {"ok": False, "error": str(e)}
        return self._inner.generate(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any):
        self._cap.reserve()  # raises DailyLimitReached, which the caller turns into an error event
        return self._inner.stream(*args, **kwargs)

    def start_tool_chat(self, *args: Any, **kwargs: Any):
        return CappedToolChat(self._inner.start_tool_chat(*args, **kwargs), self._cap)


class CappedToolChat:
    """Counts every turn of a tool chat; further attempts within a turn are counted by the chat through `attempt_guard`."""

    def __init__(self, inner: Any, cap: DailyCap):
        self._inner = inner
        self._cap = cap

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def send(self, message: Any):
        self._cap.reserve()
        return self._inner.send(message)


_cap: Optional[DailyCap] = None


def get_cap() -> DailyCap:
    """The process-wide cap, built from the environment on first use."""
    global _cap
    if _cap is None:
        limit = int(os.getenv("DAILY_LLM_LIMIT", "0") or 0)
        bucket = os.getenv("S3_BUCKET") or None
        client = None
        if limit > 0 and bucket:
            from .cloud_sync import _client

            client = _client()
        _cap = DailyCap(limit, client, bucket, os.getenv("S3_PREFIX", "ai-study-mentor"))
    return _cap


def reset_cap() -> None:
    global _cap
    _cap = None


def wrap(client: Any) -> Any:
    cap = get_cap()
    return CappedLLM(client, cap) if cap.limit > 0 else client
