"""Structure-aware chunking (version 2).

The original chunker cut text into fixed 800-character windows. That splits sentences and words,
keeps page headers and licence boilerplate as "content", produces tiny noise chunks such as
"CHAPTER 4. HEAP 39 Figure 4.6", and cuts paragraphs at page boundaries. This one:

- strips lines that repeat on many pages (running headers/footers) and licence boilerplate
- joins hard-wrapped lines and de-hyphenates words broken at a line end
- works on paragraphs, then sentences, and packs whole sentences up to `max_chars`
- carries the last sentence into the next chunk as overlap
- keeps fenced code blocks (Markdown) whole where they fit, otherwise splits them by lines
- drops chunks with almost no content and merges short tails into the previous chunk
- tracks Markdown headings and prefixes each chunk with its heading path, which helps retrieval
  ("Hash Tables > Collisions") and gives the reader context when the passage is shown on its own

`chunk_pages` works on a whole document so paragraphs that continue across a page break stay
together; each chunk is labelled with the page it starts on.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

CHUNKER_VERSION = "v2"

MAX_CHARS = 900
MIN_CHARS = 160  # shorter chunks are merged into a neighbour when possible
MIN_ALNUM = 40  # chunks with less real content than this are dropped
HARD_MAX = 1400  # a merged chunk may exceed MAX_CHARS up to this

_FENCE = re.compile(r"^(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_ABBREV = {"e.g", "i.e", "vs", "etc", "fig", "figs", "eq", "eqs", "no", "approx", "cf", "al", "dr", "mr", "mrs", "ms", "prof", "sec", "ch"}
_SENT_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]*[A-Z0-9])")
# Lines that are licence/attribution boilerplate in OpenStax-style PDFs.
_BOILERPLATE = [
    re.compile(r"\(attribution:[^)]*\)", re.I),
    re.compile(r"^\s*Access for free at\s+\S+.*$", re.I | re.M),
]


@dataclass
class Piece:
    text: str
    start: int  # character offset of the chunk's first character in the cleaned source text


# ----------------------------------------------------------------------------- cleaning
def _digits_to_hash(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_running_lines(pages: Sequence[str], min_pages: int = 8, threshold: float = 0.3) -> List[str]:
    """Remove short lines that appear on at least `threshold` of the pages (page numbers vary, so digits are ignored).

    These are running headers and footers such as "CHAPTER 4. HEAP 40". Only applied to documents with
    at least `min_pages` pages, where repetition is meaningful.
    """
    if len(pages) < min_pages:
        return list(pages)
    counts: Counter[str] = Counter()
    for p in pages:
        counts.update({_digits_to_hash(ln) for ln in p.splitlines() if 0 < len(ln.strip()) <= 90})
    limit = max(3, int(threshold * len(pages)))
    common = {k for k, n in counts.items() if n >= limit and re.search(r"[a-z]", k)}
    cleaned = []
    for p in pages:
        cleaned.append("\n".join(ln for ln in p.splitlines() if _digits_to_hash(ln) not in common))
    return cleaned


def clean_text(text: str) -> str:
    """Normalise one block of extracted text: licence boilerplate out, newlines unified, words broken at a
    line end repaired. (Hard-wrapped lines are joined later, per paragraph, in `_units`.)"""
    for pat in _BOILERPLATE:
        text = pat.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\u00ad", "")
    return re.sub(r"(\w)-\n(?=[a-z])", r"\1", text)  # "Ob-\nject" -> "Object"


# ----------------------------------------------------------------------------- splitting
def split_sentences(paragraph: str) -> List[str]:
    """Split on sentence ends, but not after common abbreviations or inside decimals."""
    parts: List[str] = []
    start = 0
    for m in _SENT_END.finditer(paragraph):
        head = paragraph[start : m.start()]
        last_token = head.rstrip(".!?\"')]").split()[-1].lower().rstrip(".") if head.strip() else ""
        if last_token in _ABBREV or re.fullmatch(r"[a-z]", last_token or "x"):
            continue  # "e.g. foo", "Fig. 3", single initials
        parts.append(paragraph[start : m.end()].strip())
        start = m.end()
    tail = paragraph[start:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _hard_split(text: str, limit: int) -> List[str]:
    """Break an over-long run (e.g. pseudocode dumped on one line) at word boundaries."""
    out: List[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        cut = cut if cut > limit // 2 else limit
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


@dataclass
class _Unit:
    text: str
    start: int
    heading: str
    atomic: bool = False  # a code block: do not merge it into prose


def _units(text: str, max_chars: int = MAX_CHARS) -> List[_Unit]:
    """Walk the text into paragraph/sentence/code units with their heading path and offsets."""
    units: List[_Unit] = []
    headings: List[Tuple[int, str]] = []  # (level, title)
    lines = text.split("\n")
    pos = 0
    i = 0
    para: List[str] = []
    para_start = 0

    def heading_path() -> str:
        return " > ".join(t for _, t in headings)

    def flush():
        nonlocal para, para_start
        if para:
            body = " ".join(s.strip() for s in para).strip()
            if body:
                for sent in split_sentences(body):
                    for piece in _hard_split(sent, max_chars) if len(sent) > max_chars else [sent]:
                        units.append(_Unit(piece, para_start, heading_path()))
            para = []

    while i < len(lines):
        ln = lines[i]
        line_len = len(ln) + 1
        stripped = ln.strip()
        if _FENCE.match(stripped):
            flush()
            block = [ln]
            start = pos
            i += 1
            pos += line_len
            while i < len(lines):
                block.append(lines[i])
                pos += len(lines[i]) + 1
                closing = bool(_FENCE.match(lines[i].strip()))
                i += 1
                if closing:
                    break
            code = "\n".join(block).strip()
            if code:
                units.append(_Unit(code, start, heading_path(), atomic=True))
            continue
        m = _HEADING.match(stripped)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
        elif not stripped:
            flush()
        else:
            if not para:
                para_start = pos
            para.append(ln)
        pos += line_len
        i += 1
    flush()
    return units


def _alnum(text: str) -> int:
    return sum(c.isalnum() for c in text)


def chunk_document_pieces(text: str, max_chars: int = MAX_CHARS, heading_context: bool = True) -> List[Piece]:
    """Chunk already-cleaned text. Returns pieces with their start offsets."""
    min_chars = min(MIN_CHARS, max_chars // 3)  # only truly tiny tails are merged
    units = _units(text, max_chars)
    chunks: List[Tuple[str, int, str, bool]] = []  # (body, start, heading, atomic)
    cur: List[_Unit] = []
    cur_len = 0

    def emit():
        nonlocal cur, cur_len
        if cur:
            chunks.append((" ".join(u.text for u in cur), cur[0].start, cur[0].heading, False))
        cur, cur_len = [], 0

    for u in units:
        if u.atomic:
            emit()
            if len(u.text) <= HARD_MAX:
                chunks.append((u.text, u.start, u.heading, True))
            else:  # long code block: split by lines, never mid-line
                buf: List[str] = []
                size = 0
                for line in u.text.split("\n"):
                    if size + len(line) > max_chars and buf:
                        chunks.append(("\n".join(buf), u.start, u.heading, True))
                        buf, size = [], 0
                    buf.append(line)
                    size += len(line) + 1
                if buf:
                    chunks.append(("\n".join(buf), u.start, u.heading, True))
            continue
        # a new heading section always starts a new chunk, so a passage never mixes two topics (or wears the wrong heading)
        if cur and u.heading != cur[0].heading:
            emit()
        if cur and cur_len + len(u.text) + 1 > max_chars:
            last = cur[-1]
            emit()
            if len(last.text) <= max_chars // 4 and last.heading == u.heading:
                cur, cur_len = [last], len(last.text)  # one-sentence overlap
        cur.append(u)
        cur_len += len(u.text) + 1
    emit()

    # merge short chunks into the previous one (same heading, not code), then drop empty ones
    merged: List[Tuple[str, int, str, bool]] = []
    for body, start, heading, atomic in chunks:
        if merged and not atomic and not merged[-1][3] and len(body) < min_chars and merged[-1][2] == heading \
                and len(merged[-1][0]) + len(body) + 1 <= HARD_MAX:
            prev = merged[-1]
            merged[-1] = (prev[0] + " " + body, prev[1], prev[2], False)
        else:
            merged.append((body, start, heading, atomic))
    pieces: List[Piece] = []
    for body, start, heading, atomic in merged:
        if _alnum(body) < MIN_ALNUM:
            continue
        prefix = f"{heading}\n" if heading_context and heading else ""
        pieces.append(Piece(prefix + body, start))
    if not pieces and merged:
        # Noise filtering must never reduce a whole (tiny) document to nothing: keep its longest piece.
        body, start, heading, _atomic = max(merged, key=lambda m: _alnum(m[0]))
        if _alnum(body) >= 5:
            prefix = f"{heading}\n" if heading_context and heading else ""
            pieces.append(Piece(prefix + body, start))
    return pieces


def chunk_document(text: str, max_chars: int = MAX_CHARS, heading_context: bool = True) -> List[str]:
    """Chunk one document (Markdown, web article, README...) into strings."""
    return [p.text for p in chunk_document_pieces(clean_text(text), max_chars, heading_context)]


def chunk_pages(pages: Sequence[Tuple[Optional[int], str]], max_chars: int = MAX_CHARS) -> List[Dict[str, object]]:
    """Chunk a paged document (PDF). Running headers/footers are stripped, paragraphs may cross page breaks,
    and each chunk carries the page it starts on and, when it runs onto the next page, `end_page`.
    Returns [{"text", "page", "end_page"}]."""
    numbers = [p for p, _ in pages]
    texts = strip_running_lines([t for _, t in pages])
    cleaned = [clean_text(t) for t in texts]
    joined: List[str] = []
    page_starts: List[Tuple[int, Optional[int]]] = []
    offset = 0
    for number, body in zip(numbers, cleaned):
        page_starts.append((offset, number))
        joined.append(body)
        offset += len(body) + 2
    full = "\n\n".join(joined)
    out: List[Dict[str, object]] = []

    def page_at(offset: int) -> Optional[int]:
        page = None
        for start, number in page_starts:
            if start <= offset:
                page = number
            else:
                break
        return page

    for piece in chunk_document_pieces(full, max_chars, heading_context=False):
        first = page_at(piece.start)
        last = page_at(piece.start + max(len(piece.text) - 1, 0))
        out.append({"text": piece.text, "page": first, "end_page": last if last != first else None})
    return out
