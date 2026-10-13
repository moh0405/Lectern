"""A daily ceiling on language-model calls, so a leaked or abused endpoint cannot run up the bill.

Set ``DAILY_LLM_LIMIT`` (0 or unset means no limit). Each call to the model counts once, whichever
feature made it. With ``S3_BUCKET`` set the count lives in S3 (``<prefix>/usage/<UTC date>.json``) so it
survives restarts and is shared by every copy of the function; otherwise it is kept in memory.

If the count cannot be read or saved, the call is refused: when money is at stake the safe failure is
to stop. The S3 read-then-write is not atomic, so two calls in the same instant can both count as one;
the cap is a guard rail (off by a few at most), not an accounting system.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

MESSAGE = "Daily limit of {limit} model calls reached. Try again after midnight UTC."


class DailyLimitReached(RuntimeError):
    pass


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

    def _load(self, day: str) -> int:
        if not self.s3:
            return self._memory.get(day, 0)
        try:
            body = self.s3.get_object(Bucket=self.bucket, Key=self._key(day))["Body"].read()
        except Exception as e:
            if getattr(e, "response", {}).get("Error", {}).get("Code", "") in ("NoSuchKey", "404"):
                return 0
            raise
        return int(json.loads(body).get("calls", 0))

    def _save(self, day: str, calls: int) -> None:
        if not self.s3:
            self._memory = {day: calls}
            return
        self.s3.put_object(Bucket=self.bucket, Key=self._key(day), Body=json.dumps({"calls": calls}).encode())

    def reserve(self) -> int:
        """Count one call. Raises DailyLimitReached when today's allowance is used up. Returns calls used today."""
        if self.limit <= 0:
            return 0
        with self._lock:
            day = self._today()
            try:
                used = self._load(day)
                if used >= self.limit:
                    raise DailyLimitReached(MESSAGE.format(limit=self.limit))
                self._save(day, used + 1)
            except DailyLimitReached:
                raise
            except Exception as e:
                raise DailyLimitReached(f"Model calls are paused because the daily count could not be checked ({e}).") from e
            return used + 1


class CappedLLM:
    """Wraps any provider so each ``generate`` or ``stream`` is counted before it reaches the model."""

    def __init__(self, inner: Any, cap: DailyCap):
        self._inner = inner
        self._cap = cap

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
