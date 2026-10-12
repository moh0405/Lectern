from __future__ import annotations

from typing import Dict, Any, List, Optional

import json

try:
    import sympy as sp  # optional
except Exception:
    sp = None

try:
    import matplotlib.pyplot as plt  # optional
except Exception:
    plt = None

from .rag_engine import RAGEngine
from .llm_config import GeminiClient


# -----------------------------
# Concept Map Generator
# -----------------------------

def _collect_context(max_chars: int = 4000) -> str:
    """Collect a concatenated context string from the docstore for prompting.

    Uses a hardened RAGEngine path that does not require FAISS indexes.
    """
    try:
        eng = RAGEngine.shared()
        items = eng._docstore_iter()
    except Exception:
        items = []
    texts = []
    size = 0
    for it in items:
        t = (it.get("text") or "").strip()
        if not t:
            continue
        if size + len(t) > max_chars:
            break
        texts.append(t)
        size += len(t)
    return "\n\n".join(texts)


def build_concept_map(topic: str, context_override: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
    """Generate a concept map JSON {nodes, edges} using Gemini if available.

    Fallback: simple hierarchical outline built from keyword clustering.
    """
    ctx = context_override or _collect_context()
    prompt = (
        "You are an expert study map generator. Given the TOPIC and CONTEXT, "
        "return a clean JSON with fields 'nodes' and 'edges'. Each node: {id, label}. "
        "Each edge: {from, to, label}. Keep node ids short, kebab-case. Only output JSON.\n\n"
        f"TOPIC: {topic}\n\nCONTEXT:\n{ctx[:6000]}\n\n"
        "Rules:\n- Prefer 20-40 nodes.\n- Use concise labels.\n- Include prerequisite relationships and 'is-a' links.\n"
    )

    try:
        client = GeminiClient(temperature=temperature)
        resp = client.generate(prompt)
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
                return {"ok": True, "nodes": nodes, "edges": edges, "model": resp.get("model")}
            return {"ok": False, "error": "Gemini returned non-JSON content"}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback heuristic: build an outline from keyword frequencies
        import re
        toks = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", (ctx or "")[:6000].lower())
        from collections import Counter
        freq = Counter(toks)
        common = [w for w, _ in freq.most_common(25)]
        nodes = [{"id": w.replace(" ", "-"), "label": w.title()} for w in common]
        edges = []
        # naive edges: connect adjacent frequent terms
        for i in range(max(0, len(common) - 1)):
            edges.append({"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "label": "related"})
        return {"ok": True, "nodes": nodes, "edges": edges, "model": None, "warning": str(e)}


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

def socratic_tutor(question: str, context_chunks: Optional[List[Dict[str, Any]]] = None, depth: int = 0, temperature: float = 0.2) -> Dict[str, Any]:
    """Return guiding questions and progressive hints without giving the answer directly."""
    context_text = "\n".join([(c.get("text") or "")[:400] for c in (context_chunks or [])])
    template = (
        "You are a Socratic tutor. Given a QUESTION and optional CONTEXT, "
        "ask 3-5 guiding questions that lead the student to the answer. "
        "Provide a short hint ladder (hint1, hint2, hint3) where each is more explicit than the last. "
        "Do NOT reveal the final answer. Return pure JSON: {questions: [..], hints: [..]}\n\n"
        f"QUESTION: {question}\n\nCONTEXT:\n{context_text}\n\n"
        f"DEPTH: {depth} (higher depth means the student has struggled more)."
    )
    try:
        client = GeminiClient(temperature=temperature)
        resp = client.generate(template)
        if resp.get("ok"):
            text = (resp.get("answer") or "").strip()
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1])
            qs = data.get("questions") or []
            hs = data.get("hints") or []
            return {"ok": True, "questions": qs, "hints": hs, "model": resp.get("model")}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback canned strategy
        qs = [
            "What key terms does the question involve?",
            "Can you define those terms in your own words?",
            "What relationship exists between those terms?",
            "Which examples from your notes match this situation?",
            "How would you test your current hypothesis?",
        ]
        hs = [
            "Look for definitions in the context provided.",
            "Identify inputs, outputs, and constraints.",
            "Consider simpler cases that you can reason about first.",
        ]
        return {"ok": True, "questions": qs, "hints": hs, "warning": str(e)}


# -----------------------------
# Multi-Document Synthesis
# -----------------------------

def multi_document_synthesis(topic: str, k_per_doc: int = 2, temperature: float = 0.2) -> Dict[str, Any]:
    """Compare how multiple documents explain a topic and synthesize a unified explanation."""
    eng = RAGEngine.shared()
    items = eng._docstore_iter()
    # Group texts by document
    by_doc: Dict[str, List[str]] = {}
    for it in items:
        doc = it.get("doc") or "unknown"
        by_doc.setdefault(doc, []).append((it.get("text") or ""))
    # For each doc, pick top-k snippets by simple length (proxy for substance)
    doc_snippets: Dict[str, List[str]] = {
        d: sorted(v, key=lambda s: len(s), reverse=True)[:k_per_doc] for d, v in by_doc.items()
    }
    # Build a comparison prompt
    comparison_blocks = []
    for d, vs in doc_snippets.items():
        joined = "\n- " + "\n- ".join([s[:400] for s in vs]) if vs else "(no content)"
        comparison_blocks.append(f"DOC: {d}\n{joined}")
    prompt = (
        "You are a research synthesizer. Compare how each DOC explains the TOPIC, "
        "list similarities and conflicts, and then produce a unified explanation that cites which DOC said what. "
        "Return JSON with fields: {similarities: [..], conflicts: [..], synthesis: string, citations: [{doc, point}]}.\n\n"
        f"TOPIC: {topic}\n\n" + "\n\n".join(comparison_blocks)
    )
    try:
        client = GeminiClient(temperature=temperature)
        resp = client.generate(prompt)
        if resp.get("ok"):
            text = resp.get("answer", "")
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1])
            return {"ok": True, **data, "model": resp.get("model")}
        return {"ok": False, "error": resp.get("error")}
    except Exception as e:
        # Fallback heuristic synthesis
        sims = [f"Common emphasis on {topic} across sources."]
        confs = ["Differences in terminology and depth of examples."]
        synth = (
            f"Across documents, {topic} is presented with overlapping ideas but varying terminology. "
            "Core themes align, while examples differ; combine definitions from multiple sources for clarity."
        )
        cits = [{"doc": d, "point": f"Provided {len(v)} snippets"} for d, v in doc_snippets.items()]
        return {"ok": True, "similarities": sims, "conflicts": confs, "synthesis": synth, "citations": cits, "warning": str(e)}


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


