# 5. Chunking

## Why chunk at all?

A search result has to be small enough to (a) fit a few of them in the model's prompt, (b) be *about one thing* so its embedding is meaningful, and (c) be readable on its own as a citation. A 300-page PDF is none of those; a 300-page PDF cut into passages of about 300 to 900 characters is.

Chunk quality quietly dominates retrieval quality. A perfect search over badly cut passages still returns bad passages.

## Version 1 (the original) and its problems

Fixed windows of 800 characters. Problems found by reading real output on the textbooks:

- cut **mid-sentence and mid-word** ("hash collis" | "ions");
- kept **running headers** ("CHAPTER 4. HEAP 40") and licence boilerplate as content, producing noise chunks;
- split a paragraph at every **page break**;
- split code blocks anywhere.

## Version 2 (`backend/chunking.py`, `CHUNKER_VERSION = "v2"`)

| Step | What it does | Why |
|---|---|---|
| Strip running lines | lines (digits ignored) that repeat on ≥30% of pages of a ≥8-page document are removed | removes headers/footers without touching content |
| Strip boilerplate | OpenStax "Access for free at…" and attribution lines | licence text is not knowledge |
| Repair text | join hard-wrapped lines; fix `Ob-\nject` → `Object` | PDFs wrap lines mid-sentence |
| Split sentences | on `. ! ?` + capital, but **not** after `e.g.`, `Fig.`, `vs`, initials | sentences are the natural atom |
| Pack sentences | add whole sentences up to 900 characters; carry the last short sentence into the next chunk as **overlap** | passages never end mid-thought, and context bridges the cut |
| Track headings | Markdown `#` headings form a path; each chunk starts with it, e.g. `Graph Algorithms > Depth-first search` | gives both the embedding and the reader topic context |
| New heading = new chunk | a chunk never mixes two sections | a passage never wears the wrong heading |
| Code blocks | fenced blocks stay whole when ≤1400 characters, otherwise split by lines | code cut in half is useless |
| Cross-page paragraphs | the whole PDF is chunked as one text; each chunk records the page it **starts** on and, if it runs over, `end_page` | citations like `(pages 12-13)` |
| Noise filter | drop chunks with <40 letters/digits; merge short tails (<160 chars) | removes "Figure 4.6" style fragments |
| Never empty a document | if filtering would remove everything, keep the longest piece | a tiny but real document must stay searchable (found as a bug) |

## Before and after on a real file (`eval/corpus/graphs.md`)

| | v1 | v2 |
|---|---|---|
| Chunks | 5, cut mid-word | 7, whole sentences |
| Lengths (chars) | uniform ≈800 | 479, 372, 509, 397, 319, 440, 479 |
| Example prefix | none | `Graph Algorithms > Depth-first search` |

## What chunking did to retrieval (measured)

On the real textbooks (33 answerable questions): chunking v2 together with hybrid search lifted hit@3 from 82% to 94%. Honest nuance: v2 chunks with dense-only search *lower* MRR by about 0.12, and hybrid on the old chunks is a gain of only 3 points (not significant). They work together. Chunk size (400, 600, 900 characters) made little difference. All rows are in `eval/reports/real-ablations.md`.

## Re-chunking existing indexes

Each indexed source records the chunker version that produced it. If you upgrade the algorithm, the next `index` run re-chunks old sources automatically; unchanged sources with the current version are skipped.

## Trade-offs to know about

- **Size.** Smaller chunks are more precise but lose surrounding context; bigger ones carry more context but blur the embedding and exceed MiniLM's ~256 word-piece limit. 900 characters (about 150 words) is a compromise measured against the evaluation set, not a law.
- **Overlap** helps boundary cases but duplicates a little text.
- A better (future) option is **semantic chunking** (split where meaning shifts) or "small-to-big" (retrieve small, show the parent section).

## Where to look

- `backend/chunking.py`, `tests/test_chunking_v2.py`
- `backend/document_processor.py`: extraction per file type
- `eval/corpus/`: the committed documents used for before/after comparisons
