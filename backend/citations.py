"""Check the citations in a model's answer against the passages it was actually given.

The prompt asks the model to cite as `[document (page N)]`. A model can invent a document, or cite a
real one for a page it never saw. Both look authoritative and are worse than no citation, so each citation
is checked against the retrieved chunks:

    ok                   the document and (if given) the page are among the retrieved passages; a section
                         path after the document ("doc > Heading") is accepted, but the section itself is not checked
    page_not_retrieved   the document was retrieved, but not the cited page
    unknown_source       the document was not retrieved at all

What counts as a citation is deliberately conservative, so ordinary text such as `nums[0]` or `[1]` is never
flagged. A bracketed expression is a citation if it has a page suffix ("(page 3)", ", p. 3"), ends in a file
extension (".pdf"), or names a retrieved document exactly (so video and web titles are verified too).

Some models ignore the bracket format and cite in prose parentheses instead: "(*Dsa.pdf*, pages 118–120)",
"(Dsa.pdf, p. 3; notes.md)". A parenthesis is only a citation when it names a document the model was actually given
(so "(see below)", "(O(log n))" or "(heaps)" are left alone), and then it is checked like a bracket citation. A
parenthesis that names an unknown document is ignored rather than flagged, because prose parentheses mention other
things too. Markdown emphasis and a leading "see" are dropped from its label; the web app strips them the same way.

A page range ("pages 118-120") is verified when any page in the range was retrieved; `page` is its first page.

Models vary the format, so these all read as the same citation: "doc page 3", "doc, Page: 3", "doc: Dsa.pdf, page: 3",
"*doc*, p. 3", "pages 3 to 5", "pages 3—5", "pages 3, 5-6", "pages 3 and 5", "a.pdf (page 3) and b.md". A page written
after a bare space only counts when the text before it is a known document or a file name, so "[see page 3]" stays
ordinary text. An invented source with neither a page nor a file extension ("[Some Book]") cannot be told from ordinary
bracketed text and is not flagged, unless it carries an explicit empty page ("[Some Book (page None)]").
The web parser (apps/web/features/ask/citations.ts) mirrors this; tests/fixtures/citation_labels.json is run against both.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

_BRACKET = re.compile(r"(?<![\w)])\[([^\[\]\n]{3,200})\](?!\()")
_RANGE = r"(?:\s*[-–—‒‑]\s*|\s+to\s+)"
_PAGE_WORD = r"(?:pages?|pgs?\.?|pp?\.?)(?:\s*no\.?)?\s*[:=#]?"
_PAGE = rf"{_PAGE_WORD}\s*(\d+)(?:{_RANGE}(\d+))?"
_DOC_SEP = r"[,;:·–—-]"
_WITH_PAGE_PAREN = re.compile(rf"^(?P<doc>.+?)\s*\(\s*{_PAGE}\s*\)\s*$", re.I)
_WITH_PAGE_COMMA = re.compile(rf"^(?P<doc>.+?)\s*{_DOC_SEP}\s*{_PAGE}\s*$", re.I)
_WITH_PAGE_SPACE = re.compile(rf"^(?P<doc>.+?)\s+{_PAGE}\s*$", re.I)
_ITEM = rf"\d+(?:{_RANGE}\d+)?"
_LIST_SEP = r"\s*(?:[,;&]\s*(?:and\s+)?|and\s+)"
_PAGES = rf"{_PAGE_WORD}\s*{_ITEM}(?:{_LIST_SEP}(?:{_PAGE_WORD}\s*)?{_ITEM})+"
_PAGE_LIST = re.compile(rf"^(?P<doc>.+?)\s*(?:\(\s*(?P<p1>{_PAGES})\s*\)|{_DOC_SEP}\s*(?P<p2>{_PAGES}))\s*$", re.I)
_PAGE_LIST_SPACE = re.compile(rf"^(?P<doc>.+?)\s+(?P<p1>{_PAGES})\s*$", re.I)
_LABEL_LEAD = re.compile(r"^(?:doc(?:ument)?|source|file)\s*:\s*", re.I)
# A prose parenthesis that may hold citations: no brackets inside (a bracket citation is handled on its own), one
# level of nested parentheses allowed ("(doc.pdf (page 3))"), and never a Markdown link target "](...)".
_PAREN = re.compile(r"(?<![\]\w])\(((?:[^()\[\]\n]|\([^()\[\]\n]*\)){3,300})\)")
_CODE = re.compile(r"```[\s\S]*?```|`[^`\n]*`")
_CODED_PAREN = re.compile(r"^`\s*\((?:[^()\[\]\n]|\([^()\[\]\n]*\)){3,300}\)\s*`$")
_EMPHASIS = re.compile(r"\*+|(?<!\w)_+|_+(?!\w)|`")
_LEAD = re.compile(r"^(?:see(?:\s+also)?|cf\.?|source:|sources:|from)\s+", re.I)
_EXTENSION = re.compile(r"\.(pdf|md|txt|py|rst|docx?|pptx?|mp3|mp4|wav|m4a|html?)\b", re.I)


@dataclass
class Citation:
    label: str  # the text as the model wrote it, e.g. "Dsa.pdf (page 12)"
    doc: str
    page: Optional[int]
    status: str  # ok | page_not_retrieved | unknown_source

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _doc_keys(name: str) -> set:
    base = _key(name)
    stem = re.sub(r"\.[a-z0-9]{1,5}$", "", base)
    return {base, stem}


_NO_PAGE = re.compile(r"\s*(?:\(\s*(?:(?:pages?|pp?\.?)\s*:?\s*)?(?:none|n/?a|null|nil|unknown|-)\s*\)|,\s*(?:pages?|pp?\.?)\s*:?\s*(?:none|n/?a|null|nil|unknown|-))\s*$", re.I)


def _page_labels(doc: str, pages: str) -> List[str]:
    """One label per page or range of a page list."""
    out = []
    for item in re.findall(_ITEM, pages, re.I):
        numbers = re.findall(r"\d+", item)
        out.append(f"{doc} (page {numbers[0]})" if len(numbers) == 1 else f"{doc} (pages {numbers[0]}-{numbers[1]})")
    return out


def _split_multi(inner: str, docs: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Models often put several citations in one bracket: [a.pdf (page 3), b.md (page 1)] or [a.md, b.md]. Split them
    so each is checked on its own. Commas alone only split when every part is a retrieved document, because a comma
    can also belong to a title."""
    listed = _PAGE_LIST.match(inner)
    if listed:  # "doc (page 58, page 170)", "doc (pages 58, 59)" or "doc, pages 58, 170": one citation per page
        return _page_labels(listed.group("doc"), listed.group("p1") or listed.group("p2"))
    spaced = _PAGE_LIST_SPACE.match(inner)
    if spaced and _names_a_document(spaced.group("doc"), docs):  # "doc pages 58 and 170"
        return _page_labels(spaced.group("doc"), spaced.group("p1"))
    parts = [p.strip() for p in re.split(r"(?<=\))\s*(?:[,;&]|(?i:and)\b)\s*|\s*;\s*", inner) if p.strip()]
    if len(parts) > 1:
        return parts
    if "," in inner:
        pieces = [p.strip() for p in inner.split(",") if p.strip()]
        if len(pieces) > 1 and all(any(k in docs for k in _doc_keys(p)) for p in pieces):
            return pieces
    # "a.pdf, page 3, b.md" or "a.pdf and b.md": split only when every part names a retrieved document.
    pieces = [p.strip() for p in re.split(rf"(?<=\d)\s*,\s*(?!\d|{_PAGE_WORD}\s*\d)|\s+(?:(?i:and)|&)\s+", inner) if p.strip()]
    if len(pieces) > 1 and all(_match_doc(_parse(p)["doc"], docs)[0] is not None for p in pieces):
        return pieces
    return [inner.strip()]


