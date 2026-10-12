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
