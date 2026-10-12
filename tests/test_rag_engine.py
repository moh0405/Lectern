import pytest

from backend.rag_engine import RAGEngine

CHUNKS = [
    {"text": "A linked list is a linear data structure of nodes with pointers.", "doc": "ds.pdf", "page": 3},
    {"text": "A hash table maps keys to values using a hash function.", "doc": "ds.pdf", "page": 9},
    {"text": "Dijkstra finds shortest paths in graphs with non-negative weights.", "doc": "algo.pdf", "page": 1},
]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    # Run in an empty dir so the engine does not scan any local PDFs.
    monkeypatch.chdir(tmp_path)
    eng = RAGEngine(store_dir=str(tmp_path / "store"), auto_embeddings=False)
    eng.meta = {"metadata": [dict(c) for c in CHUNKS]}
    return eng


def test_empty_store_has_no_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    eng = RAGEngine(store_dir=str(tmp_path / "store"), auto_embeddings=False)
    assert eng._docstore_iter() == []


def test_keyword_retrieval_ranks_relevant_chunk_first(engine):
    results = engine.retrieve_context("what is a linked list", k=2)
    assert len(results) == 2
    assert results[0]["doc"] == "ds.pdf" and results[0]["page"] == 3


@pytest.mark.xfail(reason="Phase 1: keyword fallback reports the top score for every result", strict=True)
def test_keyword_retrieval_scores_are_per_result(engine):
    results = engine.retrieve_context("what is a linked list", k=3)
    assert results[0]["score"] > results[-1]["score"]


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
    chunks = engine.retrieve_context("hash table", k=1)
    prompt = engine.generate_prompt("What is a hash table?", chunks, mode=mode)
    assert marker in prompt
    assert "What is a hash table?" in prompt
    assert "[ds.pdf (page 9)]" in prompt


def test_format_context_cites_doc_and_page(engine):
    out = engine.format_context(CHUNKS[:1])
    assert out.startswith("- [ds.pdf (page 3)]")