def _names_a_document(text: str, docs: Dict[str, List[Dict[str, Any]]]) -> bool:
    clean = _LABEL_LEAD.sub("", re.sub(r"[*`]", "", text).strip())
    return bool(_EXTENSION.search(clean)) or _match_doc(clean, docs)[0] is not None


# Sources without pages (Markdown, web pages, transcripts) are often cited by document and section, for example
# [hashing.md > Hash Tables > Collisions]. That names a real document the model was given, so it is not an invented source.
_SECTION_SEP = re.compile(r"\s*(?:>|›|»|→|/|\||::)\s*|\s+[-–—]\s+|:\s+")


def _match_doc(doc_text: str, docs: Dict[str, List[Dict[str, Any]]]) -> tuple:
    """(chunks of the matching retrieved document or None, the document part of the label). The whole text is tried
    first (document names can contain '/' or ':'), then the part before the first section separator."""
    for k in _doc_keys(doc_text):
        if k in docs:
            return docs[k], doc_text
    parts = _SECTION_SEP.split(doc_text, maxsplit=1)
    if len(parts) == 2 and parts[0].strip():
        for k in _doc_keys(parts[0]):
            if k in docs:
                return docs[k], parts[0].strip()
    return None, doc_text


def _parse(inner: str) -> Optional[Dict[str, Any]]:
    """(doc, page, has_page_suffix) from the text inside brackets, or None if it cannot be a citation."""
    raw = inner.strip()
    text = _NO_PAGE.sub("", raw)  # "(page None)": a source without pages, cited as written
    marked_no_page = text != raw
    text = _LABEL_LEAD.sub("", re.sub(r"[*`]", "", text).strip())
    for pattern in (_WITH_PAGE_PAREN, _WITH_PAGE_COMMA):
        m = pattern.match(text)
        if m:
            return {"doc": m.group("doc").strip(" ,;:"), "page": int(m.group(2)), "end": m.group(3), "suffix": True}
    m = _WITH_PAGE_SPACE.match(text)
    if m:  # no separator: a citation only if the rest names a document, which the caller checks
        return {"doc": m.group("doc").strip(" ,;:"), "page": int(m.group(2)), "end": m.group(3), "suffix": False}
    return {"doc": text, "page": None, "end": None, "suffix": marked_no_page}