def adaptive_explain(question: str, level: str = "Undergrad", temperature: float = 0.2) -> Dict[str, Any]:
    """Generate an explanation tailored to the requested ELI level, using RAG context and Gemini.

    Falls back to a template-based rewrite if Gemini is unavailable.
    """
    eng = RAGEngine.shared()
    chunks = eng.retrieve_context(question, k=4)
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
        client = GeminiClient(temperature=temperature)
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
    """Attempt symbolic math; render LaTeX and steps. Optional plot if available.

    Accepts expressions like:
    - simplify: "simplify (x^2 + 2x + 1)"
    - differentiate: "differentiate sin(x)"
    - integrate: "integrate x^2"
    - solve: "solve x^2 = 4 for x"
    """
    if sp is None:
        return {"ok": False, "error": "sympy not installed", "steps": ["Install sympy for full math features."]}

    s = user_input.strip()
    try:
        if s.lower().startswith("simplify"):
            expr_str = s[len("simplify"):].strip()
            x = sp.symbols('x')
            expr = sp.sympify(expr_str)
            simp = sp.simplify(expr)
            return {"ok": True, "kind": "simplify", "latex": sp.latex(simp), "steps": ["Parsed expression", "Applied algebraic simplification"]}
        if s.lower().startswith("differentiate") or s.lower().startswith("derivative"):
            expr_str = s.split(" ", 1)[1].strip()
            x = sp.symbols('x')
            expr = sp.sympify(expr_str)
            deriv = sp.diff(expr, x)
            return {"ok": True, "kind": "differentiate", "latex": sp.latex(deriv), "steps": ["Parsed expression", "Differentiated with respect to x"]}
        if s.lower().startswith("integrate"):
            expr_str = s[len("integrate"):].strip()
            x = sp.symbols('x')
            expr = sp.sympify(expr_str)
            integ = sp.integrate(expr, x)
            return {"ok": True, "kind": "integrate", "latex": sp.latex(integ) + "+ C", "steps": ["Parsed expression", "Integrated with respect to x"]}
        if s.lower().startswith("solve"):
            body = s[len("solve"):].strip()
            x = sp.symbols('x')
            if " for " in body:
                expr_str, var = body.split(" for ", 1)
                var_sym = sp.symbols(var.strip())
            else:
                expr_str, var_sym = body, x
            if "=" in expr_str:
                left, right = expr_str.split("=", 1)
                sol = sp.solve(sp.Eq(sp.sympify(left), sp.sympify(right)), var_sym)
            else:
                sol = sp.solve(sp.sympify(expr_str), var_sym)
            return {"ok": True, "kind": "solve", "latex": sp.latex(sol), "steps": ["Parsed equation", "Solved for variable"]}
        # Fallback attempt: just render LaTeX of the expression
        expr = sp.sympify(s)
        return {"ok": True, "kind": "expr", "latex": sp.latex(expr), "steps": ["Parsed expression", "Rendered LaTeX"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "steps": ["Could not parse expression."]}