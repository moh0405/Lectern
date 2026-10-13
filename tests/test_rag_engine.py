import pytest

from backend.embeddings import HashingEmbedder
from backend.rag_engine import RAGEngine
from backend.vector_store import VectorStore

EMB = HashingEmbedder()

CHUNKS = [
    {"text": "A linked list is a linear data structure of nodes with pointers.", "doc": "ds.pdf", "page": 3},
    {"text": "A hash table maps keys to values using a hash function.", "doc": "ds.pdf", "page": 9},
    {"text": "Dijkstra finds shortest paths in graphs with non-negative weights.", "doc": "algo.pdf", "page": 1},
]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """Engine over a small hashing-embedded store, in an empty working dir."""
    monkeypatch.chdir(tmp_path)
    store = VectorStore(tmp_path / "store")
    store.set_embedder(EMB.name, EMB.dim)
    chunks = [{**c, "source_type": "pdf"} for c in CHUNKS]
    store.add(chunks, EMB.encode([c["text"] for c in chunks]), "src")
    store.save()
    return RAGEngine(store_dir=str(tmp_path / "store"), embedder=EMB, input_dir=str(tmp_path / "in"))


@pytest.fixture
def keyword_engine(engine):
    engine.use_embeddings = False
    return engine


def test_empty_store_has_no_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    eng = RAGEngine(store_dir=str(tmp_path / "store"), input_dir=str(tmp_path / "in"))
    assert eng._docstore_iter() == []
    assert eng.retrieve_context("anything") == []


def test_semantic_retrieval_ranks_relevant_chunk_first(engine):
    engine.retrieval_mode = "dense"
    results = engine.retrieve_context("how does a hash table map keys to values", k=2)
    assert engine.semantic_ready
    assert results[0]["doc"] == "ds.pdf" and results[0]["page"] == 9
    assert results[0]["score"] >= results[1]["score"]


def test_keyword_retrieval_ranks_relevant_chunk_first(keyword_engine):
    results = keyword_engine.retrieve_context("what is a linked list", k=3)
    assert results[0]["doc"] == "ds.pdf" and results[0]["page"] == 3
    assert not keyword_engine.semantic_ready


def test_keyword_retrieval_scores_are_per_result(keyword_engine):
    results = keyword_engine.retrieve_context("linked list nodes pointers hash", k=3)
    scores = [r["score"] for r in results]
    assert len(set(scores)) > 1 and scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1 for s in scores)


def test_keyword_retrieval_ignores_stopwords_and_non_matches(keyword_engine):
    assert keyword_engine.retrieve_context("what is the of a", k=3) == []
    assert keyword_engine.retrieve_context("quantum chromodynamics", k=3) == []


def test_store_built_with_other_embedder_falls_back_to_keyword(engine):
    engine._embedder = HashingEmbedder(dim=256)  # name differs from the store's
    results = engine.retrieve_context("linked list", k=1)
    assert results and not engine.semantic_ready
    assert results[0]["doc"] == "ds.pdf"


def test_reload_picks_up_changes_on_disk(engine, tmp_path):
    other = VectorStore.load(tmp_path / "store")
    other.add(
        [{"text": "a heap is a priority queue", "doc": "new.pdf", "page": 1, "source_type": "pdf"}],
        EMB.encode(["a heap is a priority queue"]),
        "new.pdf",
    )
    other.save()
    assert "new.pdf" not in engine.store.docs()
    engine.reload()
    assert "new.pdf" in engine.store.docs()


def test_shared_returns_one_instance_per_store(tmp_path):
    RAGEngine.clear_shared()
    a = RAGEngine.shared(store_dir=str(tmp_path / "s"))
    assert RAGEngine.shared(store_dir=str(tmp_path / "s")) is a
    assert RAGEngine.shared(store_dir=str(tmp_path / "other")) is not a
    RAGEngine.clear_shared()


