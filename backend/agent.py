"""An agentic way to answer, built as a LangGraph workflow, for questions the plain pipeline may get wrong.

    rewrite -> retrieve -> grade --(passages weak, one retry left)--> retrieve
                              |
                              v
                           answer -> verify --(cites passages it was not given, once)--> regenerate -> verify -> end

Nothing here replaces the normal pipeline; it reuses it (`RAGEngine.retrieve_context`, `generate_prompt`,
`check_answer`) and adds three decisions the plain path never makes:

1. Rewrite the question into a better search query (expand "BFS", name the concept). Retrieval runs on the
   original question *and* the rewrite and merges them, so a bad rewrite cannot make results worse than the
   plain path's.
2. Grade the passages: if the model says they do not answer the question, search once more with a query it
   suggests.
3. Verify the answer's citations; if it cited sources it was never given, ask once more with the valid labels.

Every model call is counted against the spend cap like any other, and one question makes at most MAX_LLM_CALLS.
Rewrite and grade failures degrade quietly to the plain behaviour; a failure of the answer itself is an error.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from .citations import check_answer

MAX_RETRIEVALS = 2  # the first search plus one retry
MAX_LLM_CALLS = 6  # rewrite, grade (x2), answer, regenerate: the most one question can use

# Errors that must stop the run instead of being swallowed as "planning failed": the model is out of quota or capped.
_STOP_MARKERS = ("resource_exhausted", "exceeded your current quota", "daily limit", "calls are paused")


class AgentState(TypedDict, total=False):
    question: str
    k: int
    mode: Optional[str]
    queries: List[str]
    chunks: List[Dict[str, Any]]
    attempts: int
    sufficient: bool
    next_query: str
    prompt: str
    answer: str
    check: Dict[str, Any]
    regenerated: bool
    llm_calls: int
    model: Optional[str]
    steps: int


def _json_object(text: str) -> Optional[Dict[str, Any]]:
    """The first JSON object in a model reply (it may be wrapped in a code fence or prose)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        value = json.loads(m.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _key(c: Dict[str, Any]) -> tuple:
    return (c.get("doc"), c.get("page"), (c.get("text") or "")[:80])


def _merge(first: List[Dict[str, Any]], second: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    """Union of two retrievals, best score first, no duplicates."""
    seen: Dict[tuple, Dict[str, Any]] = {}
    for c in [*first, *second]:
        key = _key(c)
        if key not in seen or float(c.get("score") or 0) > float(seen[key].get("score") or 0):
            seen[key] = c
    return sorted(seen.values(), key=lambda c: -float(c.get("score") or 0))[:k]


def build_agent(engine: Any, llm: Any, temperature: float):
    """Compile the graph. `engine` provides retrieval and prompts; `llm` is a client with generate() and stream()."""

    def planning_call(state: AgentState, prompt: str) -> Optional[Dict[str, Any]]:
        """A small JSON-answering call whose failure is not fatal. Returns the parsed object, or None."""
        if state.get("llm_calls", 0) >= MAX_LLM_CALLS:
            return None
        try:
            res = llm.generate(prompt, temperature=0.0, json_mode=True)
        except Exception as e:
            if any(m in str(e).lower() for m in _STOP_MARKERS):
                raise
            return None
        state["llm_calls"] = state.get("llm_calls", 0) + 1
        if not res.get("ok", True):
            if any(m in str(res.get("error", "")).lower() for m in _STOP_MARKERS):
                raise RuntimeError(str(res.get("error")))
            return None
        return _json_object(res.get("answer") or "")

    def step(writer: StreamWriter, state: AgentState, name: str, detail: str) -> None:
        state["steps"] = state.get("steps", 0) + 1
        writer({"event": "step", "data": {"name": name, "detail": detail}})

    def rewrite(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        out = planning_call(
            state,
            "TASK: REWRITE_QUERY\n"
            "Rewrite the student's question as a short search query for a computer-science textbook index. "
            "Expand acronyms and name the concepts involved. Reply with JSON only: {\"query\": \"...\"}.\n\n"
            f"Question: {state['question']}",
        )
        query = out.get("query") if out else None
        if isinstance(query, str) and 2 <= len(query.strip()) <= 200 and query.strip().lower() != state["question"].strip().lower():
            step(writer, state, "rewrite", f"Searching for: {query.strip()}")
            return {"queries": [query.strip()], "llm_calls": state.get("llm_calls", 0), "steps": state.get("steps", 0)}
        step(writer, state, "rewrite", "Kept your wording")
        return {"queries": [], "llm_calls": state.get("llm_calls", 0), "steps": state.get("steps", 0)}

    def retrieve(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        k = state["k"]
        queries = state.get("queries", [])
        retried = bool(state.get("attempts", 0))
        # Always include the question itself, so a poor rewrite cannot be worse than the plain pipeline.
        chunks = engine.retrieve_context(state["question"], k=k)
        extra = state.get("next_query") if retried else (queries[-1] if queries else None)
        if extra:
            chunks = _merge(chunks, engine.retrieve_context(extra, k=k), k)
        docs = len({c.get("doc") for c in chunks})
        step(writer, state, "retrieve", f"{'Searched again: ' if retried else ''}found {len(chunks)} passage{'s' if len(chunks) != 1 else ''} in {docs} source{'s' if docs != 1 else ''}")
        return {"chunks": chunks, "attempts": state.get("attempts", 0) + 1, "steps": state.get("steps", 0)}

    def grade(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        chunks = state.get("chunks", [])
        listing = "\n\n".join(f"[{i}] {c.get('doc')} (page {c.get('page')}): {(c.get('text') or '')[:600]}" for i, c in enumerate(chunks, 1))
        out = planning_call(
            state,
            "TASK: GRADE_PASSAGES\n"
            "Do these passages contain what is needed to answer the student's question? Reply with JSON only: "
            "{\"sufficient\": true|false, \"reason\": \"one short sentence\", \"better_query\": \"a different search query if not sufficient, else empty\"}.\n\n"
            f"Question: {state['question']}\n\nPassages:\n{listing or '(none)'}",
        )
        sufficient = True if out is None else bool(out.get("sufficient", True))
        better = str(out.get("better_query") or "").strip()[:200] if out else ""
        reason = str(out.get("reason") or "").strip()[:160] if out else ""
        if sufficient or not better or state.get("attempts", 0) >= MAX_RETRIEVALS:
            step(writer, state, "grade", ("Passages look sufficient" if sufficient else "Passages look weak, answering with the best available") + (f": {reason}" if reason else ""))
            return {"sufficient": True, "llm_calls": state.get("llm_calls", 0), "steps": state.get("steps", 0)}
        step(writer, state, "grade", f"Passages look weak ({reason or 'not enough detail'}); searching again")
        return {"sufficient": False, "next_query": better, "llm_calls": state.get("llm_calls", 0), "steps": state.get("steps", 0)}

    def stream_answer(prompt: str, writer: StreamWriter) -> str:
        parts: List[str] = []
        for piece in llm.stream(prompt, temperature=temperature):
            parts.append(piece)
            writer({"event": "token", "data": {"text": piece}})
        if not parts:
            raise RuntimeError("Model returned an empty response (it may have been blocked by a safety filter)")
        return "".join(parts)

    def answer(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        chunks = state.get("chunks", [])
        prompt = engine.generate_prompt(state["question"], chunks, mode=state.get("mode"))
        writer({"event": "meta", "data": {"chunks": chunks}})
        step(writer, state, "answer", "Writing the answer from these passages")
        text = stream_answer(prompt, writer)
        return {"prompt": prompt, "answer": text, "llm_calls": state.get("llm_calls", 0) + 1, "steps": state.get("steps", 0), "model": getattr(llm, "model", None)}

    def verify(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        check = check_answer(state.get("answer", ""), state.get("chunks", []))
        bad = int(check["unverified"])
        step(writer, state, "verify", "Every citation is in the retrieved passages" if bad == 0 else f"{bad} citation{'s' if bad != 1 else ''} not among the retrieved passages")
        return {"check": check, "steps": state.get("steps", 0)}

    def regenerate(state: AgentState, writer: StreamWriter) -> Dict[str, Any]:
        labels = ", ".join(f"[{c.get('doc')}" + (f" (page {c.get('page')})" if c.get("page") else "") + "]" for c in state.get("chunks", []))
        writer({"event": "replace", "data": {"reason": "Some citations were not in the retrieved passages; rewriting the answer"}})
        step(writer, state, "regenerate", "Rewriting with only the valid citations")
        prompt = (
            state["prompt"]
            + "\n\nYour previous answer cited sources that were not provided. Rewrite it, citing only these passages: "
            + labels
            + ". If they do not contain the answer, say so plainly instead of citing anything else."
        )
        text = stream_answer(prompt, writer)
        return {"answer": text, "regenerated": True, "llm_calls": state.get("llm_calls", 0) + 1, "steps": state.get("steps", 0)}

    def after_grade(state: AgentState) -> str:
        return "answer" if state.get("sufficient", True) else "retrieve"

    def after_verify(state: AgentState) -> str:
        bad = int(state.get("check", {}).get("unverified", 0))
        if bad and not state.get("regenerated") and state.get("llm_calls", 0) < MAX_LLM_CALLS:
            return "regenerate"
        return END

    graph = StateGraph(AgentState)
    for name, fn in [("rewrite", rewrite), ("retrieve", retrieve), ("grade", grade), ("answer", answer), ("verify", verify), ("regenerate", regenerate)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", after_grade, {"answer": "answer", "retrieve": "retrieve"})
    graph.add_edge("answer", "verify")
    graph.add_conditional_edges("verify", after_verify, {"regenerate": "regenerate", END: END})
    graph.add_edge("regenerate", "verify")
    return graph.compile()


def run_agent(engine: Any, llm: Any, question: str, k: int = 3, mode: Optional[str] = None, temperature: float = 0.2) -> Iterator[Dict[str, Any]]:
    """Run the workflow, yielding {"event": ..., "data": ...} dicts as it goes: step, meta, token, replace,
    and a final done. Exceptions (for example the model failing mid-answer) propagate to the caller."""
    app = build_agent(engine, llm, temperature)
    final: AgentState = {}
    for kind, payload in app.stream({"question": question, "k": k, "mode": mode, "attempts": 0, "llm_calls": 0, "steps": 0}, stream_mode=["custom", "values"]):
        if kind == "custom":
            yield payload
        else:
            final = payload
    check = final.get("check") or check_answer(final.get("answer", ""), final.get("chunks", []))
    yield {
        "event": "done",
        "data": {
            "model": final.get("model"),
            "citations": check["citations"],
            "unverified_citations": check["unverified"],
            "uncited": check["uncited"],
            "cached": False,
            "llm_calls": final.get("llm_calls", 0),
            "regenerated": bool(final.get("regenerated")),
            "_answer": final.get("answer", ""),
            "_prompt": final.get("prompt", ""),
            "_chunks": final.get("chunks", []),
        },
    }
