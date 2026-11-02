"""Runtime settings for the API, read from the environment once at import.

Kept in a mutable object (not module constants) so tests and deployments can
override individual values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    upload_dir: Path = field(default_factory=lambda: Path(os.getenv("UPLOAD_DIR", "data/uploaded_files")).resolve())
    store_dir: Path = field(default_factory=lambda: Path(os.getenv("STORE_DIR", "data/vector_store")).resolve())
    analytics_db: Path = field(default_factory=lambda: Path(os.getenv("ANALYTICS_DB", "data/analytics.db")).resolve())
    study_db: Path = field(default_factory=lambda: Path(os.getenv("STUDY_DB", "data/study.db")).resolve())
    cors_origins: List[str] = field(
        default_factory=lambda: _csv(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))
    )
    # With a bucket set, the index and study database are kept in S3 (see backend/cloud_sync.py).
    s3_bucket: Optional[str] = field(default_factory=lambda: os.getenv("S3_BUCKET") or None)
    s3_prefix: str = field(default_factory=lambda: os.getenv("S3_PREFIX", "ai-study-mentor"))
    s3_sync_seconds: float = field(default_factory=lambda: float(os.getenv("S3_SYNC_SECONDS", "30")))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    max_files_per_request: int = 10
    rate_limit_per_min: int = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
    # If set, every /api/v1 request must send this value in the X-API-Key header.
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("API_KEY") or None)
    # Lets the tool-using agent call tools that change data (saving flashcards). Off by default, and never settable
    # per request: a public deployment must not let a model write to a shared database.
    agent_allow_writes: bool = field(default_factory=lambda: os.getenv("AGENT_ALLOW_WRITES") == "1")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()

PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".mp4", ".wav", ".m4a"}
