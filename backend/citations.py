"""Check the citations in a model's answer against the passages it was actually given.

The prompt asks the model to cite as `[document (page N)]`. A model can invent a document, or cite a
real one for a page it never saw. Both look authoritative and are worse than no citation, so each citation
is checked against the retrieved chunks:

    ok                   the document and (if given) the page are among the retrieved passages
    page_not_retrieved   the document was retrieved, but not the cited page
    unknown_source       the document was not retrieved at all

What counts as a citation is deliberately conservative, so ordinary text such as `nums[0]` or `[1]` is never
flagged. A bracketed expression is a citation if it has a page suffix ("(page 3)", ", p. 3"), ends in a file
extension (".pdf"), or names a retrieved document exactly (so video and web titles are verified too).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

_BRACKET = re.compile(r"(?<![\w\])])\[([^\[\]\n]{3,200})\](?!\()")
_PAGE = r"(?:pages?|pp?\.?)\s*(\d+)(?:\s*[-–]\s*(\d+))?"
_WITH_PAGE_PAREN = re.compile(rf"^(?P<doc>.+?)\s*\(\s*{_PAGE}\s*\)\s*$", re.I)
_WITH_PAGE_COMMA = re.compile(rf"^(?P<doc>.+?)\s*[,;:·–-]\s*{_PAGE}\s*$", re.I)
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


_NO_PAGE = re.compile(r"\s*\(\s*(?:pages?|pp?\.?)\s*(?:none|n/?a|null|-)\s*\)\s*$", re.I)


def _parse(inner: str) -> Optional[Dict[str, Any]]:
    """(doc, page, has_page_suffix) from the text inside brackets, or None if it cannot be a citation."""
    text = _NO_PAGE.sub("", inner.strip())  # "(page None)": a source without pages, cited as written
    for pattern in (_WITH_PAGE_PAREN, _WITH_PAGE_COMMA):
        m = pattern.match(text)
        if m:
            return {"doc": m.group("doc").strip(" ,;:"), "page": int(m.group(2)), "end": m.group(3), "suffix": True}
    return {"doc": text, "page": None, "end": None, "suffix": False}


def extract_citations(answer: str, chunks: Sequence[Dict[str, Any]]) -> List[Citation]:
    """Citations found in `answer`, each checked against `chunks` (dicts with doc/page/end_page)."""
    docs: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        for k in _doc_keys(c.get("doc") or ""):
            docs.setdefault(k, []).append(c)

    found: List[Citation] = []
    seen = set()
    for m in _BRACKET.finditer(answer or ""):
        raw = m.group(1).strip()
        parsed = _parse(raw)
        if not parsed or not re.search(r"[A-Za-z]", parsed["doc"]):
            continue
        doc_keys = _doc_keys(parsed["doc"])
        matches = next((docs[k] for k in doc_keys if k in docs), None)
        is_citation = parsed["suffix"] or bool(_EXTENSION.search(parsed["doc"])) or matches is not None
        if not is_citation:
            continue  # ordinary bracketed text such as an index, a note, a placeholder
        if matches is None:
            status = "unknown_source"
        elif parsed["page"] is None:
            status = "ok"
        else:
            lo = parsed["page"]
            hi = int(parsed["end"]) if parsed["end"] else lo
            wanted = set(range(lo, hi + 1)) if hi >= lo and hi - lo < 50 else {lo}
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