def _wanted_pages(parsed: Dict[str, Any]) -> set:
    lo = parsed["page"]
    hi = int(parsed["end"]) if parsed["end"] else lo
    return set(range(lo, hi + 1)) if hi >= lo and hi - lo < 50 else {lo}


def clean_paren(inner: str) -> str:
    """The text of a prose parenthesis as a citation label: Markdown emphasis, a leading "see" and extra spaces dropped.
    Mirrored by `cleanParen` in apps/web/features/ask/citations.ts."""
    text = re.sub(r"\s+", " ", _EMPHASIS.sub("", inner)).strip()
    return _LEAD.sub("", text).strip()


def _paren_parts(inner: str, docs: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """The citations a prose parenthesis holds: only parts that name a retrieved document count."""
    text = clean_paren(inner)
    parts = []
    for raw in _split_multi(text, docs):
        parsed = _parse(raw)
        matches, doc_part = _match_doc(parsed["doc"], docs)
        if matches is None:
            continue
        # A bare stem such as "(heaps)" for heaps.pdf is ordinary prose; a page, an extension or the full name is not.
        named = parsed["suffix"] or bool(_EXTENSION.search(doc_part)) or any(_key(doc_part) == _key(c.get("doc") or "") for c in matches)
        if named:
            parts.append(raw)
    return parts


def citation_spans(answer: str, docs: Dict[str, List[Dict[str, Any]]]) -> List[tuple]:
    """(start, end, labels) for every bracket and prose-parenthesis citation in `answer`, in order."""
    spans = [(m.start(), m.end(), _split_multi(m.group(1).strip(), docs)) for m in _BRACKET.finditer(answer or "")]
    # Never read citations out of code, except an inline span that is exactly one parenthesis ("`(doc.pdf, page 3)`"):
    # some models wrap their citations in backticks. Offsets are kept so spans still index into `answer`.
    prose = _CODE.sub(lambda m: (" " + m.group(0)[1:-1] + " ") if _CODED_PAREN.match(m.group(0)) else " " * len(m.group(0)), answer or "")
    for m in _PAREN.finditer(prose):
        if any(s <= m.start() < e or m.start() <= s < m.end() for s, e, _ in spans):
            continue
        parts = _paren_parts(m.group(1), docs)
        if parts:
            spans.append((m.start(), m.end(), parts))
    return sorted(spans, key=lambda s: s[0])


def _index(chunks: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    docs: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        for k in _doc_keys(c.get("doc") or ""):
            docs.setdefault(k, []).append(c)
    return docs


def extract_citations(answer: str, chunks: Sequence[Dict[str, Any]]) -> List[Citation]:
    """Citations found in `answer`, each checked against `chunks` (dicts with doc/page/end_page)."""
    docs = _index(chunks)
    found: List[Citation] = []
    seen = set()
    cited: List[str] = [label for _s, _e, labels in citation_spans(answer, docs) for label in labels]
    for raw in cited:
        parsed = _parse(raw)
        if not parsed or not re.search(r"[A-Za-z]", parsed["doc"]):
            continue
        matches, doc_part = _match_doc(parsed["doc"], docs)
        parsed["doc"] = doc_part
        is_citation = parsed["suffix"] or bool(_EXTENSION.search(parsed["doc"])) or matches is not None
        if not is_citation:
            continue  # ordinary bracketed text such as an index, a note, a placeholder
        if matches is None:
            status = "unknown_source"
        elif parsed["page"] is None:
            status = "ok"
        else:
            wanted = _wanted_pages(parsed)
            status = "ok" if any(wanted & _pages_of(c) for c in matches) else "page_not_retrieved"
        key = (raw.lower(), status)
        if key in seen:
            continue
        seen.add(key)
        found.append(Citation(label=raw, doc=parsed["doc"], page=parsed["page"], status=status))
    return found


def _pages_of(chunk: Dict[str, Any]) -> set:
    page, end = chunk.get("page"), chunk.get("end_page")
    if page is None:
        return {None}
    if end and end >= page:
        return set(range(page, end + 1))
    return {page}


def passages_to_show(answer: str, passages: Sequence[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    """The passages to send with an answer: at most `limit`, except that a passage backing a verified citation is never
    left out, so every citation checked against `passages` can open its evidence. Original order is kept."""
    docs = _index(passages)
    position = {id(p): i for i, p in enumerate(passages)}
    keep = set()
    for c in extract_citations(answer, passages):
        if c.status != "ok":
            continue
        parsed = _parse(c.label)
        matches = _match_doc(parsed["doc"], docs)[0] or []
        if parsed["page"] is not None:
            wanted = _wanted_pages(parsed)
            matches = [m for m in matches if wanted & _pages_of(m)]
        if matches and not any(id(m) in {id(passages[i]) for i in keep} for m in matches):
            keep.add(position[id(matches[0])])
    for i in range(len(passages)):
        if len(keep) >= limit:
            break
        keep.add(i)
    return [passages[i] for i in sorted(keep)]


def check_answer(answer: str, chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The summary the API returns: the checked citations, how many are unverified, and whether an
    answer that had sources to cite cited none of them."""
    citations = extract_citations(answer, chunks)
    unverified = sum(1 for c in citations if c.status != "ok")
    substantive = len((answer or "").strip()) >= 200
    return {
        "citations": [c.to_dict() for c in citations],
        "unverified": unverified,
        "uncited": bool(chunks) and substantive and not citations,
    }
