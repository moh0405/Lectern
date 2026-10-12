import numpy as np

from backend.embeddings import HashingEmbedder, get_embedder, get_embedder_by_name


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder()
    a = e.encode(["a linked list stores nodes"])
    b = e.encode(["a linked list stores nodes"])
    assert a.shape == (1, e.dim) and a.dtype == np.float32
    assert np.array_equal(a, b)
    assert abs(float(np.linalg.norm(a[0])) - 1.0) < 1e-5


def test_hashing_embedder_ranks_related_text_higher():
    e = HashingEmbedder()
    q, near, far = e.encode(["linked list nodes", "a linked list is made of nodes", "dijkstra shortest path graph"])
    assert float(q @ near) > float(q @ far)


def test_hashing_embedder_empty_text_is_zero_vector():
    v = HashingEmbedder().encode([""])
    assert not v.any()


def test_embedder_selection(monkeypatch):
    monkeypatch.setenv("EMBEDDER", "hashing")
    assert get_embedder().name == "hashing-512"
    assert get_embedder_by_name("hashing-256").dim == 256
