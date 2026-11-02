"""The real API with a REAL language model, for the opt-in real-model browser tests (apps/web/e2e-real).

    GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.6-flash python tests/real_server.py 8500

What is real: everything, including the model. What is simplified: the corpus is the committed synthetic one
(`eval/corpus/*.md`) indexed with the hashing embedder (no PyTorch needed), and storage is temporary. The daily
call cap is on, so a runaway test cannot burn a quota.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY to run the real-model server.")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8500
    work = Path(tempfile.mkdtemp(prefix="asm-real-"))
    os.environ.update(
        UPLOAD_DIR=str(work / "uploads"),
        STORE_DIR=str(work / "store"),
        ANALYTICS_DB=str(work / "analytics.db"),
        STUDY_DB=str(work / "study.db"),
        CORS_ORIGINS=os.getenv("E2E_WEB_ORIGIN", "http://localhost:3500"),
        RATE_LIMIT_PER_MIN="100000",
        DAILY_LLM_LIMIT=os.getenv("DAILY_LLM_LIMIT", "200"),
        EMBEDDER="hashing",
        AGENT_ALLOW_WRITES="1",  # a private test server: let the agent save flashcards
    )
    os.chdir(work)
    (work / "uploads").mkdir()
    (work / "data" / "leetcode").mkdir(parents=True)
    src = ROOT / "data" / "leetcode" / "normalized_problems.jsonl"
    if src.exists():
        shutil.copy(src, work / "data" / "leetcode" / "normalized_problems.jsonl")

    from eval.harness import CONFIGS, CORPORA, build_store

    shutil.copytree(build_store(CORPORA["synthetic"], CONFIGS["default-hashing"]), work / "store", dirs_exist_ok=True)

    import uvicorn

    from backend.api import app

    print(f"Real-model API on http://127.0.0.1:{port} (model {os.getenv('GEMINI_MODEL', 'default')}, storage {work})", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":  # the math tool runs in a spawned worker that re-imports this file
    main()