@pytest.mark.parametrize(
    ("mode", "marker"),
    [
        ("eli5", "ELI5"),
        ("technical", "Technical mode"),
        ("interview", "Interview Prep mode"),
        ("summary", "Quick Summary mode"),
        (None, "Computer Science tutor"),
    ],
)
def test_prompt_modes(engine, mode, marker):
    chunks = engine.retrieve_context("hash table maps keys", k=1)
    prompt = engine.generate_prompt("What is a hash table?", chunks, mode=mode)
    assert marker in prompt
    assert "What is a hash table?" in prompt
    assert "[ds.pdf (page 9)]" in prompt


def test_format_context_cites_doc_and_page(engine):
    out = engine.format_context(CHUNKS[:1])
    assert out.startswith("- [ds.pdf (page 3)]")


def test_results_carry_citation_url_with_timestamp(tmp_path):
    store = VectorStore(tmp_path / "s")
    store.set_embedder(EMB.name, EMB.dim)
    chunk = {"text": "binary search halves the range", "doc": "Lecture", "page": None, "source_type": "youtube",
             "url": "https://youtu.be/abc", "extra": {"citation_url": "https://www.youtube.com/watch?v=abc&t=95s"}}
    store.add([chunk], EMB.encode([chunk["text"]]), "https://youtu.be/abc")
    eng = RAGEngine(store_dir=str(tmp_path / "s"), embedder=EMB, input_dir=str(tmp_path / "in"))
    eng.store = store
    hit = eng.retrieve_context("binary search", k=1)[0]
    assert hit["citation_url"].endswith("&t=95s") and hit["url"] == "https://youtu.be/abc"


class SemanticStub:
    """Pretends to be a real (non-hashing) embedder so the engine's auto mode picks hybrid search."""

    name = "stub-semantic"

    def __init__(self):
        self._inner = EMB
        self.dim = EMB.dim

    def encode(self, texts):
        return self._inner.encode(texts)


def make_store(tmp_path, embedder_name, chunks):
    store = VectorStore(tmp_path / "s")
    store.set_embedder(embedder_name, EMB.dim)
    store.add([{**c, "source_type": "pdf"} for c in chunks], EMB.encode([c["text"] for c in chunks]), "src")
    store.save()
    return tmp_path / "s"


def test_auto_uses_bm25_with_a_non_semantic_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = make_store(tmp_path, EMB.name, CHUNKS)
    eng = RAGEngine(store_dir=str(d), embedder=EMB, input_dir=str(tmp_path / "in"))
    assert eng.retrieval_mode == "auto"
    res = eng.retrieve_context("linked list nodes pointers", k=3)
    assert res[0]["doc"] == "ds.pdf" and res[0]["page"] == 3
    assert all(0 < r["score"] <= 1 for r in res)  # normalized BM25
    assert eng.retrieve_context("quantum chromodynamics") == []


def test_auto_uses_hybrid_with_a_semantic_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub = SemanticStub()
    d = make_store(tmp_path, stub.name, CHUNKS)
    eng = RAGEngine(store_dir=str(d), embedder=stub, input_dir=str(tmp_path / "in"))
    # a keyword the vectors cannot know about is found by the BM25 half
    extra = [{"text": "Zygomorphic flowers are bilaterally symmetric.", "doc": "bio.pdf", "page": 1}]
    eng.store.add([{**c, "source_type": "pdf"} for c in extra], EMB.encode([extra[0]["text"]]), "bio")
    res = eng.retrieve_context("zygomorphic", k=3)
    assert res[0]["doc"] == "bio.pdf"
    assert all(-1.0 <= r["score"] <= 1.0 for r in res)  # cosine similarity is what is shown


def test_forced_modes_and_fallback_without_an_embedder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = make_store(tmp_path, EMB.name, CHUNKS)
    eng = RAGEngine(store_dir=str(d), embedder=EMB, input_dir=str(tmp_path / "in"), retrieval_mode="dense")
    assert eng.retrieve_context("dijkstra shortest paths graph", k=1)[0]["doc"] == "algo.pdf"
    eng.retrieval_mode = "hybrid"
    assert eng.retrieve_context("dijkstra shortest paths graph", k=1)[0]["doc"] == "algo.pdf"
    eng.use_embeddings = False  # dense/hybrid fall back to BM25 when no embedder is available
    eng.retrieval_mode = "dense"
    assert eng.retrieve_context("dijkstra shortest paths graph", k=1)[0]["doc"] == "algo.pdf"


