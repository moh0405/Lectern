"""The concept map and multi-document synthesis are grounded in passages about the requested topic, and synthesis
citations are checked against the passages the model was given. Uses FakeGemini; no network."""

import json

import pytest

from backend import advanced_ai
from backend.embeddings import HashingEmbedder
from backend.rag_engine import RAGEngine
from backend.vector_store import VectorStore

EMB = HashingEmbedder()


def _engine(tmp_path, chunks):
    store = VectorStore(tmp_path / "store")
    store.set_embedder(EMB.name, EMB.dim)
    chunks = [{**c, "source_type": "pdf"} for c in chunks]
    store.add(chunks, EMB.encode([c["text"] for c in chunks]), "src")
    store.save()
    return RAGEngine(store_dir=str(tmp_path / "store"), embedder=EMB, input_dir=str(tmp_path / "in"))


SORTING_OPENING = "Sorting overview. Merge sort splits the array in halves and merges sorted runs back together."
# The first document is long enough that "the first few thousand characters of the corpus" never reaches the second.
SORTING = [
    {"text": SORTING_OPENING + " " + "Comparison sorts need n log n comparisons in the worst case. " * 8, "doc": "sorting.pdf", "page": 1},
    *[
        {"text": f"Sorting section {i}. Quicksort partitions around a pivot; insertion sort is fast on nearly sorted "
                 f"input. " + "Stability keeps equal keys in their original order. " * 10, "doc": "sorting.pdf", "page": i}
        for i in range(2, 10)
    ],
]
TREES = [
    {"text": "Binary search trees keep keys ordered for lookup.", "doc": "trees.pdf", "page": 1},
    {"text": "A red-black tree restores balance after insertion with rotations and recolouring.", "doc": "trees.pdf", "page": 4},
]


@pytest.fixture
def two_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return _engine(tmp_path, SORTING + TREES)


# ----------------------------------------------------------------- concept map
def test_concept_map_context_is_retrieved_for_the_topic(two_docs, fake_gemini):
    res = advanced_ai.build_concept_map("red-black tree rotations", engine=two_docs)
    assert res["ok"] and res["grounding_note"] is None
    prompt = fake_gemini.calls[-1]
    assert "[trees.pdf (page 4)] A red-black tree restores balance" in prompt
    assert SORTING_OPENING not in prompt  # not just the opening of whichever document comes first
    assert res["chunks"] and res["chunks"][0]["doc"] == "trees.pdf" and res["chunks"][0]["page"] == 4
    assert all(c["doc"] == "trees.pdf" for c in res["chunks"])


def test_concept_map_context_stays_within_budget(two_docs, fake_gemini):
    res = advanced_ai.build_concept_map("sorting stability quicksort", engine=two_docs)
    assert sum(len(c["text"]) for c in res["chunks"]) <= advanced_ai.CONCEPT_MAP_CONTEXT_CHARS
    assert all(len(c["text"]) <= advanced_ai.PASSAGE_CHARS for c in res["chunks"])


def test_concept_map_without_a_match_says_so_and_samples_every_document(two_docs, fake_gemini):
    res = advanced_ai.build_concept_map("quantum chromodynamics", engine=two_docs)
    assert res["ok"] and "No passages in your material matched" in res["grounding_note"]
    assert {c["doc"] for c in res["chunks"]} == {"sorting.pdf", "trees.pdf"}  # spread across documents
    assert "[trees.pdf (page 1)]" in fake_gemini.calls[-1]


def test_concept_map_context_override_is_used_verbatim(two_docs, fake_gemini):
    res = advanced_ai.build_concept_map("anything", context_override="CUSTOM CONTEXT", engine=two_docs)
    assert "CUSTOM CONTEXT" in fake_gemini.calls[-1] and "trees.pdf" not in fake_gemini.calls[-1]
    assert res["chunks"] == [] and res["grounding_note"] is None


def test_concept_map_api_returns_its_passages(indexed, fake_gemini):
    body = indexed.post("/api/v1/concept-map", json={"topic": "binary heap"}).json()
    assert body["chunks"] and body["chunks"][0]["doc"] == "heaps.pdf" and body["grounding_note"] is None
    body = indexed.post("/api/v1/concept-map", json={"topic": "quantum chromodynamics"}).json()
    assert body["grounding_note"] and body["warning"] is None  # a grounding note is not an offline fallback


