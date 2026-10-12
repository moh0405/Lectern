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


def test_cached_load_makes_no_network_calls_and_does_not_rewrite(tmp_path, monkeypatch):
    shutil.copy(NORMALIZED, tmp_path / "normalized_problems.jsonl")
    before = (tmp_path / "normalized_problems.jsonl").read_bytes()

    def boom(*a, **k):
        raise AssertionError("must not hit the network or re-parse when a cache exists")

    h = LeetCodeHandler(cache_dir=str(tmp_path))
    for name in ("_try_load_huggingface", "_try_load_kaggle_competition", "_try_load_local_files"):
        monkeypatch.setattr(h, name, boom)
    n, _ = h.load_all(generate_embeddings=False)
    assert n > 1000
    assert (tmp_path / "normalized_problems.jsonl").read_bytes() == before


def test_topics_are_parsed_from_related_topics_column(tmp_path):
    kaggle = tmp_path / "kaggle"
    kaggle.mkdir()
    (kaggle / "lc.csv").write_text(
        "id,title,description,difficulty,related_topics,url\n"
        '1,Two Sum,"Find two numbers.",Easy,"Array,Hash Table",https://leetcode.com/problems/two-sum\n'
        '2,Empty Topics,"Something.",Hard,,https://leetcode.com/problems/x\n',
        encoding="utf-8",
    )
    h = LeetCodeHandler(cache_dir=str(tmp_path))
    assert h.rebuild_from_local() == 2
    h.load_all(generate_embeddings=False)
    by_title = {p.title: p for p in h._problems}
    assert by_title["Two Sum"].topics == ["Array", "Hash Table"]
    assert by_title["Empty Topics"].topics == []
    assert [r["title"] for r in h.search("numbers", topics=["Hash Table"])] == ["Two Sum"]


def test_shipped_dataset_has_topics():
    import json

    rows = [json.loads(line) for line in NORMALIZED.read_text(encoding="utf-8").splitlines()]
    with_topics = sum(1 for r in rows if r["topics"])
    assert with_topics > 0.8 * len(rows)