def test_bm25_index_is_rebuilt_when_the_store_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = make_store(tmp_path, EMB.name, CHUNKS)
    eng = RAGEngine(store_dir=str(d), embedder=EMB, input_dir=str(tmp_path / "in"), retrieval_mode="bm25")
    assert eng.retrieve_context("zygomorphic") == []
    eng.store.add(
        [{"text": "Zygomorphic flowers are bilaterally symmetric.", "doc": "bio.pdf", "page": 1, "source_type": "pdf"}],
        EMB.encode(["Zygomorphic flowers are bilaterally symmetric."]), "bio",
    )
    assert eng.retrieve_context("zygomorphic")[0]["doc"] == "bio.pdf"
    eng.remove_source("bio", save=False)
    assert eng.retrieve_context("zygomorphic") == []


def test_source_labels_match_what_a_model_should_cite(engine):
    assert engine.source_label({"doc": "a.pdf", "page": 12}) == "a.pdf (page 12)"
    assert engine.source_label({"doc": "a.pdf", "page": 12, "end_page": 13}) == "a.pdf (pages 12-13)"
    assert engine.source_label({"doc": "a.pdf", "page": 12, "end_page": 12}) == "a.pdf (page 12)"
    assert engine.source_label({"doc": "Lecture on heaps", "page": None}) == "Lecture on heaps"  # never "(page None)"
    ctx = engine.format_context([{"doc": "notes.md", "page": None, "text": "t"}])
    assert ctx == "- [notes.md] t" and "None" not in ctx


def test_the_labels_in_the_prompt_are_accepted_by_the_citation_checker(engine):
    from backend.citations import extract_citations

    chunks = [{"doc": "Dsa.pdf", "page": 12, "end_page": 13, "text": "x"}, {"doc": "notes.md", "page": None, "text": "y"}]
    prompt_labels = [engine.source_label(c) for c in chunks]
    answer = " and ".join(f"[{label}]" for label in prompt_labels)
    assert [c.status for c in extract_citations(answer, chunks)] == ["ok", "ok"]


def test_parse_questions_keeps_only_question_shaped_lines():
    reply = (
        "Here are some questions:\n"
        "1. What is a hash table?\n"
        "2) How does BFS differ from DFS?\n"
        "- Why is merge sort stable?\n"
        "* **When** should I use a heap?\n"
        "| Data structure | queue | stack |\n"
        "|---|---|---|\n"
        "Both visit every vertex in O(V + E) time; the difference is the order of exploration.\n"
        "3. Explain recursion.\n"
        "4. What is a hash table?\n"
        "5. ok?\n"
    )
    qs = RAGEngine.parse_questions(reply, 10)
    assert qs == ["What is a hash table?", "How does BFS differ from DFS?", "Why is merge sort stable?", "When should I use a heap?"]
    assert RAGEngine.parse_questions(reply, 2) == qs[:2]
    assert RAGEngine.parse_questions("", 5) == [] and RAGEngine.parse_questions("just prose, no questions", 5) == []


def test_suggestions_ignore_a_reply_with_no_usable_questions(engine, monkeypatch):
    import backend.llm_providers as cfg

    class Rambler:
        def __init__(self, **kw):
            pass

        def generate(self, prompt, temperature=None, json_mode=False):
            return {"ok": True, "model": "x", "answer": "| a | b |\n|---|---|\nSome prose without any question."}

    monkeypatch.setattr(cfg, "create_llm", Rambler)
    qs = engine.generate_query_suggestions(max_questions=3)
    assert len(qs) == 3 and all(q.endswith(("?",)) or q for q in qs) and "|" not in "".join(qs)
