"""A small in-memory cache of finished answers.

The key includes everything that can change the answer: the question, the study mode, how many passages, the model,
the temperature, and the *version of the index* (which changes whenever a source is added, removed or re-chunked).
So a cached answer is never served for material that has since changed. It exists to save model calls (cost and
latency) when the same question is asked again; `no_cache` on a request asks for a fresh answer.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

Key = Tuple[str, str, int, str, float, str]


def make_key(question: str, mode: Optional[str], k: int, model: Optional[str], temperature: float, store_version: str) -> Key:
    return (" ".join(question.lower().split()), mode or "", k, model or "", round(temperature, 2), store_version)


class AnswerCache:
    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries = max_entries
        self._data: "OrderedDict[Key, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Key) -> Optional[Dict[str, Any]]:
        with self._lock:
            value = self._data.get(key)
            if value is None:
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: Key, value: Dict[str, Any]) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
