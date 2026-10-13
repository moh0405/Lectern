import pytest

from backend.lexical import BM25Index, reciprocal_rank_fusion, stem, tokenize


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("collisions", "collision"), ("queries", "query"), ("hashes", "hash"), ("tables", "table"),
        ("caches", "cache"), ("sorting", "sort"), ("sorted", "sort"), ("running", "run"), ("trees", "tree"),
        ("graphs", "graph"), ("queues", "queue"), ("nodes", "node"),
    ],
)
def test_inflections_share_a_stem(a, b):
    assert stem(a) == stem(b)


@pytest.mark.parametrize("word", ["class", "status", "analysis", "bus", "O1", "123", "dfs", "heap"])
def test_stemmer_leaves_these_alone(word):
    assert stem(word) == word or word == "O1" and stem(word) == "O1"


def test_unrelated_words_stay_apart():
    assert len({stem(w) for w in ["sort", "sword", "port", "heap", "hash", "stack"]}) == 6


def test_tokenize_drops_stopwords_and_lowercases():
    assert tokenize("What IS the Heap property?") == ["heap", "property"]
    assert tokenize("") == []


DOCS = [
    "A hash table stores keys in buckets and resolves collisions by chaining.",
    "Dijkstra's algorithm finds shortest paths using a priority queue.",
    "Breadth-first search explores a graph level by level using a queue.",
    "The heap property says every parent is smaller than its children.",
    "A heap in memory is the region used for dynamic allocation.",
    "Sorting algorithms such as quicksort and mergesort run in n log n time.",
]


def test_exact_terms_rank_first():
    idx = BM25Index(DOCS)
    assert idx.search("hash collisions", k=3)[0][0] == 0
    assert idx.search("shortest path", k=3)[0][0] == 1  # "paths" matches "path"
    assert idx.search("sorting", k=3)[0][0] == 5


def test_rare_terms_outweigh_common_ones():
    idx = BM25Index(DOCS)
    top = idx.search("queue dijkstra", k=3)
    assert top[0][0] == 1  # "dijkstra" appears once, "queue" in two documents


def test_scores_are_normalized_and_non_matches_are_absent():
    idx = BM25Index(DOCS)
    res = idx.search("heap property", k=6)
    assert all(0 < s <= 1 for _, s in res)
    assert res[0][0] == 3 and res[0][1] > res[1][1]
    assert idx.search("kubernetes ingress", k=5) == []
    assert BM25Index([]).search("anything") == []


def test_scores_are_comparable_across_queries():
    idx = BM25Index(DOCS)
    full = idx.search("hash table collisions chaining", k=1)[0][1]
    partial = idx.search("hash banana spaceship", k=1)[0][1]
    assert full > partial


def test_longer_passages_are_discounted():
    short = "heap property"
    long = "heap property " + "unrelated filler words " * 60
    res = BM25Index([long, short]).search("heap property", k=2)
    assert res[0][0] == 1


def test_reciprocal_rank_fusion():
    fused = reciprocal_rank_fusion([[1, 2], [2, 3]])
    ids = [i for i, _ in fused]
    assert ids[0] == 2  # it is the only id in both lists
    assert set(ids) == {1, 2, 3}
    scores = dict(fused)
    assert scores[2] == pytest.approx(1 / 62 + 1 / 61) and scores[1] == pytest.approx(1 / 61)
    assert scores[1] > scores[3]  # rank 1 in one list beats rank 2 in the other
    assert reciprocal_rank_fusion([]) == []
