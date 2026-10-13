from backend.chunking import chunk_document, chunk_pages, split_sentences, strip_running_lines


def test_sentences_are_not_split_at_abbreviations_or_decimals():
    s = "Use a hash map, e.g. a dict. It takes about 1.5 microseconds. See Fig. 3 for details. Done."
    parts = split_sentences(s)
    assert parts[0].startswith("Use a hash map, e.g. a dict.")
    assert "about 1.5 microseconds." in parts[1]
    assert any(p.startswith("See Fig. 3") for p in parts)
    assert parts[-1] == "Done."


def test_chunks_never_cut_words_or_sentences_and_respect_the_size():
    sentence = "Hash tables map keys to values using a hash function to pick a bucket. "
    text = sentence * 60
    chunks = chunk_document(text, max_chars=400)
    assert len(chunks) > 3
    assert all(len(c) <= 400 + len(sentence) for c in chunks)
    for c in chunks:
        assert c.strip().endswith("bucket.")  # every chunk ends on a sentence boundary
        assert c.strip().startswith(("Hash tables", ))  # and starts on one


def test_adjacent_chunks_overlap_by_a_sentence():
    text = " ".join(f"Sentence number {i} talks about topic {i} in some detail." for i in range(40))
    chunks = chunk_document(text, max_chars=300)
    for a, b in zip(chunks, chunks[1:]):
        last = a.split(". ")[-1].strip()
        assert last in b  # the final sentence of one chunk reopens the next


def test_markdown_headings_become_context_and_start_new_chunks():
    md = (
        "# Hash Tables\n\n## Collisions\nTwo keys can land in one bucket, which is called a collision. "
        "Every table needs a strategy for handling them.\n\n## Load factor\nThe load factor is the number of entries "
        "divided by the number of buckets, and it controls when the table resizes."
    )
    chunks = chunk_document(md)
    assert len(chunks) == 2
    assert chunks[0].startswith("Hash Tables > Collisions\n")
    assert chunks[1].startswith("Hash Tables > Load factor\n")
    assert "collision" in chunks[0] and "load factor" in chunks[1]


def test_code_blocks_stay_whole():
    code = "```python\n" + "\n".join(f"x{i} = {i}" for i in range(12)) + "\n```"
    md = "Intro paragraph that is long enough to be a real sentence about the code below.\n\n" + code + "\n\nA closing remark about the code that follows the block."
    chunks = chunk_document(md)
    block = [c for c in chunks if "x0 = 0" in c]
    assert len(block) == 1 and "x11 = 11" in block[0] and block[0].count("```") == 2


def test_long_code_is_split_by_lines_not_mid_line():
    code = "```\n" + "\n".join(f"line_{i:03d} = compute({i})" for i in range(200)) + "\n```"
    chunks = chunk_document(code, max_chars=500)
    assert len(chunks) > 1
    for c in chunks:
        for ln in c.split("\n"):
            assert ln.startswith("```") or ln.startswith("line_") and ln.endswith(")")


def test_noise_chunks_are_dropped_and_short_tails_merged():
    text = "Figure 4.6\n\n" + ("A real paragraph about heaps and priority queues that explains the heap property clearly. " * 3)
    chunks = chunk_document(text)
    assert all("Figure 4.6" not in c or len(c) > 100 for c in chunks)
    assert len(chunks) == 1


def test_hyphenated_line_breaks_are_repaired():
    out = chunk_document("An object-ori-\nented design hides the data behind well chosen interfaces and methods for callers.")
    assert "object-oriented" in out[0].lower() or "oriented" in out[0]
    assert "-\n" not in out[0]


def test_running_headers_and_boilerplate_are_stripped_from_paged_documents():
    pages = []
    for n in range(1, 13):
        pages.append(
            (n, f"CHAPTER 4. HEAP {n}\nReal content number {n} about heaps explains the heap property and priority queues in depth, "
                f"with enough words to count as a paragraph.\nAccess for free at openstax.org\n(attribution: Copyright Rice University, OpenStax, under CC BY 4.0 license)")
        )
    chunks = chunk_pages(pages)
    text = " ".join(c["text"] for c in chunks)
    assert "CHAPTER 4" not in text and "openstax" not in text.lower() and "attribution" not in text
    assert "Real content number 7" in text
    assert strip_running_lines([t for _, t in pages[:3]])[0].startswith("CHAPTER")  # too few pages to judge


def test_paragraphs_continue_across_page_breaks_and_pages_are_the_start_page():
    pages = [(1, "Dijkstra's algorithm finds shortest paths. It keeps a priority queue of vertices and repeatedly"),
             (2, "relaxes the edges leaving the closest unvisited vertex until every vertex has been processed.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1 and chunks[0]["page"] == 1
    assert "repeatedly relaxes the edges" in chunks[0]["text"]


def test_empty_and_whitespace_input():
    assert chunk_document("") == [] and chunk_document("   \n\n ") == []
    assert chunk_pages([]) == [] and chunk_pages([(1, "  ")]) == []


def test_a_tiny_document_is_kept_not_filtered_away():
    assert chunk_document("Graphs have nodes and edges.") == ["Graphs have nodes and edges."]
    assert [c["text"] for c in chunk_pages([(1, "Graphs have nodes and edges.")])] == ["Graphs have nodes and edges."]


def test_noise_is_still_dropped_when_real_content_exists():
    text = "Figure 4.6\n\n" + "A real paragraph about heaps and priority queues that explains the heap property clearly. " * 2
    assert all("Figure 4.6" not in c.split(".")[0] or len(c) > 100 for c in chunk_document(text))
