"""The study tools an agent (or an MCP client) can call.

One registry, two users: the ReAct agent (`backend/react_agent.py`) offers these tools to the model, and the
MCP server (`backend/mcp_server.py`) offers the same tools to any MCP client. Each tool has a name, a
description the model reads, a JSON Schema for its arguments, and a handler that returns a small, bounded
JSON-able dict. Handlers never raise to the caller: bad arguments or failures come back as `{"error": ...}`,
which the model can read and recover from.

Read-only tools are always available. Tools that change data (`writes=True`) exist only when the deployment
turns them on, because a public deployment must not let a model write to a shared database.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .tool_chat import ToolSpec

PASSAGE_CHARS = 900  # per passage returned by a search
PAGE_CHARS = 4000  # for a whole page read
RESULT_CHARS = 6000  # the most one tool result may hand back to the model


@dataclass
class ToolContext:
    """What the handlers work with, plus a record of every passage they handed out (used to check citations)."""

    engine: Any
    leetcode: Optional[Callable[[], Any]] = None  # loads the problem bank on first use
    study: Optional[Callable[[], Any]] = None  # the flashcard store
    passages: List[Dict[str, Any]] = field(default_factory=list)

    def remember(self, items: List[Dict[str, Any]]) -> None:
        seen = {(p.get("doc"), p.get("page"), (p.get("text") or "")[:80]) for p in self.passages}
        for it in items:
            key = (it.get("doc"), it.get("page"), (it.get("text") or "")[:80])
            if key not in seen:
                seen.add(key)
                self.passages.append(it)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    run: Callable[[ToolContext, Dict[str, Any]], Dict[str, Any]]
    writes: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)


class ToolArgError(ValueError):
    pass


def _text(args: Dict[str, Any], key: str, max_len: int, required: bool = True) -> str:
    v = args.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ToolArgError(f"'{key}' is required")
        return ""
    if not isinstance(v, str):
        raise ToolArgError(f"'{key}' must be text")
    return v.strip()[:max_len]


def _int(args: Dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    v = args.get(key, default)
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ToolArgError(f"'{key}' must be a whole number") from None
    return max(low, min(high, n))


def _passage(c: Dict[str, Any], limit: int = PASSAGE_CHARS) -> Dict[str, Any]:
    out: Dict[str, Any] = {"doc": c.get("doc"), "text": (c.get("text") or "")[:limit]}
    if c.get("page") is not None:  # leave the key out for sources without pages, so a model does not write "(null)"
        out["page"] = c["page"]
    if c.get("end_page"):
        out["end_page"] = c["end_page"]
    return out


# --------------------------------------------------------------------------- handlers
def _search_documents(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    query = _text(args, "query", 500)
    k = _int(args, "k", 4, 1, 8)
    chunks = ctx.engine.retrieve_context(query, k=k)
    passages = [{**_passage(c), "score": round(float(c.get("score") or 0), 3)} for c in chunks]
    ctx.remember([{**_passage(c), "score": float(c.get("score") or 0)} for c in chunks])
    return {"count": len(passages), "passages": passages} if passages else {"count": 0, "passages": [], "note": "No matching passages. Try different words."}


def _list_documents(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for c in ctx.engine._docstore_iter():
        counts[c.get("doc") or "?"] = counts.get(c.get("doc") or "?", 0) + 1
    docs = [{"doc": d, "passages": n} for d, n in sorted(counts.items())]
    return {"count": len(docs), "documents": docs[:50]}


def _read_page(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    name = _text(args, "document", 300)
    page = _int(args, "page", 1, 1, 100000)
    chunks = ctx.engine._docstore_iter()
    names = sorted({c.get("doc") or "" for c in chunks})
    exact = [n for n in names if n.lower() == name.lower()]
    near = [n for n in names if name.lower() in n.lower()]
    chosen = exact[0] if exact else (near[0] if len(near) == 1 else None)
    if chosen is None:
        return {"error": f"Unknown document '{name}'.", "documents": names[:20]}
    of_doc = [c for c in chunks if c.get("doc") == chosen]
    if of_doc and not any(c.get("page") for c in of_doc):
        # Markdown, web pages and transcripts have no page numbers: hand back the start of the document instead of failing.
        ctx.remember([{**_passage(c, 4000), "score": 0.0} for c in of_doc[:3]])
        text = "\n\n".join((c.get("text") or "") for c in of_doc)[:PAGE_CHARS]
        return {"doc": chosen, "page": None, "text": text, "note": "This document has no page numbers; this is its beginning. Cite it as [" + chosen + "]."}
    hits = [c for c in of_doc if (c.get("page") or 0) <= page <= (c.get("end_page") or c.get("page") or 0)]
    if not hits:
        return {"error": f"No text found on page {page} of {chosen}. Use search_documents to find the right page."}
    ctx.remember([{**_passage(c, 4000), "score": 0.0} for c in hits])
    text = "\n\n".join((c.get("text") or "") for c in hits)[:PAGE_CHARS]
    return {"doc": chosen, "page": page, "text": text}


def _solve_math(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    from .safe_math import solve_request

    res = solve_request(_text(args, "expression", 300))
    out = {k: res[k] for k in ("ok", "kind", "result", "latex", "error") if k in res and res[k] is not None}
    if res.get("steps"):
        out["steps"] = [str(s)[:200] for s in res["steps"][:6]]
    return out


def _find_leetcode_problem(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    if ctx.leetcode is None:
        return {"error": "The LeetCode problem bank is not available here."}
    query = _text(args, "query", 200)
    difficulty = _text(args, "difficulty", 10, required=False)
    if difficulty and difficulty.lower() not in {"easy", "medium", "hard"}:
        raise ToolArgError("'difficulty' must be Easy, Medium or Hard")
    found = ctx.leetcode().search(query, top_k=5, difficulty=[difficulty] if difficulty else None)
    return {"count": len(found), "problems": [{k: p.get(k) for k in ("pid", "title", "difficulty", "topics", "url")} for p in found]}


def _save_flashcard(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    if ctx.study is None:
        return {"error": "Flashcards are not available here."}
    card = ctx.study().add_card(_text(args, "front", 1200), _text(args, "back", 1200), source="agent")
    return {"saved": True, "id": card.get("id")}


def _obj(props: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


ALL_TOOLS: List[Tool] = [
    Tool(
        "search_documents",
        "Search the student's own study material (textbooks, notes, lecture transcripts) for passages about a topic. "
        "Returns passages with their document name and page, which you must use to cite. Call it with specific keywords.",
        _obj({"query": {"type": "string", "description": "What to look for"}, "k": {"type": "integer", "description": "How many passages (1-8, default 4)"}}, ["query"]),
        _search_documents,
    ),
    Tool("list_documents", "List the documents in the student's study material, with how many passages each has.", _obj({}, []), _list_documents),
    Tool(
        "read_page",
        "Read the full text of one page of a document. Use it after a search when you need the surrounding detail.",
        _obj({"document": {"type": "string", "description": "Document name, as returned by search or list_documents"}, "page": {"type": "integer"}}, ["document", "page"]),
        _read_page,
    ),
    Tool(
        "solve_math",
        "Do symbolic math exactly: differentiate, integrate, simplify, expand, factor or solve. Examples: 'integrate x^2 + 3x', 'solve x^2 - 5x + 6 = 0'. Prefer this to doing algebra yourself.",
        _obj({"expression": {"type": "string"}}, ["expression"]),
        _solve_math,
    ),
    Tool(
        "find_leetcode_problem",
        "Search the bank of 1,825 LeetCode problems by topic or title. Returns id, title, difficulty, topics and link.",
        _obj({"query": {"type": "string"}, "difficulty": {"type": "string", "description": "Easy, Medium or Hard (optional)"}}, ["query"]),
        _find_leetcode_problem,
    ),
    Tool(
        "save_flashcard",
        "Save a spaced-repetition flashcard to the student's deck. Only use it when the student asked for flashcards.",
        _obj({"front": {"type": "string", "description": "The question"}, "back": {"type": "string", "description": "The answer"}}, ["front", "back"]),
        _save_flashcard,
        writes=True,
    ),
]


def default_tools(allow_writes: bool = False) -> List[Tool]:
    """The read-only tools, plus the ones that change data only when the deployment allows it."""
    return [t for t in ALL_TOOLS if allow_writes or not t.writes]


def bounded(payload: Dict[str, Any], limit: int = RESULT_CHARS) -> Dict[str, Any]:
    """A tool result small enough to hand back to the model; oversized ones are cut and marked."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return payload
    return {"truncated": True, "text": text[:limit]}


def run_tool(tools: List[Tool], ctx: ToolContext, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one tool. Never raises: problems come back as {"error": ...} for the model to read."""
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(t.name for t in tools)}."}
    try:
        return bounded(tool.run(ctx, args if isinstance(args, dict) else {}))
    except ToolArgError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # a tool failure must not end the run, and must not leak internals
        return {"error": f"{name} failed ({type(e).__name__})."}


def summarize(name: str, result: Dict[str, Any]) -> str:
    """One line for a trace display."""
    if "error" in result:
        return str(result["error"])[:160]
    if name == "search_documents":
        docs = sorted({p.get("doc") for p in result.get("passages", []) if p.get("doc")})
        return f"{result.get('count', 0)} passages" + (f" from {', '.join(docs)}" if docs else "")
    if name == "list_documents":
        return f"{result.get('count', 0)} documents"
    if name == "read_page":
        where = f"page {result.get('page')}" if result.get("page") else "start"
        return f"{result.get('doc')} {where}, {len(result.get('text', ''))} characters"
    if name == "solve_math":
        return str(result.get("result") or result.get("latex") or "done")[:160]
    if name == "find_leetcode_problem":
        return f"{result.get('count', 0)} problems"
    if name == "save_flashcard":
        return "saved"
    return "done"
