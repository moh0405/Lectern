"""A scripted stand-in for GeminiClient, used by unit tests and by the browser end-to-end server.

No network, no API key. Override `FakeGemini.handler` to script replies, or set `fail_with`
to make every call fail.
"""

from __future__ import annotations

import json
import re


_WORD = re.compile(r"[a-z][a-z0-9]{3,}")
_NEGATION = re.compile(r"\b(not|never|no|cannot|can't|doesn't|isn't|don't|without)\b", re.I)
_HEDGE = re.compile(r"\b(i think|maybe|probably|i guess)\b", re.I)
_METHOD = re.compile(r"\b(hash|map|lookup|pointers?|stack|sort|loop)\b", re.I)
FORCE_REJECTION = "[e2e: reject first draft]"  # in the original question: the first draft leaks, the retry is clean


def scripted_attempt_feedback(prompt: str) -> dict:
    """A deterministic judge for Try first feedback, so tests and the e2e server need no model. Not a real tutor: a unit
    sharing two or more words with a passage is judged against it (contradicted when the unit is negated, supported
    otherwise, and supported but uncited when it hedges with "I think"/"maybe"); anything else is not covered."""
    passages = re.findall(r"^- \[(.+?)\] (.+)$", prompt, re.M)
    units = re.findall(r"^(Step|Line|Sentence) (\d+): (.+)$", prompt, re.M)
    problem_mode = "JUDGE: problem" in prompt
    items = []
    for _kind, n, text in units:
        words = set(_WORD.findall(text.lower()))
        best, overlap = None, 0
        for label, body in passages:
            shared = len(words & set(_WORD.findall(body.lower())))
            if shared > overlap:
                best, overlap = label, shared
        if problem_mode and (best is None or overlap < 2) and _METHOD.search(text):
            # Reasoned from the problem: no citation, a pointer only. A negated method step is the scripted wrong one.
            wrong = bool(_NEGATION.search(text))
            items.append({"unit": int(n), "verdict": "contradicted" if wrong else "supported", "basis": "problem", "citations": [],
                          "note": "What happens on a small input if you trace this?" if wrong else "This reasoning works for the statement."})
        elif best is None or overlap < 2:
            items.append({"unit": int(n), "verdict": "not_covered", "note": "Your passages do not mention this.", "citations": []})
        elif _HEDGE.search(text):
            items.append({"unit": int(n), "verdict": "supported", "note": "This sounds right, but say which passage backs it.", "citations": []})
        elif _NEGATION.search(text):
            items.append({"unit": int(n), "verdict": "contradicted", "note": f"Compare this with what {best} says.", "citations": [best]})
        else:
            items.append({"unit": int(n), "verdict": "supported", "note": f"This matches {best}.", "citations": [best]})
    wrong = [i["unit"] for i in items if i["verdict"] == "contradicted"]
    summary = f"Look at step {wrong[0]} first." if wrong else "Your attempt is on track so far."
    return {"answer_key": "SCRIPTED-HIDDEN-ANSWER stays on the server." if problem_mode else "", "summary": summary, "items": items}


def scripted_similar_question(prompt: str) -> dict:
    """A deterministic practice question built from the first passage's words; each one already asked shifts the words."""
    passages = re.findall(r"^- \[(.+?)\] (.+)$", prompt, re.M)
    if not passages:
        return {"question": "", "answer_key": "", "citations": []}
    label, body = passages[0]
    if FORCE_REJECTION in prompt and "YOUR PREVIOUS DRAFT WAS REJECTED" not in prompt:
        return {"question": "The answer is SCRIPTED-LEAKED-DRAFT, so what is it?", "answer_key": "SCRIPTED-HIDDEN-ANSWER stays on the server.", "citations": [label]}
    words = list(dict.fromkeys(w for w in _WORD.findall(body.lower()) if len(w) > 4))
    shift = len(re.findall(r"^\* ", prompt, re.M))
    picked = (words[shift:shift + 3] or words[:3])
    return {"question": f"Practice {shift + 1}: how do {', '.join(picked)} relate in a new example?",
            "answer_key": "SCRIPTED-HIDDEN-ANSWER stays on the server.", "citations": [label]}


