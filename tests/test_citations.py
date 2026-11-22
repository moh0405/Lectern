import pytest

from backend.citations import check_answer, extract_citations

CHUNKS = [
    {"doc": "Dsa.pdf", "page": 12, "end_page": None, "text": "..."},
    {"doc": "Dsa.pdf", "page": 50, "end_page": 51, "text": "..."},
    {"doc": "Intro to Heaps", "page": None, "text": "a video transcript"},
]


def statuses(answer):
    return {c.label: c.status for c in extract_citations(answer, CHUNKS)}


def test_a_citation_of_a_retrieved_page_is_ok():
    assert statuses("Heaps are trees [Dsa.pdf (page 12)].") == {"Dsa.pdf (page 12)": "ok"}


def test_the_page_must_have_been_retrieved():
    assert statuses("See [Dsa.pdf (page 99)].") == {"Dsa.pdf (page 99)": "page_not_retrieved"}


def test_a_passage_that_spans_pages_supports_either_page():
    s = statuses("[Dsa.pdf (page 50)] and [Dsa.pdf (page 51)] but not [Dsa.pdf (page 52)]")
    assert s == {"Dsa.pdf (page 50)": "ok", "Dsa.pdf (page 51)": "ok", "Dsa.pdf (page 52)": "page_not_retrieved"}


def test_invented_documents_are_flagged():
    s = statuses("According to [Operating Systems.pdf (page 3)] and [made_up_notes.pdf].")
    assert s == {"Operating Systems.pdf (page 3)": "unknown_source", "made_up_notes.pdf": "unknown_source"}


@pytest.mark.parametrize(
    "text",
    ["[Dsa.pdf, page 12]", "[Dsa.pdf (p. 12)]", "[Dsa.pdf (pages 11-13)]", "[dsa (page 12)]", "[DSA.PDF (Page 12)]", "[Dsa.pdf]"],
)
def test_common_citation_styles_are_understood(text):
    assert [c.status for c in extract_citations(text, CHUNKS)] == ["ok"]


def test_titles_without_an_extension_are_verified_when_they_name_a_retrieved_document():
    assert statuses("As shown in [Intro to Heaps].") == {"Intro to Heaps": "ok"}
    assert statuses("[Intro to Heaps, page 3]") == {"Intro to Heaps, page 3": "page_not_retrieved"}  # that source has no pages


@pytest.mark.parametrize(
    "text",
    [
        "Use nums[0] and grid[i][j] to index.",
        "As noted in [1] and [2].",
        "Fill in the [x] placeholder; see [below] for details.",
        "A [link](https://example.com) is not a citation.",
        "A list like [1, 2, 3] is not either.",
        "",
    ],
)
def test_ordinary_brackets_are_never_flagged(text):
    assert extract_citations(text, CHUNKS) == []


def test_duplicates_are_reported_once():
    cites = extract_citations("[Dsa.pdf (page 12)] ... again [Dsa.pdf (page 12)]", CHUNKS)
    assert len(cites) == 1


def test_summary_counts_unverified_and_flags_uncited_answers():
    ok = check_answer("Heaps [Dsa.pdf (page 12)].", CHUNKS)
    assert ok == {"citations": ok["citations"], "unverified": 0, "uncited": False}
    bad = check_answer("Heaps [Dsa.pdf (page 12)] and [Nope.pdf (page 1)].", CHUNKS)
    assert bad["unverified"] == 1 and len(bad["citations"]) == 2

    long_uncited = "A heap is a tree. " * 20
    assert check_answer(long_uncited, CHUNKS)["uncited"] is True
    assert check_answer("Short answer.", CHUNKS)["uncited"] is False  # too short to expect citations
    assert check_answer(long_uncited, [])["uncited"] is False  # nothing was retrieved to cite


def test_works_with_no_chunks():
    assert extract_citations("[Dsa.pdf (page 12)]", [])[0].status == "unknown_source"


