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
