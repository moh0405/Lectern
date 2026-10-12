"""In-memory background jobs for slow work (indexing PDFs, fetching URLs, transcribing audio).

Single worker on purpose: indexing mutates one shared store, so jobs run one at a time.
Job records live in memory; they are gone after a restart (the index itself is persisted).
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

MAX_JOBS_KEPT = 200


class JobManager:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Callable[[str], None]], Dict[str, Any]]) -> str:
        """Run `fn(progress)` in the background; `fn` returns a JSON-serializable result."""
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "kind": kind, "status": "queued", "progress": [], "result": None,
               "error": None, "created_at": time.time(), "finished_at": None}
        with self._lock:
            self._jobs[job_id] = job
            if len(self._jobs) > MAX_JOBS_KEPT:
                for old in sorted(self._jobs.values(), key=lambda j: j["created_at"])[: len(self._jobs) - MAX_JOBS_KEPT]:
                    if old["status"] in {"done", "failed"}:
                        self._jobs.pop(old["id"], None)

        def progress(msg: str) -> None:
            with self._lock:
                job["progress"].append(msg)

        def run() -> None:
            with self._lock:
                job["status"] = "running"
            try:
                result = fn(progress)
                with self._lock:
                    job["result"], job["status"] = result, "done"
            except Exception as e:  # reported to the client, not raised
                with self._lock:
                    job["error"], job["status"] = str(e), "failed"
            finally:
                with self._lock:
                    job["finished_at"] = time.time()

        self._pool.submit(run)
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else {**job, "progress": list(job["progress"])}

    def wait(self, job_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Block until the job finishes (used by tests)."""
        end = time.time() + timeout
        while time.time() < end:
            job = self.get(job_id)
            if job is None or job["status"] in {"done", "failed"}:
                return job
            time.sleep(0.02)
        return self.get(job_id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