@pytest.mark.parametrize("text", ["[Intro to Heaps (page None)]", "[Intro to Heaps (page n/a)]", "[Intro to Heaps (p. null)]"])
def test_a_source_without_pages_may_be_cited_as_page_none(text):
    # an older prompt labelled such sources "(page None)", and models copy labels; that must not look invented
    assert [c.status for c in extract_citations(text, CHUNKS)] == ["ok"]


# ----------------------------------------------------------------- document + section citations (sources without pages)
MD_CHUNKS = [
    {"doc": "hashing.md", "page": None, "text": "Hash Tables > Collisions: ..."},
    {"doc": "dsa.pdf", "page": 12, "text": "..."},
    {"doc": "src/utils.py", "page": None, "text": "..."},
]


@pytest.mark.parametrize(
    "label",
    [
        "hashing.md > Hash Tables > Open addressing",
        "hashing.md › Hash Tables",
        "hashing.md / Collisions",
        "hashing.md - Collisions",
        "hashing.md: Collisions",
        "hashing > Collisions",  # the extension may be dropped, as it already may for a plain citation
    ],
)
def test_a_document_followed_by_a_section_path_cites_the_retrieved_document(label):
    found = extract_citations(f"Use chaining [{label}].", MD_CHUNKS)
    assert [(c.doc, c.status) for c in found] == [("hashing.md" if "." in label else "hashing", "ok")]
    assert found[0].label == label  # the label is shown as the model wrote it


def test_a_section_path_does_not_launder_an_invented_document():
    found = extract_citations("See [Invented.md > Hash Tables > Collisions] and [made-up.pdf > Chapter 3].", MD_CHUNKS)
    assert [c.status for c in found] == ["unknown_source", "unknown_source"]


def test_a_real_document_name_that_contains_a_separator_still_matches_exactly():
    assert [c.status for c in extract_citations("See [src/utils.py].", MD_CHUNKS)] == ["ok"]


def test_a_section_path_with_a_page_still_checks_the_page():
    ok = extract_citations("See [dsa.pdf > Heaps (page 12)].", MD_CHUNKS)
    bad = extract_citations("See [dsa.pdf > Heaps (page 99)].", MD_CHUNKS)
    assert [c.status for c in ok] == ["ok"] and [c.status for c in bad] == ["page_not_retrieved"]


def test_the_summary_no_longer_accuses_a_section_style_citation():
    answer = "Hash tables resolve collisions by chaining or open addressing. " * 5 + "[hashing.md > Hash Tables > Collisions]"
    summary = check_answer(answer, MD_CHUNKS)
    assert summary["unverified"] == 0 and summary["uncited"] is False


# ----------------------------------------------------------------- several citations in one bracket, and "(null)" pages
def test_several_citations_in_one_bracket_are_checked_one_by_one():
    found = extract_citations("See [Dsa.pdf (page 12), Dsa.pdf (page 50)].", CHUNKS)
    assert [(c.label, c.status) for c in found] == [("Dsa.pdf (page 12)", "ok"), ("Dsa.pdf (page 50)", "ok")]


def test_a_bad_one_among_several_is_reported_alone():
    found = extract_citations("See [Dsa.pdf (page 12); Ghost.pdf (page 3)] and [Dsa.pdf (page 99), Dsa.pdf (page 12)].", CHUNKS)
    assert {c.label: c.status for c in found} == {
        "Dsa.pdf (page 12)": "ok",
        "Ghost.pdf (page 3)": "unknown_source",
        "Dsa.pdf (page 99)": "page_not_retrieved",
    }


def test_documents_listed_with_commas_split_only_when_each_is_a_retrieved_document():
    found = extract_citations("See [Dsa.pdf, Intro to Heaps].", CHUNKS)
    assert [(c.doc, c.status) for c in found] == [("Dsa.pdf", "ok"), ("Intro to Heaps", "ok")]
    # a title that merely contains a comma is left whole
    whole = extract_citations("See [Intro to Heaps, second edition.pdf].", CHUNKS)
    assert len(whole) == 1 and whole[0].status == "unknown_source"


