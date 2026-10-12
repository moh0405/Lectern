import shutil
from pathlib import Path

import pytest

from backend.leetcode_handler import LeetCodeHandler

NORMALIZED = Path(__file__).resolve().parents[1] / "data" / "leetcode" / "normalized_problems.jsonl"


@pytest.fixture
def handler(tmp_path):
    if not NORMALIZED.exists():
        pytest.skip("normalized_problems.jsonl not present")
    shutil.copy(NORMALIZED, tmp_path / "normalized_problems.jsonl")
    h = LeetCodeHandler(cache_dir=str(tmp_path))
    h.load_all(generate_embeddings=False)
    return h


def test_loads_and_dedupes(handler):
    stats = handler.get_stats()
    assert stats["total"] > 1000
    assert {"Easy", "Medium", "Hard"} & set(stats["by_difficulty"])


def test_keyword_search_with_difficulty_filter(handler):
    results = handler.search("two sum array hash", top_k=5, difficulty=["Easy"])
    assert results
    assert all(r["difficulty"].lower() == "easy" for r in results)
