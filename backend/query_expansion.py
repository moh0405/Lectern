"""Cheap, deterministic query expansion for retrieval.

Students type "BFS" and "DFS"; textbooks mostly write "breadth-first search" and "depth-first search". An
acronym gives BM25 one token and the embedding model almost nothing to go on, and "DFS" is also a
*distributed file system*: on the live site "Difference between BFS and DFS" retrieved two passages about
distributed file systems. `expand_query` appends the spelled-out form of every known CS acronym. For an
acronym with several senses it picks the sense the rest of the question points to (graph words, or another
acronym such as BFS, mean depth-first search; file, server and storage words mean distributed file system),
and keeps every sense when nothing tells them apart, so a bare "What is DFS?" can retrieve both.

A short list of related terms does the same for concepts a question names generically (a hash collision ->
chaining, open addressing, probing), so a corpus that describes those strategies is found.

No model, no network, no state: safe at Lambda init, and well under a millisecond per query. Measured in
eval/README.md (`default-*-noexpand` configs).
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Tuple

# acronym -> [(expansion, cue words that select this sense)]. A single-sense entry needs no cues.
# Only acronyms whose expansion is unambiguous in a CS course, or whose senses can be told apart by cues.
_GRAPH_CUES = frozenset(
    "graph graphs tree trees traversal traverse traversing vertex vertices node nodes edge edges neighbor neighbors "
    "neighbour neighbours stack queue backtrack backtracking explore exploring exploration recursion recursive cycle "
    "cycles topological maze path paths shortest search searching algorithm algorithms bfs level visit visited "
    "connected component components adjacency iterative deepening".split()
)
_FILE_CUES = frozenset(
    "file files filesystem storage store stored server servers network networked replication replica replicas "
    "hdfs nfs disk disks block blocks cluster distributed share sharing shared directory directories cloud "
    "namenode datanode mount".split()
)

ACRONYMS: Dict[str, List[Tuple[str, FrozenSet[str]]]] = {
    "bfs": [("breadth-first search", frozenset())],
    "dfs": [("depth-first search", _GRAPH_CUES), ("distributed file system", _FILE_CUES)],
    "bst": [("binary search tree", frozenset())],
    "dag": [("directed acyclic graph", frozenset())],
    "mst": [("minimum spanning tree", frozenset())],
    "dp": [("dynamic programming", frozenset())],
    "lru": [("least recently used", frozenset())],
    "fifo": [("first in first out", frozenset())],
    "lifo": [("last in first out", frozenset())],
    "adt": [("abstract data type", frozenset())],
    "oop": [("object-oriented programming", frozenset())],
    "dbms": [("database management system", frozenset())],
    "rdbms": [("relational database management system", frozenset())],
    "sql": [("structured query language", frozenset())],
    "acid": [("atomicity consistency isolation durability", frozenset(
        "transaction transactions database databases property properties commit".split()))],
    "tcp": [("transmission control protocol", frozenset())],
    "udp": [("user datagram protocol", frozenset())],
    "dns": [("domain name system", frozenset())],
    "http": [("hypertext transfer protocol", frozenset())],
    "nfs": [("network file system", frozenset())],
    "hdfs": [("hadoop distributed file system", frozenset())],
    "cpu": [("central processing unit processor", frozenset())],
    "ram": [("random access memory", frozenset())],
    "gc": [("garbage collection", frozenset())],
    "os": [("operating system", frozenset(
        "process processes kernel thread threads scheduling scheduler memory system call calls file".split()))],
}

# A few textbook terms students use for a concept the material may name differently. Applied only when the
# trigger words all occur in the query and it names none of the terms yet. Kept short: every added word also
# widens the BM25 match.
RELATED_TERMS: List[Tuple[FrozenSet[str], str]] = [
    (frozenset({"hash", "collision"}), "collision resolution separate chaining open addressing probing"),
    (frozenset({"hash", "collisions"}), "collision resolution separate chaining open addressing probing"),
    (frozenset({"hashing", "collision"}), "collision resolution separate chaining open addressing probing"),
    (frozenset({"hashing", "collisions"}), "collision resolution separate chaining open addressing probing"),
]

_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def expansions(query: str) -> List[str]:
    """The phrases `expand_query` would add, in order, without duplicates or phrases already in the query."""
    words = _words(query)
    present = set(words)
    lowered = " ".join(words)
    out: List[str] = []

    def add(phrase: str) -> None:
        norm = " ".join(_words(phrase))
        if norm and norm not in lowered and phrase not in out:
            out.append(phrase)

    for w in dict.fromkeys(words):
        senses = ACRONYMS.get(w)
        if not senses:
            continue
        if len(senses) == 1:
            add(senses[0][0])
            continue
        context = present - {w}
        scores = [len(cues & context) for _, cues in senses]
        best = max(scores)
        for (phrase, _), s in zip(senses, scores):
            if best == 0 or s == best:  # nothing disambiguates: keep every sense
                add(phrase)
    for triggers, phrase in RELATED_TERMS:
        specific = set(_words(phrase)) - triggers - {"collision", "collisions", "resolution"}
        # a question that already names one of the strategies is about that one: do not pull in the others
        if triggers <= present and not specific & present:
            add(phrase)
    return out


def expand_query(query: str) -> str:
    """`query` with the spelled-out acronyms and related terms appended, e.g.
    "Difference between BFS and DFS" -> "Difference between BFS and DFS (breadth-first search; depth-first search)".
    Returns `query` unchanged when there is nothing to add."""
    extra = expansions(query)
    return f"{query} ({'; '.join(extra)})" if extra else query