@pytest.mark.parametrize("label", ["hashing.md (null)", "hashing.md (None)", "hashing.md (page null)", "hashing.md (n/a)", "hashing.md (unknown)"])
def test_a_null_page_marker_means_the_document_has_no_pages(label):
    found = extract_citations(f"Chaining [{label}].", MD_CHUNKS)
    assert [(c.doc, c.page, c.status) for c in found] == [("hashing.md", None, "ok")]


def test_the_exact_reply_a_real_model_gave_is_no_longer_accused():
    chunks = [{"doc": "graphs.md", "page": None, "text": "..."}, {"doc": "arrays-lists.md", "page": None, "text": "..."}]
    answer = "BFS uses a queue [graphs.md (null), arrays-lists.md (null)]. It runs in O(V+E) time [graphs.md (null)]."
    assert check_answer(answer, chunks)["unverified"] == 0


@pytest.mark.parametrize("label", ["a.pdf (page 58, page 170)", "a.pdf (pages 58, 170)", "a.pdf (pp. 58, 170)", "a.pdf, pages 58, 170", "a.pdf, p. 58, 170"])
def test_several_pages_in_one_parenthesis_are_checked_page_by_page(label):
    chunks = [{"doc": "a.pdf", "page": 58, "end_page": 58}, {"doc": "a.pdf", "page": 170, "end_page": 170}]
    assert check_answer(f"x [{label}]", chunks)["unverified"] == 0


def test_a_listed_page_that_was_not_retrieved_is_still_flagged():
    chunks = [{"doc": "a.pdf", "page": 58, "end_page": 58}]
    out = check_answer("x [a.pdf (page 58, page 170)]", chunks)
    assert out["unverified"] == 1 and out["citations"][1]["status"] == "page_not_retrieved"


# Prose-parenthesis citations, as the failover model gemini-3.1-flash-lite writes them (live evaluation, defect 1).
PROSE = [
    {"doc": "Data Structures Using Python.pdf", "page": 118, "end_page": 119, "text": "..."},
    {"doc": "Data Structures Using Python.pdf", "page": 120, "end_page": None, "text": "..."},
    {"doc": "heaps.pdf", "page": 1, "end_page": None, "text": "..."},
    {"doc": "Intro to Heaps", "page": None, "text": "a video transcript"},
]


def prose(answer):
    return [(c.label, c.doc, c.page, c.status) for c in extract_citations(answer, PROSE)]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("A binary heap is used to implement a priority queue (heaps.pdf, page 1).", [("heaps.pdf, page 1", "heaps.pdf", 1, "ok")]),
        ("…until the queue is empty (*Data Structures Using Python.pdf*, page 120).",
         [("Data Structures Using Python.pdf, page 120", "Data Structures Using Python.pdf", 120, "ok")]),
        ("Bold works too (**heaps.pdf**, p. 1) and underscores (_heaps.pdf_, p. 1).", [("heaps.pdf, p. 1", "heaps.pdf", 1, "ok")]),
        ("A page range (*Data Structures Using Python.pdf*, pages 118–120).",
         [("Data Structures Using Python.pdf, pages 118–120", "Data Structures Using Python.pdf", 118, "ok")]),
        ("Hyphen and pp. (Data Structures Using Python.pdf, pp. 118-119).",
         [("Data Structures Using Python.pdf, pp. 118-119", "Data Structures Using Python.pdf", 118, "ok")]),
        ("Nested (heaps.pdf (page 1)).", [("heaps.pdf (page 1)", "heaps.pdf", 1, "ok")]),
        ("With see (see heaps.pdf, page 1).", [("heaps.pdf, page 1", "heaps.pdf", 1, "ok")]),
        ("A titled source (Intro to Heaps).", [("Intro to Heaps", "Intro to Heaps", None, "ok")]),
        ("Wrapped in backticks `(heaps.pdf, page 1)`.", [("heaps.pdf, page 1", "heaps.pdf", 1, "ok")]),
        ("Bracket in backticks `[heaps.pdf (page 1)]`.", [("heaps.pdf (page 1)", "heaps.pdf", 1, "ok")]),
    ],
)
def test_prose_parenthesis_citations_are_recognised(answer, expected):
    assert prose(answer) == expected


