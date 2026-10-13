from backend.rerank import DEFAULT_RERANKER, Reranker, get_reranker


class FakeCrossEncoder:
    """Scores a (query, passage) pair by how many query words the passage contains."""

    def __init__(self):
        self.calls = []

    def predict(self, pairs, batch_size=16, show_progress_bar=False):
        self.calls.append(list(pairs))
        return [sum(w in p.lower() for w in q.lower().split()) for q, p in pairs]


def reranker():
    r = Reranker("fake")
    r._model = FakeCrossEncoder()
    return r


def test_get_reranker_parses_the_environment_value():
    assert get_reranker(None) is None and get_reranker("") is None
    assert all(get_reranker(v) is None for v in ("0", "off", "none", "false", "OFF"))
    assert get_reranker("cross-encoder").model_name == DEFAULT_RERANKER
    assert get_reranker("1").model_name == DEFAULT_RERANKER
    assert get_reranker("my/custom-model").model_name == "my/custom-model"


def test_order_puts_the_best_passage_first_and_is_a_permutation():
    r = reranker()
    passages = ["about trees", "the heap property of a heap", "heap memory"]
    order = r.order("heap property", passages)
    assert order[0] == 1 and sorted(order) == [0, 1, 2]
    assert len(r._model.calls[0]) == 3 and r._model.calls[0][0] == ("heap property", "about trees")


def test_empty_input():
    r = reranker()
    assert r.score("q", []) == [] and r.order("q", []) == []
    assert r._model.calls == []


def test_the_engine_reorders_with_the_reranker_and_survives_its_failure(tmp_path, monkeypatch):
    from backend.embeddings import HashingEmbedder
    from backend.rag_engine import RAGEngine
    from backend.vector_store import VectorStore

    monkeypatch.chdir(tmp_path)
    emb = HashingEmbedder()
    texts = ["trees have nodes", "the heap property orders parents above children", "heap memory is dynamically allocated"]
    store = VectorStore(tmp_path / "s")
    store.set_embedder(emb.name, emb.dim)
    store.add([{"text": t, "doc": "d.pdf", "page": i + 1, "source_type": "pdf"} for i, t in enumerate(texts)], emb.encode(texts), "d")
    store.save()
    eng = RAGEngine(store_dir=str(tmp_path / "s"), embedder=emb, input_dir=str(tmp_path / "in"), retrieval_mode="dense")
    plain = [c["page"] for c in eng.retrieve_context("heap property", k=3)]

    eng._reranker = reranker()
    boosted = eng.retrieve_context("heap property", k=3)
    assert boosted[0]["page"] == 2 and sorted(c["page"] for c in boosted) == [1, 2, 3]
    assert all(-1 <= c["score"] <= 1 for c in boosted)  # still shows cosine similarity, not the reranker's logit

    class Broken:
        def order(self, *a, **k):
            raise RuntimeError("model download failed")

    eng._reranker = Broken()
    assert [c["page"] for c in eng.retrieve_context("heap property", k=3)] == plain  # falls back, never errors
    assert eng._reranker is None
