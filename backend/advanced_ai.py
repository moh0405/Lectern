from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

import json
import logging
import re

from .citations import Citation, check_answer, extract_citations
from .rag_engine import RAGEngine
from .llm_providers import create_llm

logger = logging.getLogger("ai-study-mentor.advanced_ai")

# How much material the concept map and synthesis prompts may carry.
CONCEPT_MAP_K = 12
CONCEPT_MAP_CONTEXT_CHARS = 5000  # passage text; the source labels fit in the prompt's 6,000-character cap
PASSAGE_CHARS = 600
SYNTHESIS_MIN_POOL = 40
SYNTHESIS_MAX_POOL = 200


def _engine(engine: Optional[RAGEngine]) -> Optional[RAGEngine]:
    try:
        return engine or RAGEngine.shared()
    except Exception as e:  # no store yet: the tools still answer, from the topic alone
        logger.warning("No retrieval engine available (%s)", e)
        return None


def _retrieve(eng: Optional[RAGEngine], topic: str, k: int) -> List[Dict[str, Any]]:
    if eng is None or k <= 0:
        return []
    try:
        return [c for c in eng.retrieve_context(topic, k=k) if (c.get("text") or "").strip()]
    except Exception as e:
        logger.warning("Retrieval failed for %r (%s)", topic, e)
        return []


def _fit(chunks: List[Dict[str, Any]], max_chars: int) -> List[Dict[str, Any]]:
    """Chunks in order, each cut to PASSAGE_CHARS, until the character budget is used."""
    picked: List[Dict[str, Any]] = []
    size = 0
    for c in chunks:
        text = c["text"].strip()[:PASSAGE_CHARS]
        if size + len(text) > max_chars:
            continue
        picked.append({**c, "text": text})
        size += len(text)
    return picked


def _format(chunks: List[Dict[str, Any]]) -> str:
    """Passages labelled the way the Ask prompt labels them, so the model cites them as `[doc (page N)]`."""
    return "\n".join(f"- [{RAGEngine.source_label(c)}] {c['text']}" for c in chunks)


def _no_match_note(eng: Optional[RAGEngine], topic: str, what: str) -> str:
    if eng is None or not eng._docstore_iter():
        return f"No study material is indexed, so the {what} is based on the topic alone."
    return (f"No passages in your material matched \"{topic}\", so the {what} is based on a general sample "
            "of your documents instead.")


# -----------------------------
# Concept Map Generator
# -----------------------------

def concept_map_passages(topic: str, engine: Optional[RAGEngine] = None,
                         k: int = CONCEPT_MAP_K, max_chars: int = CONCEPT_MAP_CONTEXT_CHARS) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """(passages, note) the concept map is grounded in: the passages retrieved for `topic`, within `max_chars`.

    If nothing matches the topic, a sample spread across all documents is used and `note` says so."""
    eng = _engine(engine)
    chunks = _fit(_retrieve(eng, topic, k), max_chars)
    if chunks:
        return chunks, None
    sample = eng.sample_passages(max_chars=max_chars, per_passage=PASSAGE_CHARS) if eng is not None else []
    return sample, _no_match_note(eng, topic, "map")


