"""Keep the search index and the study database in S3 so a container can be replaced without losing them.

Container disks are wiped on every redeploy. With ``S3_BUCKET`` set, the API pulls the saved files
at startup (only the ones missing locally) and a background thread pushes changed files every
``S3_SYNC_SECONDS``, plus once more on shutdown. Without ``S3_BUCKET`` nothing here runs.

On AWS Lambda the process is frozen between requests, so a background thread cannot be trusted. There
(``AWS_LAMBDA_FUNCTION_NAME`` is set) the API instead saves right after every request that changes data.
Work that continues after a response, such as indexing a new source in the background, can be cut off;
build the index locally and upload it with ``python -m backend.cloud_sync push``.

Files are tracked by (size, mtime). The SQLite database is copied with SQLite's own backup API
first, so a half-written page is never uploaded. In the index, ``manifest.json`` is uploaded last
and downloaded last: it is the file that says which version of the other two is current.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ai-study-mentor.cloud")

ON_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
INDEX_FILES = ["embeddings.npy", "chunks.jsonl", "index.faiss", "manifest.json"]  # manifest last, on purpose


def _client() -> Any:
    try:
        import boto3
    except ImportError as e:  # pragma: no cover - depends on the optional extra
        raise RuntimeError("S3 sync needs boto3: pip install 'ai-study-mentor[aws]'") from e
    return boto3.client("s3")


class S3Sync:
    def __init__(self, bucket: str, prefix: str, store_dir: Path, study_db: Path, client: Optional[Any] = None):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.store_dir = Path(store_dir)
        self.study_db = Path(study_db)
        self.s3 = client or _client()
        self._seen: Dict[str, Tuple[int, int]] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _key(self, *parts: str) -> str:
        return "/".join(p for p in (self.prefix, *parts) if p)

    def _targets(self) -> List[Tuple[Path, str]]:
        files = [(self.store_dir / name, self._key("index", name)) for name in INDEX_FILES]
        return files + [(self.study_db, self._key("study.db"))]

    @staticmethod
    def _stamp(path: Path) -> Tuple[int, int]:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)

    def _exists_remote(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def pull(self) -> List[str]:
        """Download whatever is saved remotely and missing here. Returns the files fetched."""
        fetched = []
        for path, key in self._targets():
            if path.exists() or not self._exists_remote(key):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".part")
            self.s3.download_file(self.bucket, key, str(tmp))
            os.replace(tmp, path)
            self._seen[str(path)] = self._stamp(path)
            fetched.append(path.name)
        if fetched:
            logger.info("Restored from s3://%s/%s: %s", self.bucket, self.prefix, ", ".join(fetched))
        return fetched

    def push(self) -> List[str]:
        """Upload files that changed since the last pass. Returns the files sent."""
        sent = []
        for path, key in self._targets():
            if not path.exists():
                continue
            stamp = self._stamp(path)
            if self._seen.get(str(path)) == stamp:
                continue
            if path == self.study_db:
                self._upload_db(path, key)
            else:
                self.s3.upload_file(str(path), self.bucket, key)
            self._seen[str(path)] = stamp
            sent.append(path.name)
        if sent:
            logger.info("Saved to s3://%s/%s: %s", self.bucket, self.prefix, ", ".join(sent))
        return sent

    def _upload_db(self, path: Path, key: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "study.db"
            src, dst = sqlite3.connect(path), sqlite3.connect(copy)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            self.s3.upload_file(str(copy), self.bucket, key)

    def start(self, interval: float) -> None:
        def loop() -> None:
            while not self._stop.wait(interval):
                try:
                    self.push()
                except Exception as e:  # a failed pass is retried next time; it must not kill the thread
                    logger.warning("S3 sync failed: %s", e)

        self._thread = threading.Thread(target=loop, name="s3-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        try:
            self.push()
        except Exception as e:
            logger.warning("Final S3 sync failed: %s", e)


def load_secret_env(client: Optional[Any] = None) -> None:
    """If ``GEMINI_SECRET_ID`` names a Secrets Manager secret and ``GEMINI_API_KEY`` is unset, fetch it.

    Lambda cannot inject secrets as environment variables the way App Runner can, so the code asks for it.
    """
    secret_id = os.getenv("GEMINI_SECRET_ID")
    if not secret_id or os.getenv("GEMINI_API_KEY"):
        return
    if client is None:
        import boto3

        client = boto3.client("secretsmanager")
    os.environ["GEMINI_API_KEY"] = client.get_secret_value(SecretId=secret_id)["SecretString"].strip()


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m backend.cloud_sync push|pull``: copy the index and study database to or from S3."""
    import argparse

    from .api.settings import settings

    ap = argparse.ArgumentParser(prog="python -m backend.cloud_sync", description=main.__doc__)
    ap.add_argument("action", choices=["push", "pull"])
    args = ap.parse_args(argv)
    if not settings.s3_bucket:
        ap.error("S3_BUCKET is not set")
    sync = S3Sync(settings.s3_bucket, settings.s3_prefix, settings.store_dir, settings.study_db)
    done = sync.push() if args.action == "push" else sync.pull()
    print(f"{args.action}: {', '.join(done) or 'nothing to do'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