def test_several_citations_in_one_parenthesis():
    answer = "Both agree (heaps.pdf, p. 1; *Data Structures Using Python.pdf*, page 120; Intro to Heaps)."
    assert [(c[0], c[3]) for c in prose(answer)] == [
        ("heaps.pdf, p. 1", "ok"),
        ("Data Structures Using Python.pdf, page 120", "ok"),
        ("Intro to Heaps", "ok"),
    ]


def test_a_page_range_verifies_when_any_page_in_it_was_retrieved():
    assert prose("(heaps.pdf, pages 1-3)")[0][3] == "ok"
    assert prose("(heaps.pdf, pages 4–6)")[0][3] == "page_not_retrieved"


def test_a_prose_citation_of_a_page_not_retrieved_is_flagged():
    assert prose("(heaps.pdf, page 7)") == [("heaps.pdf, page 7", "heaps.pdf", 7, "page_not_retrieved")]


@pytest.mark.parametrize(
    "answer",
    [
        "The details come later (see below).",
        "Insertion is fast (O(log n)) and lookups too (O(1)).",
        "Priority queues (heaps) are trees.",  # a bare stem of heaps.pdf is a word, not a citation
        "Call it as `push(heaps.pdf, page 1)` in code.",
        "A link [text](heaps.pdf) is not a prose citation.",
        "Use a list (for example, page 1 of a book).",
    ],
)
def test_ordinary_parentheses_are_not_citations(answer):
    assert prose(answer) == []


def test_an_unknown_source_in_parentheses_is_ignored_not_flagged():
    # Prose parentheses mention many things; only a source the model was given counts as a citation.
    assert prose("CLRS covers this (Cormen.pdf, page 3) in depth.") == []


def test_mixed_parenthesis_keeps_only_the_named_source():
    assert [c[0] for c in prose("(heaps.pdf, page 1; see also the lecture)")] == ["heaps.pdf, page 1"]


def test_a_bracket_citation_inside_parentheses_is_counted_once():
    assert prose("Heaps are trees ([heaps.pdf (page 1)]).") == [("heaps.pdf (page 1)", "heaps.pdf", 1, "ok")]


def test_bracket_citations_are_unchanged_next_to_prose_ones():
    answer = "Heaps [heaps.pdf (page 1)] and queues (Data Structures Using Python.pdf, page 120)."
    assert [c[0] for c in prose(answer)] == ["heaps.pdf (page 1)", "Data Structures Using Python.pdf, page 120"]


def test_a_prose_cited_answer_is_not_reported_as_uncited():
    answer = ("A binary heap is a complete binary tree stored in an array, so the parent of index i is at (i - 1) // 2 "
              "and its children are at 2i + 1 and 2i + 2. It is used to implement a priority queue (heaps.pdf, page 1).")
    result = check_answer(answer, PROSE)
    assert result["uncited"] is False
    assert result["unverified"] == 0
    assert [c["label"] for c in result["citations"]] == ["heaps.pdf, page 1"]


def test_the_answer_prompt_insists_on_brackets():
    from backend.rag_engine import RAGEngine

    for mode in (None, "eli5", "technical", "interview", "summary"):
        template = RAGEngine._prompt_for_mode(RAGEngine.__new__(RAGEngine), mode)
        assert "square brackets" in template and "Never cite in parentheses" in template
