"""A scripted stand-in for GeminiClient, used by unit tests and by the browser end-to-end server.

No network, no API key. Override `FakeGemini.handler` to script replies, or set `fail_with`
to make every call fail.
"""

from __future__ import annotations

import json
import re


class FakeGemini:
    """Stand-in for GeminiClient. Override `FakeGemini.handler` in a test to script replies."""

    handler = None  # callable(prompt, json_mode) -> str
    fail_with = None  # set to an Exception to make every call fail
    calls: list = []
    echo_context = False  # e2e server: answer from the retrieved context instead of a fixed string

    def __init__(self, model=None, temperature=0.2, **kw):
        if FakeGemini.fail_with is not None and isinstance(FakeGemini.fail_with, RuntimeError):
            raise FakeGemini.fail_with
        self.model = model or "fake-model"
        self.temperature = temperature

    @staticmethod
    def default_reply(prompt: str, json_mode: bool) -> str:
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
        if FakeGemini.echo_context and "study corpus" in prompt:
            return "1. What is a binary heap?\n2. How does insert work in a heap?\n3. What is a priority queue?"
        if FakeGemini.echo_context:
            # Answer from the first retrieved passage so end-to-end tests can see real retrieval.
            m = re.search(r"^- \[(.+?)\] (.+)$", prompt, re.MULTILINE)
            if m:
                return f"From your material: {m.group(2)[:140]} [{m.group(1)}]"
            return "I could not find that in your sources."
        return "A linked list is a chain of nodes. [heaps.pdf (page 1)]"

    def _reply(self, prompt, json_mode):
        FakeGemini.calls.append(prompt)
        if FakeGemini.fail_with is not None:
            raise FakeGemini.fail_with
        return (FakeGemini.handler or FakeGemini.default_reply)(prompt, json_mode)

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
