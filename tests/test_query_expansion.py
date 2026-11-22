import pytest

from backend.embeddings import HashingEmbedder
from backend.query_expansion import expand_query, expansions
from backend.rag_engine import RAGEngine
from backend.vector_store import VectorStore


# ----------------------------------------------------------------------------- expansion
def test_bfs_and_dfs_expand_to_graph_search():
    """The live failure: "DFS" next to "BFS" means depth-first search, not distributed file system."""
    assert expansions("Difference between BFS and DFS") == ["breadth-first search", "depth-first search"]
    assert expansions("BFS vs DFS?") == ["breadth-first search", "depth-first search"]


def test_dfs_follows_its_context():
    assert expansions("How does DFS traverse a graph?") == ["depth-first search"]
    assert expansions("How does a DFS replicate files across servers?") == ["distributed file system"]


def test_bare_ambiguous_acronym_keeps_every_sense():
    assert expansions("What is DFS?") == ["depth-first search", "distributed file system"]


def test_expand_query_appends_and_leaves_the_question_intact():
    q = "Difference between BFS and DFS"
    assert expand_query(q) == f"{q} (breadth-first search; depth-first search)"


@pytest.mark.parametrize("q", ["", "What is a linked list?", "Explain breadth-first search (BFS)", "user ids and passwords"])
def test_nothing_to_add_returns_the_query_unchanged(q):
    assert expand_query(q) == q


def test_does_not_repeat_a_spelled_out_form_already_present():
    assert expansions("Is BFS the same as breadth-first search?") == []


def test_acronyms_match_whole_words_only():
    assert expansions("Who wrote the dpkg tool and osmosis?") == []


def test_concept_words_are_not_expanded():
    """Synonyms for concepts measured no gain and hurt a question about one specific strategy (eval s02)."""
    assert expansions("How do hash tables handle collisions?") == []
    assert expansions("How does separate chaining resolve hash collisions?") == []


def test_expansion_is_deterministic():
    q = "Compare DFS, BFS and DP on a DAG"
    assert expand_query(q) == expand_query(q)
    assert expansions(q) == ["depth-first search", "breadth-first search", "dynamic programming", "directed acyclic graph"]


# ----------------------------------------------------------------------------- in the engine
EMB = HashingEmbedder()
CHUNKS = [
    # distributed file systems share the acronym, and say "DFS" over and over
    "A distributed file system (DFS) stores files on multiple servers. A DFS hides where files live.",
    "DFS replication keeps copies of each file on several DFS servers so the DFS survives failures.",
    "DFS clients cache files; the DFS must keep the caches consistent.",
    "Depth-first search explores a graph as far as possible along each branch before backtracking.",
    "Breadth-first search explores a graph level by level from the start vertex using a queue.",
]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = VectorStore(tmp_path / "store")
    store.set_embedder(EMB.name, EMB.dim)
    chunks = [{"text": t, "doc": "book.pdf", "page": i + 1, "source_type": "pdf"} for i, t in enumerate(CHUNKS)]
    store.add(chunks, EMB.encode(CHUNKS), "src")
    store.save()
    return RAGEngine(store_dir=str(tmp_path / "store"), embedder=EMB, input_dir=str(tmp_path / "in"))


def _pages(chunks):
    return [c["page"] for c in chunks]


@pytest.mark.parametrize("mode", ["bm25", "dense", "hybrid"])
def test_bfs_vs_dfs_retrieves_both_graph_searches(engine, mode):
    engine.retrieval_mode = mode
    pages = _pages(engine.retrieve_context("Difference between BFS and DFS", k=2))
    assert sorted(pages) == [4, 5]


def test_without_expansion_bfs_vs_dfs_retrieves_file_systems(engine):
    """Documents the failure the expansion fixes (BM25 sees only the token "dfs")."""
    engine.retrieval_mode = "bm25"
    engine.query_expansion = False
    assert 4 not in _pages(engine.retrieve_context("Difference between BFS and DFS", k=2))


def test_keyword_baseline_is_left_unexpanded(engine):
    engine.retrieval_mode = "keyword"
    assert engine.retrieve_context("BFS", k=3) == []  # no chunk contains the token "bfs"


def test_flags_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert RAGEngine(store_dir=str(tmp_path / "s")).query_expansion is True
    monkeypatch.setenv("QUERY_EXPANSION", "0")
    assert RAGEngine(store_dir=str(tmp_path / "s")).query_expansion is False

