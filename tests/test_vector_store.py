import numpy as np
import pytest

from backend import vector_store as vs
from backend.embeddings import HashingEmbedder
from backend.vector_store import VectorStore, chunk_hash

EMB = HashingEmbedder()


def make_chunks(doc, texts, source_type="pdf"):
    return [{"text": t, "doc": doc, "page": i + 1, "source_type": source_type} for i, t in enumerate(texts)]


def fill(store, doc, texts, key=None):
    chunks = make_chunks(doc, texts)
    store.set_embedder(EMB.name, EMB.dim)
    return store.add(chunks, EMB.encode(texts), key or doc)


@pytest.fixture
def store(tmp_path):
    s = VectorStore(tmp_path / "store")
    fill(s, "ds.pdf", ["a linked list is a chain of nodes", "a hash table maps keys to values"])
    fill(s, "algo.pdf", ["dijkstra finds shortest paths in a graph"])
    return s


def test_add_and_search_returns_best_chunk(store):
    qv = EMB.encode(["how does a hash table map keys"])[0]
    (idx, score), *_ = store.search(qv, k=2)
    assert store.chunks[idx]["doc"] == "ds.pdf" and "hash table" in store.chunks[idx]["text"]
    assert 0 < score <= 1.0001


def test_duplicate_chunks_are_not_added_twice(store):
    before = len(store)
    assert fill(store, "ds.pdf", ["a linked list is a chain of nodes"]) == 0
    assert len(store) == before


def test_remove_source_and_doc(store):
    assert store.remove_source("algo.pdf") == 1
    assert store.docs() == ["ds.pdf"]
    assert "algo.pdf" not in store.sources
    assert store.remove_doc("ds.pdf") == 2
    assert len(store) == 0 and store.embeddings.shape[0] == 0


def test_save_load_roundtrip(store, tmp_path):
    store.save()
    for name in ("manifest.json", "chunks.jsonl", "embeddings.npy"):
        assert (store.dir / name).exists()
    assert not list(store.dir.glob("*.pkl"))
    loaded = VectorStore.load(store.dir)
    assert len(loaded) == len(store)
    assert loaded.embedder_name == EMB.name
    assert np.allclose(loaded.embeddings, store.embeddings)
    qv = EMB.encode(["shortest path"])[0]
    assert loaded.search(qv, 1)[0][0] == store.search(qv, 1)[0][0]


def test_load_missing_or_corrupt_store_is_empty(tmp_path):
    assert len(VectorStore.load(tmp_path / "nope")) == 0
    d = tmp_path / "bad"
    d.mkdir()
    (d / "manifest.json").write_text("{not json")
    (d / "chunks.jsonl").write_text("")
    np.save(d / "embeddings.npy", np.zeros((0, 4), dtype=np.float32))
    assert len(VectorStore.load(d)) == 0


def test_embedder_mismatch_is_rejected(store):
    with pytest.raises(ValueError, match="rebuild"):
        store.set_embedder("some-other-model", 384)


def test_search_dimension_mismatch_raises(store):
    with pytest.raises(ValueError):
        store.search(np.ones(7, dtype=np.float32), 1)


def test_chunk_hash_depends_on_source_and_text():
    a = {"text": "x", "doc": "d", "page": 1, "source_type": "pdf"}
    assert chunk_hash(a) == chunk_hash(dict(a))
    assert chunk_hash(a) != chunk_hash({**a, "page": 2})
    assert chunk_hash(a) != chunk_hash({**a, "text": "y"})


@pytest.mark.skipif(vs.faiss is None, reason="faiss not installed")
def test_faiss_and_numpy_agree(store, tmp_path, monkeypatch):
    qv = EMB.encode(["linked list nodes"])[0]
    with_faiss = store.search(qv, 3)
    assert store.uses_faiss
    store.save()
    assert (store.dir / "index.faiss").exists()
    reloaded = VectorStore.load(store.dir)
    assert reloaded._index is not None  # persisted index is reused
    monkeypatch.setattr(vs, "faiss", None)
    without = VectorStore.load(store.dir).search(qv, 3)
    # ties may be ordered differently, so compare the best hit and the score profile
    assert with_faiss[0][0] == without[0][0]
    assert np.allclose(sorted(s for _, s in with_faiss), sorted(s for _, s in without), atol=1e-5)
