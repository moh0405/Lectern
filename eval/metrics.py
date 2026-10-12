"""Retrieval metrics for the evaluation harness. Pure functions, no I/O."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

KS = (1, 3, 5)


def norm(text: str) -> str:
    """Lowercase, fold ligatures and curly quotes, and collapse whitespace, so a phrase split by a
    line break or typeset with a ligature (PDF text) still matches."""
    text = unicodedata.normalize("NFKC", text).replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_relevant(chunk: Dict[str, Any], evidence: Dict[str, Any], loose: bool = False) -> bool:
    """Does `chunk` satisfy this piece of evidence?

    Strict: the chunk is from the right document and contains a key phrase of the answer.
    Loose (paged documents): the chunk is from the right document and from a page where the evidence
    appears (`evidence["pages"]`), which is how the product cites sources and does not depend on
    where chunk boundaries fall. Strict is used when no page information is available.
    """
    if chunk.get("doc") != evidence["doc"]:
        return False
    if loose and evidence.get("pages"):
        covered = {chunk.get("page"), chunk.get("end_page")}  # a chunk that runs onto the next page covers both
        return bool(covered & set(evidence["pages"]))
    text = norm(chunk.get("text") or "")
    return any(norm(p) in text for p in evidence["any"])


def first_relevant_rank(chunks: Sequence[Dict[str, Any]], expect: List[Dict[str, Any]], loose: bool = False) -> Optional[int]:
    """1-based rank of the first chunk satisfying any expected evidence, else None."""
    for i, c in enumerate(chunks, start=1):
        if any(is_relevant(c, e, loose) for e in expect):
            return i
    return None


def evidence_coverage(chunks: Sequence[Dict[str, Any]], expect: List[Dict[str, Any]], loose: bool = False) -> float:
    """Fraction of the expected pieces of evidence found among the chunks."""
    if not expect:
        return 1.0
    return sum(any(is_relevant(c, e, loose) for c in chunks) for e in expect) / len(expect)


def auroc(positives: Sequence[float], negatives: Sequence[float]) -> Optional[float]:
    """Probability that a random positive scores above a random negative (ties count half).
    Used to ask: does the top retrieval score separate answerable from unanswerable questions?"""
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


@dataclass
class QuestionResult:
    id: str
    category: str
    question: str
    answerable: bool
    rank: Optional[int]  # first relevant rank within the retrieved list (the corpus's primary relevance)
    top_score: float
    coverage_at_5: float
    retrieved: List[Dict[str, Any]] = field(default_factory=list)  # [{doc, page, score}] for the report
    rank_strict: Optional[int] = None  # same, but requiring the key phrase inside the chunk


@dataclass
class Summary:
    n_answerable: int
    n_unanswerable: int
    hit: Dict[int, float]
    mrr: float
    coverage_at_5: float
    abstain_auroc: Optional[float]
    by_category: Dict[str, Dict[str, float]]
    misses: List[str]  # ids of answerable questions with no relevant chunk in the top 5
    strict_hit: Dict[int, float]  # hit@k when the key phrase must be inside the chunk


def summarize(results: Iterable[QuestionResult]) -> Summary:
    results = list(results)
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    n = max(len(answerable), 1)

    def hit_at(rs: List[QuestionResult], k: int) -> float:
        return sum(1 for r in rs if r.rank is not None and r.rank <= k) / max(len(rs), 1)

    cats: Dict[str, Dict[str, float]] = {}
    for cat in sorted({r.category for r in answerable}):
        rs = [r for r in answerable if r.category == cat]
        cats[cat] = {
            "n": float(len(rs)),
            "hit@1": hit_at(rs, 1),
            "hit@3": hit_at(rs, 3),
            "hit@5": hit_at(rs, 5),
            "mrr": sum(1 / r.rank for r in rs if r.rank) / len(rs),
        }
    return Summary(
        n_answerable=len(answerable),
        n_unanswerable=len(unanswerable),
        hit={k: hit_at(answerable, k) for k in KS},
        mrr=sum(1 / r.rank for r in answerable if r.rank) / n,
        coverage_at_5=sum(r.coverage_at_5 for r in answerable) / n,
        abstain_auroc=auroc([r.top_score for r in answerable], [r.top_score for r in unanswerable]),
        by_category=cats,
        misses=[r.id for r in answerable if r.rank is None or r.rank > 5],
        strict_hit={k: sum(1 for r in answerable if r.rank_strict is not None and r.rank_strict <= k) / n for k in KS},
    )