# ----------------------------------------------------------------- synthesis
LONG_FILLER = "This chapter's history section recounts the people and years behind the field. " * 6
SYNTH_DOCS = [
    {"text": "A.pdf intro. " + LONG_FILLER, "doc": "a.pdf", "page": 1},
    {"text": "A binary heap keeps the smallest key at the root.", "doc": "a.pdf", "page": 2},
    {"text": "B.pdf intro. " + LONG_FILLER, "doc": "b.pdf", "page": 1},
    {"text": "A heap supports insert and extract-min in O(log n).", "doc": "b.pdf", "page": 5},
]


@pytest.fixture
def synth_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return _engine(tmp_path, SYNTH_DOCS)


def test_synthesis_picks_topic_passages_per_document_not_the_longest(synth_engine, fake_gemini):
    res = advanced_ai.multi_document_synthesis("binary heap", k_per_doc=1, engine=synth_engine)
    assert res["ok"] and res["grounding_note"] is None
    prompt = fake_gemini.calls[-1]
    assert "- [a.pdf (page 2)] A binary heap keeps the smallest key" in prompt
    assert "- [b.pdf (page 5)] A heap supports insert" in prompt
    assert "history section" not in prompt  # the longest passages were not about the topic
    assert sorted((c["doc"], c["page"]) for c in res["chunks"]) == [("a.pdf", 2), ("b.pdf", 5)]


def test_synthesis_citations_are_checked(synth_engine, fake_gemini):
    fake_gemini.handler = lambda prompt, json_mode: json.dumps({
        "similarities": ["Both put the extreme key first [a.pdf (page 2)] [b.pdf (page 5)]."],
        "conflicts": ["Only one gives costs [b.pdf (page 1)]."],
        "synthesis": "A heap is a tree ordered by key [a.pdf (page 2)], also per [ghost.pdf (page 9)].",
        "citations": [{"doc": "b.pdf (page 5)", "point": "costs"}, {"doc": "Invented Notes", "point": "made up"},
                      {"doc": "", "point": "no document"}],
    })
    res = advanced_ai.multi_document_synthesis("binary heap", k_per_doc=1, engine=synth_engine)
    status = {c["label"]: c["status"] for c in res["checked_citations"]}
    assert status["a.pdf (page 2)"] == "ok" and status["b.pdf (page 5)"] == "ok"
    assert status["ghost.pdf (page 9)"] == "unknown_source"  # an invented citation is flagged
    assert status["b.pdf (page 1)"] == "page_not_retrieved"  # a real document, but a passage the model never saw
    assert status["Invented Notes"] == "unknown_source"
    assert res["unverified_citations"] == 3
    assert [c.get("status") for c in res["citations"]] == ["ok", "unknown_source", None]


def test_synthesis_api_reports_checked_citations_and_passages(indexed, fake_gemini):
    body = indexed.post("/api/v1/synthesis", json={"topic": "binary heap"}).json()
    assert body["chunks"] and {c["doc"] for c in body["chunks"]} == {"heaps.pdf"}
    # FakeGemini's default reply cites "a.pdf", which is not in the indexed material
    assert body["checked_citations"] == [{"label": "a.pdf", "doc": "a.pdf", "page": None, "status": "unknown_source"}]
    assert body["unverified_citations"] == 1 and body["grounding_note"] is None


def test_synthesis_without_a_match_says_so(synth_engine, fake_gemini):
    res = advanced_ai.multi_document_synthesis("quantum chromodynamics", k_per_doc=1, engine=synth_engine)
    assert "No passages in your material matched" in res["grounding_note"]
    assert sorted(c["doc"] for c in res["chunks"]) == ["a.pdf", "b.pdf"]


# ----------------------------------------------------------------- suggestions sample
def test_suggestion_sample_spreads_across_documents(two_docs):
    passages = two_docs.sample_passages(max_chars=2500)
    assert {p["doc"] for p in passages} == {"sorting.pdf", "trees.pdf"}
    assert sum(len(p["text"]) for p in passages) <= 2500
    assert two_docs.sample_passages(max_chars=2500) == passages  # deterministic
