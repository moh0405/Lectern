"""BM25 lexical search with no dependencies.

Dense embeddings capture meaning but blur exact terms (an acronym, a function name, "O(n log n)"),
while keyword search is exact but blind to paraphrase. BM25 is the standard keyword ranker: it
rewards rare query terms (IDF), saturates repeated terms (k1) and discounts long passages (b).

`tokenize` lower-cases, drops stopwords and applies a deliberately conservative suffix stemmer
(plurals, -ing, -ed) so "collisions" matches "collision" and "sorting" matches "sort".
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

STOPWORDS = frozenset(
    "a an the is are was were be been being of in on at to for from by with and or not as it its this that these those "
    "what which who whom how why when where do does did can could should would will you your i we they he she them "
    "his her our us about into than then so if there their".split()
)

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def stem(word: str) -> str:
    """Strip common English inflections. Conservative on purpose: it only needs to be *consistent* between
    the index and the query, and over-stemming merges unrelated words.

    plurals (collisions -> collision, queries -> query, hashes -> hash), -ing / -ed with undoubling
    (running -> run, sorted -> sort), then a trailing "e" is dropped so table/tables and cache/caches agree.
    """
    if len(word) <= 3 or word.isdigit():
        return word
    if word.endswith("sses"):
        word = word[:-2]
    elif word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith(("ches", "shes", "xes", "zes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            base = word[: -len(suffix)]
            if len(base) >= 4 and base[-1] == base[-2] and base[-1] not in "lsz":
                base = base[:-1]  # running -> run
            word = base
            break
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    """Inverted index over a fixed list of texts. Rebuild when the texts change."""

    def __init__(self, texts: Iterable[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        self.doc_len: List[int] = []
        for i, text in enumerate(texts):
            toks = tokenize(text)
            self.doc_len.append(len(toks))
            for term, tf in Counter(toks).items():
                self.postings[term].append((i, tf))
        self.n = len(self.doc_len)
        self.avg_len = (sum(self.doc_len) / self.n) if self.n else 0.0
        self._idf_cache: Dict[str, float] = {}

    def idf(self, term: str) -> float:
        cached = self._idf_cache.get(term)
        if cached is None:
            df = len(self.postings.get(term, ()))
            cached = math.log(1 + (self.n - df + 0.5) / (df + 0.5)) if df else 0.0
            self._idf_cache[term] = cached
        return cached

    def max_score(self, terms: Sequence[str]) -> float:
        """Upper bound of a document's score for these query terms (every term present, tf -> infinity),
        used to put scores on a 0..1 scale that is comparable across queries.

        Terms that never occur in the corpus still count, as maximally rare ones: a question where one of
        five words matches must not score like one where all five do.
        """
        rarest = math.log(1 + (self.n + 0.5) / 0.5)
        return sum((self.idf(t) if t in self.postings else rarest) * (self.k1 + 1) for t in set(terms)) or 1.0

    def search(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        """Top-k (doc index, normalized score in 0..1). Documents sharing no term are not returned."""
        terms = [t for t in dict.fromkeys(tokenize(query)) if t in self.postings]
        if not terms or not self.n:
            return []
        scores: Dict[int, float] = defaultdict(float)
        for term in terms:
            idf = self.idf(term)
            for doc, tf in self.postings[term]:
                norm = 1 - self.b + self.b * self.doc_len[doc] / (self.avg_len or 1.0)
                scores[doc] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        top = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
        ceiling = self.max_score(tokenize(query))
        return [(i, s / ceiling) for i, s in top]


def reciprocal_rank_fusion(rankings: Sequence[Sequence[int]], k: int = 60) -> List[Tuple[int, float]]:
    """Merge several ranked lists of ids: each list contributes 1 / (k + rank). Needs no score calibration,
    which is why it is the usual way to combine keyword and vector search."""
    fused: Dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, ident in enumerate(ranking, start=1):
            fused[ident] += 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