class FakeGemini:
    """Stand-in for GeminiClient. Override `FakeGemini.handler` in a test to script replies."""

    handler = None  # callable(prompt, json_mode) -> str
    fail_with = None  # set to an Exception to make every call fail
    calls: list = []
    tool_script = None  # callable(turn, message) -> TurnResult, for tool-calling tests
    echo_context = False  # e2e server: answer from the retrieved context instead of a fixed string

    def __init__(self, model=None, temperature=0.2, **kw):
        if FakeGemini.fail_with is not None and isinstance(FakeGemini.fail_with, RuntimeError):
            raise FakeGemini.fail_with
        self.model = model or "fake-model"
        self.temperature = temperature

    @staticmethod
    def default_reply(prompt: str, json_mode: bool) -> str:
        if "TASK: ATTEMPT_FEEDBACK" in prompt:
            return json.dumps(scripted_attempt_feedback(prompt))
        if "TASK: SIMILAR_QUESTION" in prompt:
            return json.dumps(scripted_similar_question(prompt))
        if "TASK: REWRITE_QUERY" in prompt:  # the agentic workflow's planning calls
            return json.dumps({"query": "binary heap priority queue data structure"})
        if "TASK: GRADE_PASSAGES" in prompt:
            return json.dumps({"sufficient": True, "reason": "The passages define the concept.", "better_query": ""})
        if json_mode and "study map" in prompt.lower():
            return json.dumps({
                "nodes": [{"id": "list", "label": "Linked list"}, {"id": "node", "label": "Node"},
                          {"id": "list", "label": "dup"}],
                "edges": [{"from": "list", "to": "node", "label": "has"}, {"from": "list", "to": "ghost"}],
            })
        if json_mode and "socratic" in prompt.lower():
            return json.dumps({"questions": ["What is a node?", "How are nodes linked?"], "hints": ["h1", "h2", "h3"]})
        if json_mode and "synthesizer" in prompt.lower():
            return json.dumps({"similarities": ["both define it"], "conflicts": [], "synthesis": "Unified view.",
                               "citations": [{"doc": "a.pdf", "point": "defines it"}, "loose citation"]})
        if "flashcard author" in prompt:
            return json.dumps({"cards": [
                {"front": "What is a binary heap?", "back": "A complete binary tree where each parent is ordered before its children."},
                {"front": "What is a heap used for?", "back": "Implementing a priority queue."},
            ]})
        if FakeGemini.echo_context and "algorithms mentor" in prompt:
            return "## Approach\n\n- Use a hash map from value to index.\n\n```python\ndef solve(nums):\n    return nums\n```"
        if FakeGemini.echo_context and "study corpus" in prompt:
            return "1. What is a binary heap?\n2. How does insert work in a heap?\n3. What is a priority queue?"
        if FakeGemini.echo_context:
            # Answer from the first retrieved passage so end-to-end tests can see real retrieval.
            m = re.search(r"^- \[(.+?)\] (.+)$", prompt, re.MULTILINE)
            if m:
                if "previous answer cited sources" in prompt:  # the agentic workflow's corrective retry: behave this time
                    return f"From your material: {m.group(2)[:140]} [{m.group(1)}]"
                if "in prose" in prompt.lower():  # e2e: a failover model that cites in parentheses, not brackets
                    label = m.group(1)
                    lm = re.match(r"(.+?) \((pages? [\d-]+)\)$", label)
                    cite = f"(*{lm.group(1)}*, {lm.group(2).replace('-', '–')})" if lm else f"(*{label}*)"
                    return (f"From your material: {m.group(2)[:140]} {cite}.\n\nInsertion and removal take O(log n) time "
                            f"(see below), one swap per level (O(1) each). It is the usual way to implement a priority "
                            f"queue ([{label}]).")
                if "hallucinate" in prompt.lower():  # e2e: a model that invents a source
                    return f"From your material: {m.group(2)[:100]} [{m.group(1)}] and also [Invented Notes.pdf (page 9)]"
                return f"From your material: {m.group(2)[:140]} [{m.group(1)}]"
            return "I could not find that in your sources."
        return "A linked list is a chain of nodes. [heaps.pdf (page 1)]"

    def _reply(self, prompt, json_mode):
        FakeGemini.calls.append(prompt)
        if FakeGemini.fail_with is not None:
            raise FakeGemini.fail_with
        return (FakeGemini.handler or FakeGemini.default_reply)(prompt, json_mode)

    def start_tool_chat(self, system, tools, temperature=None):
        if FakeGemini.fail_with is not None and isinstance(FakeGemini.fail_with, RuntimeError):
            raise FakeGemini.fail_with
        return FakeToolChat(self.model, system, tools)

    def list_supported_models(self):
        return ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-flash-latest"]

    def generate(self, prompt, temperature=None, json_mode=False):
        try:
            return {"ok": True, "model": self.model, "answer": self._reply(prompt, json_mode)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stream(self, prompt, temperature=None, json_mode=False):
        text = self._reply(prompt, json_mode)
        words = text.split(" ")
        for i, w in enumerate(words):
            yield w + ("" if i == len(words) - 1 else " ")


class FakeToolChat:
    """Stand-in for a Gemini tool chat. Script it with `FakeGemini.tool_script = fn(turn, message) -> TurnResult`.

    Without a script it behaves like a sensible model: the first turn searches the study material for the task, and
    once it has results it answers from the first passage (so browser tests can see real tool results)."""

    def __init__(self, model, system, tools):
        self.model = model
        self.system = system
        self.tool_names = [t.name for t in tools]
        self.turn = 0

    def send(self, message):
        from backend.tool_chat import ToolCall, TurnResult

        FakeGemini.calls.append(f"TOOLCHAT turn {self.turn}: {message if isinstance(message, str) else [(r.name, r.payload) for r in message]}")
        if FakeGemini.fail_with is not None:
            raise FakeGemini.fail_with
        turn, self.turn = self.turn, self.turn + 1
        if turn == 0 and isinstance(message, str):
            self.task = message
        if turn == 1 and "busy model" in getattr(self, "task", "").lower():
            # e2e: the first model runs out of quota after its first turn and the failover chain's next model carries on
            # (the real move is GeminiToolChat's, tested in tests/test_tool_chat.py; this only shows it to the page)
            self.model = "gemini-3.1-flash-lite"
        script = getattr(FakeGemini, "tool_script", None)
        if script is not None:
            return script(turn, message)
        if turn == 0:
            return TurnResult(calls=[ToolCall("search_documents", {"query": str(message)[:120]})])
        passages = []
        for r in message if isinstance(message, list) else []:
            passages += r.payload.get("passages", [])
        if passages:
            p = passages[0]
            ref = f"{p['doc']} (page {p['page']})" if p.get("page") else p["doc"]
            if "bare page" in getattr(self, "task", "").lower() and p.get("page"):  # e2e: a model that omits the parentheses
                ref = f"{p['doc']} page {p['page']}"
            return TurnResult(text=f"From your material: {p['text'][:140]} [{ref}]")
        return TurnResult(text="I could not find that in your sources.")