def build_concept_map(topic: str, context_override: Optional[str] = None, temperature: float = 0.2,
                      engine: Optional[RAGEngine] = None) -> Dict[str, Any]:
    """Generate a concept map JSON {nodes, edges} using Gemini if available.

    The context is the passages retrieved for `topic` (or `context_override`); the result carries them as
    `chunks`, plus `grounding_note` when nothing matched the topic and a general sample was used.
    Fallback: simple hierarchical outline built from keyword clustering.
    """
    chunks: List[Dict[str, Any]] = []
    note: Optional[str] = None
    if context_override:
        ctx = raw = context_override
    else:
        chunks, note = concept_map_passages(topic, engine=engine)
        ctx = _format(chunks) if chunks else "(no study material available)"
        raw = "\n\n".join(c["text"] for c in chunks)
    grounding = {"chunks": chunks, "grounding_note": note}
    prompt = (
        "You are an expert study map generator. Given the TOPIC and CONTEXT, "
        "return a clean JSON with fields 'nodes' and 'edges'. Each node: {id, label}. "
        "Each edge: {from, to, label}. Keep node ids short, kebab-case. Only output JSON.\n\n"
        f"TOPIC: {topic}\n\nCONTEXT:\n{ctx[:6000]}\n\n"
        "Rules:\n- Prefer 20-40 nodes.\n- Use concise labels.\n- Include prerequisite relationships and 'is-a' links.\n"
    )

    try:
        client = create_llm(temperature=temperature)
        resp = client.generate(prompt, json_mode=True)
        if resp.get("ok"):
            text = resp.get("answer", "").strip()
            # Defensive JSON extraction
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(text[start : end + 1])
                # Normalize
                nodes = data.get("nodes") or []
                edges = data.get("edges") or []
                return {"ok": True, "nodes": nodes, "edges": edges, "model": resp.get("model"), **grounding}
            return {"ok": False, "error": "Gemini returned non-JSON content"}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback heuristic: build an outline from keyword frequencies
        import re
        toks = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", (raw or "")[:6000].lower())
        from collections import Counter
        freq = Counter(toks)
        common = [w for w, _ in freq.most_common(25)]
        nodes = [{"id": w.replace(" ", "-"), "label": w.title()} for w in common]
        edges = []
        # naive edges: connect adjacent frequent terms
        for i in range(max(0, len(common) - 1)):
            edges.append({"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "label": "related"})
        return {"ok": True, "nodes": nodes, "edges": edges, "model": None, "warning": str(e), **grounding}


def concept_map_to_dot(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
    """Render concept map as Graphviz DOT source (usable with st.graphviz_chart)."""
    lines = ["digraph G {", "  rankdir=LR;", "  node [shape=box, style=filled, color=lightgray];"]
    for n in nodes:
        nid = n.get("id") or n.get("label")
        lbl = n.get("label", nid)
        lines.append(f"  \"{nid}\" [label=\"{lbl}\"];")
    for e in edges:
        s = e.get("from")
        t = e.get("to")
        lbl = e.get("label") or "related"
        lines.append(f"  \"{s}\" -> \"{t}\" [label=\"{lbl}\"];")
    lines.append("}")
    return "\n".join(lines)


# -----------------------------
# Socratic Tutor Mode
# -----------------------------

def _hint_strings(value: Any) -> List[str]:
    """Accept numbered hint objects and lists without stringifying invalid model values."""
    import re

    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [hint for item in value for hint in _hint_strings(item)]
    if isinstance(value, dict):
        numbered = []
        for key, item in value.items():
            match = re.fullmatch(r"hint[_ -]?(\d+)", str(key), re.IGNORECASE)
            if match:
                numbered.append((int(match.group(1)), item))
        return [hint for _, item in sorted(numbered, key=lambda pair: pair[0]) for hint in _hint_strings(item)]
    return []


SOCRATIC_PROMPT = """You are a Socratic tutor. The student asked the QUESTION below and wants to work the answer out themselves, using the PASSAGES from their own study material.

First, privately decide the correct answer and write it as ONE sentence in "answer_key". The student never sees "answer_key"; it is used only to check that no hint gives the answer away.

Then write 3-5 guiding "questions" that lead the student toward the answer without stating it.

Then write a "hints" ladder of 3-4 hints the student reveals one at a time. It is graduated scaffolding, not a summary of the answer:
- Hint 1 points at the relevant concept, or at where to look in the passages (name the passage, and its page if it has one, e.g. "Re-read the part of notes.pdf (page 4) that describes ...").
- The middle hints ask a guiding question or give ONE partial step, leaving the next step for the student.
- The last hint may narrow things down strongly, but the student must still state the conclusion themselves.

Rules for every hint:
- Phrase it as a question or a nudge ("What happens to ...?", "Look at ...", "Compare ...", "Think about ..."), never as a declarative statement of the answer's key mechanism, step or result.
- Never write "The answer is", "This is because", "So the result is" or anything that completes the reasoning for the student.
- Do not restate the answer_key in other words, and do not let the hints together spell out the whole answer.
- Stay grounded in the PASSAGES; if they do not cover the question, guide from general knowledge and say what to look up.

Example for "Why is searching a balanced binary search tree O(log n)?":
  bad hint: "Each comparison discards half the remaining nodes, so the search takes log n steps." (states the answer)
  good hints: "Look at how the passage on page 3 describes what one comparison at a node tells you.", "After one comparison, how many of the remaining nodes could still hold the key?", "If each step keeps only part of the tree, how many steps until one node is left? How does that relate to the tree's height?"

Return pure JSON: {"answer_key": "...", "questions": ["..."], "hints": ["..."]}

QUESTION: {question}

PASSAGES:
{passages}

DEPTH: {depth} (0-5; higher means the student has struggled more, so the middle hints may give a slightly bigger step, but the rules above still apply)."""

# Words that carry no answer content, for the leak check below.
_STOPWORDS = frozenset("""
a an the and or but if then than so as of to in on at by for with from into onto over under about after before
is are was were be been being am do does did doing done has have had having can could will would shall should may
might must it its this that these those there here which who whom whose what when where why how each every any all
some no not only also just very more most less least much many such same other own both either neither one two
you your yours we our they their them he she his her i me my itself themselves via per out up down off again once
""".split())

# Openers that make a hint a nudge rather than a statement.
_NUDGE_OPENERS = ("look", "consider", "think", "check", "compare", "notice", "re-read", "reread", "read", "try",
                  "ask yourself", "recall", "remember", "what", "why", "how", "which", "when", "where", "can you",
                  "could you", "imagine", "trace", "picture", "start", "focus", "find", "see", "review", "revisit")

# Declarative patterns that hand over the conclusion whatever the overlap.
_REVEAL_PATTERNS = re.compile(
    r"\b(the (final |short )?answer is|this is because|that is because|which is why|the reason is|"
    r"so the (answer|result) is|in conclusion|therefore,? the)\b",
    re.IGNORECASE,
)


def _content_words(text: str) -> set:
    """Lower-case content words with a crude stem, so "swaps"/"swap" and "updates"/"updating" match."""
    words = set()
    for w in re.findall(r"[a-z][a-z0-9]+", text.lower()):
        if w in _STOPWORDS or len(w) < 3:
            continue
        for suffix in ("ing", "ies", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                w = w[: -len(suffix)] + ("y" if suffix == "ies" else "")
                break
        words.add(w)
    return words


def _is_nudge(hint: str) -> bool:
    h = hint.strip().lower().lstrip("*_\"'- ")
    return h.endswith("?") or h.startswith(_NUDGE_OPENERS)


def hint_leaks_answer(hint: str, answer_key: str, question: str = "") -> bool:
    """Whether a hint gives the answer away: an explicit "the answer is"-style conclusion, or a hint whose own
    content words (beyond those already in the question) are mostly the hidden answer's. Declarative hints
    are judged strictly; a question or nudge may share more vocabulary before it counts as restating the answer."""
    if _REVEAL_PATTERNS.search(hint):
        return True
    if not answer_key:
        return False
    asked = _content_words(question)
    mine = _content_words(hint) - asked
    answer = _content_words(answer_key) - asked
    if not mine or not answer:
        return False
    shared = mine & answer
    precision = len(shared) / len(mine)  # how much of the hint is answer content
    coverage = len(shared) / len(answer)  # how much of the answer the hint carries
    if _is_nudge(hint):
        return len(shared) >= 5 and (precision >= 0.7 or coverage >= 0.6)
    return len(shared) >= 3 and (precision >= 0.5 or coverage >= 0.4)


def guard_hints(hints: List[str], answer_key: str, question: str) -> Tuple[List[str], int]:
    """Drop hints that restate the hidden answer. Returns the kept hints and how many were dropped."""
    kept = [h for h in hints if not hint_leaks_answer(h, answer_key, question)]
    return kept, len(hints) - len(kept)


_FALLBACK_QUESTIONS = [
    "What key terms does the question involve?",
    "Can you define those terms in your own words?",
    "What relationship exists between those terms?",
    "Which examples from your notes match this situation?",
    "How would you test your current hypothesis?",
]
_FALLBACK_HINTS = [
    "Look for definitions in the context provided.",
    "Identify inputs, outputs, and constraints.",
    "Consider simpler cases that you can reason about first.",
]


def socratic_tutor(question: str, context_chunks: Optional[List[Dict[str, Any]]] = None, depth: int = 0, temperature: float = 0.2) -> Dict[str, Any]:
    """Return guiding questions and progressive hints without giving the answer directly.

    The model also writes a one-sentence answer key in the same call; it is never returned, only used to drop
    hints and questions that restate it."""
    chunks = [c for c in (context_chunks or []) if (c.get("text") or "").strip()]
    passages = "\n".join(
        f"- [{RAGEngine.source_label(c)}] {(c.get('text') or '')[:400]}" if c.get("doc") else f"- {(c.get('text') or '')[:400]}"
        for c in chunks
    ) or "(none: no study material matched, so guide from general knowledge)"
    template = (SOCRATIC_PROMPT.replace("{question}", question).replace("{passages}", passages)
                .replace("{depth}", str(depth)))
    try:
        client = create_llm(temperature=temperature)
        resp = client.generate(template, json_mode=True)
        if resp.get("ok"):
            text = (resp.get("answer") or "").strip()
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1])
            answer_key = data.get("answer_key") if isinstance(data.get("answer_key"), str) else ""
            qs = [q for q in (data.get("questions") or []) if not (isinstance(q, str) and hint_leaks_answer(q, answer_key, question))]
            hs, dropped = guard_hints(_hint_strings(data.get("hints")), answer_key, question)
            if dropped:
                logger.info("Dropped %d socratic hint(s) that restated the answer", dropped)
            if not hs and dropped:
                hs = list(_FALLBACK_HINTS)
            return {"ok": True, "questions": qs, "hints": hs, "model": resp.get("model")}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback canned strategy
        return {"ok": True, "questions": list(_FALLBACK_QUESTIONS), "hints": list(_FALLBACK_HINTS), "warning": str(e)}


# -----------------------------
# Multi-Document Synthesis
# -----------------------------

def synthesis_passages(topic: str, k_per_doc: int = 2, engine: Optional[RAGEngine] = None) -> Tuple[Dict[str, List[Dict[str, Any]]], Optional[str]]:
    """({document: passages}, note): the up-to-`k_per_doc` passages most relevant to `topic` in each document.

    The engine has no per-document filter, so one retrieval over a pool large enough to reach every document is
    grouped by document, keeping each document's best-ranked passages. Documents with nothing about the topic are left
    out. If nothing matches at all, a sample spread across documents is used and `note` says so."""
    eng = _engine(engine)
    items = eng._docstore_iter() if eng is not None else []
    n_docs = len({it.get("doc") for it in items})
    pool = min(len(items), SYNTHESIS_MAX_POOL, max(SYNTHESIS_MIN_POOL, k_per_doc * n_docs * 5))
    by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for c in _retrieve(eng, topic, pool):
        picked = by_doc.setdefault(str(c.get("doc") or "unknown"), [])
        if len(picked) < k_per_doc:
            picked.append({**c, "text": c["text"].strip()[:PASSAGE_CHARS]})
    if by_doc:
        return by_doc, None
    budget = k_per_doc * max(n_docs, 1) * PASSAGE_CHARS  # enough for k_per_doc rounds over every document
    sample = eng.sample_passages(max_chars=budget, per_passage=PASSAGE_CHARS) if eng is not None else []
    for c in sample:
        picked = by_doc.setdefault(str(c.get("doc") or "unknown"), [])
        if len(picked) < k_per_doc:
            picked.append(c)
    return by_doc, _no_match_note(eng, topic, "comparison")


def _check_synthesis(data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Check the model's citations against the passages it was given, the same way Ask answers are checked.

    Covers inline `[doc (page N)]` citations in the synthesis, similarities and conflicts, and the `doc` of each
    structured citation (which gets a `status` in place). Returns (checked citations, number not verified)."""
    texts: List[str] = []
    for key in ("synthesis", "similarities", "conflicts"):
        value = data.get(key)
        texts.extend([value] if isinstance(value, str) else [v for v in (value or []) if isinstance(v, str)])
    found = check_answer("\n".join(texts), chunks)["citations"]
    for cit in data.get("citations") or []:
        if not isinstance(cit, dict) or not str(cit.get("doc") or "").strip():
            continue
        label = str(cit["doc"]).strip().strip("[]").strip()
        checked = extract_citations(f"[{label}]", chunks)
        # a name that matches no passage is not a source the model was given, even if it does not look like a file
        result = checked[0] if checked else Citation(label=label, doc=label, page=None, status="unknown_source")
        cit["status"] = result.status
        found.append(result.to_dict())
    unique: List[Dict[str, Any]] = []
    seen = set()
    for c in found:
        key = (c["label"].lower(), c["status"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique, sum(1 for c in unique if c["status"] != "ok")


def multi_document_synthesis(topic: str, k_per_doc: int = 2, temperature: float = 0.2,
                             engine: Optional[RAGEngine] = None) -> Dict[str, Any]:
    """Compare how multiple documents explain a topic and synthesize a unified explanation.

    Each document contributes its passages most relevant to `topic` (see `synthesis_passages`), labelled with
    document and page; the model's citations are then checked against exactly those passages. The result carries
    `chunks`, `checked_citations`, `unverified_citations` and, when nothing matched the topic, `grounding_note`."""
    doc_passages, note = synthesis_passages(topic, k_per_doc=k_per_doc, engine=engine)
    chunks = [c for cs in doc_passages.values() for c in cs]
    comparison_blocks = [f"DOC: {d}\n{_format(cs)}" for d, cs in doc_passages.items()]
    prompt = (
        "You are a research synthesizer. Compare how each DOC explains the TOPIC, using ONLY the passages given, "
        "list similarities and conflicts, and then produce a unified explanation that cites which DOC said what. "
        "Cite each claim inline with the passage label in square brackets exactly as it appears before the passage, "
        "for example [notes.pdf (page 3)]. Never cite a document or page that is not listed below.\n"
        "Return JSON with fields: {similarities: [..], conflicts: [..], synthesis: string, citations: [{doc, point}]}, "
        "where each citation's doc is one of those passage labels.\n\n"
        f"TOPIC: {topic}\n\n" + ("\n\n".join(comparison_blocks) or "(no study material available)")
    )
    grounding = {"chunks": chunks, "grounding_note": note}
    try:
        client = create_llm(temperature=temperature)
        resp = client.generate(prompt, json_mode=True)
        if resp.get("ok"):
            text = resp.get("answer", "")
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1])
            checked, unverified = _check_synthesis(data, chunks)
            return {"ok": True, **data, "model": resp.get("model"), "checked_citations": checked,
                    "unverified_citations": unverified, **grounding}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback heuristic synthesis
        sims = [f"Common emphasis on {topic} across sources."]
        confs = ["Differences in terminology and depth of examples."]
        synth = (
            f"Across documents, {topic} is presented with overlapping ideas but varying terminology. "
            "Core themes align, while examples differ; combine definitions from multiple sources for clarity."
        )
        cits = [{"doc": d, "point": f"Provided {len(v)} snippets"} for d, v in doc_passages.items()]
        data = {"similarities": sims, "conflicts": confs, "synthesis": synth, "citations": cits}
        checked, unverified = _check_synthesis(data, chunks)
        return {"ok": True, **data, "checked_citations": checked, "unverified_citations": unverified,
                "warning": str(e), **grounding}


# -----------------------------
# Adaptive Difficulty + ELI Levels
# -----------------------------

ELI_LEVELS = {
    "ELI5": "Explain like I'm 5 years old — use simple analogies and everyday language.",
    "ELI10": "Explain like middle school — use simple math and concrete examples.",
    "Undergrad": "Explain for an undergraduate — include definitions and brief formalisms.",
    "Grad": "Explain for a graduate student — rigorous, with references and proofs sketch.",
    "Expert": "Explain for an expert — terse, technical, assume strong background.",
}


def adaptive_explain(question: str, level: str = "Undergrad", temperature: float = 0.2,
                     engine: Optional[RAGEngine] = None, passages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Generate an explanation tailored to the requested ELI level, using RAG context and Gemini.

    `passages`, when given, are used instead of retrieving (the ones an answer was built from, or browser documents).
    Falls back to a template-based rewrite if Gemini is unavailable.
    """
    eng = engine or RAGEngine.shared()
    chunks = passages if passages is not None else eng.retrieve_context(question, k=4)
    context = eng.format_context(chunks)
    instr = ELI_LEVELS.get(level, ELI_LEVELS["Undergrad"])
    prompt = (
        f"You are a tutor. {instr}\n\n"
        "Use ONLY the following context:\n"
        f"{context}\n\n"
        f"Question: {question}\n\n"
        "Produce a clear explanation and end with 3 short quiz questions." 
    )
    try:
        client = create_llm(temperature=temperature)
        resp = client.generate(prompt)
        if resp.get("ok"):
            return {"ok": True, "answer": resp.get("answer"), "chunks": chunks, "model": resp.get("model")}
        return {"ok": False, "error": resp.get("error"), "chunks": chunks}
    except Exception as e:
        # Fallback rewrite
        preface = {
            "ELI5": "Imagine you're learning with building blocks. ",
            "ELI10": "Think of it like a recipe with steps. ",
            "Undergrad": "Formally, we can define the key terms. ",
            "Grad": "From a theoretical perspective: ",
            "Expert": "Concise technical view: ",
        }.get(level, "Explanation: ")
        text = preface + (chunks[0]["text"][:500] if chunks else "No context available.")
        quiz = "\n\nQuiz:\n1) Define the core term.\n2) Give one example.\n3) Explain a limitation."
        return {"ok": True, "answer": text + quiz, "chunks": chunks, "warning": str(e)}


# -----------------------------
# LaTeX Math Rendering + Steps
# -----------------------------

def math_solve(user_input: str) -> Dict[str, Any]:
    """Symbolic math with LaTeX output and short steps.

    Accepts: "simplify (x^2 + 2x + 1)", "differentiate sin(x)", "integrate x^2",
    "expand (x+1)^3", "factor x^2 - 1", "solve x^2 = 4 for x", or a bare expression.
    Input is validated against a whitelist and computed in a worker process with
    a timeout (see backend/safe_math.py); it never reaches `eval` unchecked.
    """
    from .safe_math import solve_request

    return solve_request(user_input)
