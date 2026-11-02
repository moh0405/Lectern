"""API server for the browser end-to-end tests (apps/web/e2e).

The real FastAPI app on real (temporary) storage, with the language model replaced by a scripted
fake so no API key or network is needed. Not used in production.

    python tests/e2e_server.py [port]
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8100
work = Path(tempfile.mkdtemp(prefix="asm-e2e-"))
os.environ.update(
    UPLOAD_DIR=str(work / "uploads"),
    STORE_DIR=str(work / "store"),
    ANALYTICS_DB=str(work / "analytics.db"),
    STUDY_DB=str(work / "study.db"),
    EMBEDDER="hashing",
    CORS_ORIGINS=os.getenv("E2E_WEB_ORIGIN", "http://localhost:3100"),
    RATE_LIMIT_PER_MIN="100000",
    GEMINI_API_KEY="",
)
os.chdir(work)  # relative paths (the LeetCode cache) resolve inside the temp dir
(work / "data" / "leetcode").mkdir(parents=True)
src = ROOT / "data" / "leetcode" / "normalized_problems.jsonl"
if src.exists():
    (work / "data" / "leetcode" / "normalized_problems.jsonl").write_bytes(src.read_bytes())

from tests.fake_gemini import FakeGemini  # noqa: E402

FakeGemini.echo_context = True

import backend.advanced_ai  # noqa: E402
import backend.api.routers.agent  # noqa: E402
import backend.api.routers.ask  # noqa: E402
import backend.leetcode_handler  # noqa: E402
import backend.api.routers.tracking  # noqa: E402
import backend.llm_providers  # noqa: E402

for module in (backend.llm_providers, backend.api.routers.ask, backend.api.routers.agent, backend.api.routers.tracking, backend.advanced_ai, backend.leetcode_handler):
    module.create_llm = FakeGemini

import uvicorn  # noqa: E402

from backend.api import app  # noqa: E402

if __name__ == "__main__":
    print(f"e2e storage: {work}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
