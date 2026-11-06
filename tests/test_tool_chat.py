"""GeminiToolChat: a first turn may move to another model; later turns never do."""

from __future__ import annotations

import pytest

from backend import llm_config, tool_chat
from backend.llm_config import GeminiClient
from backend.tool_chat import GeminiToolChat, ToolResult, ToolSpec

from .test_llm_config import ALL, DEFAULT, LITE, SECOND, THIRD, FakeAPIError, FakeClient, FakeModel


class Part:
    def __init__(self, text=None, call=None):
        self.text, self.function_call, self.thought = text, call, False


class Call:
    def __init__(self, name, args):
        self.name, self.args = name, args


class Resp:
    def __init__(self, *parts):
        self.candidates = [type("C", (), {"content": type("K", (), {"parts": list(parts)})()})()]


class Chat:
    def __init__(self, model, plan):
        self.model, self.plan = model, plan

    def send_message(self, payload):
        item = self.plan.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Chats:
    def __init__(self, plans):
        self.plans, self.created = plans, []

    def create(self, model, config):
        self.created.append(model)
        return Chat(model, self.plans.setdefault(model, []))


def make(plans, model=None):
    fake = FakeClient(models=[FakeModel(m) for m in ALL])
    fake.chats = Chats(plans)
    client = GeminiClient(model=model, client=fake)
    tools = [ToolSpec("search_documents", "search", {"type": "object", "properties": {}})]
    return GeminiToolChat(client, "system", tools), fake.chats


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(llm_config.time, "sleep", lambda s: None)
    monkeypatch.setattr(tool_chat.time, "sleep", lambda s: None)
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm_config._resolved_models.clear()


OVERLOADED = FakeAPIError(503, "503 UNAVAILABLE high demand")


def test_a_normal_first_turn_parses_text_and_tool_calls():
    chat, chats = make({DEFAULT: [Resp(Part(text="Let me look."), Part(call=Call("search_documents", {"query": "heap"})))]})
    turn = chat.send("what is a heap")
    assert turn.text == "Let me look." and [(c.name, c.args) for c in turn.calls] == [("search_documents", {"query": "heap"})]
    assert chats.created == [DEFAULT] and chat.model == DEFAULT


def test_an_overloaded_first_turn_starts_again_on_the_next_model():
    chat, chats = make({DEFAULT: [OVERLOADED], LITE: [Resp(Part(text="answer"))]})
    assert chat.send("hi").text == "answer"
    assert chats.created == [DEFAULT, LITE] and chat.model == LITE  # a fresh conversation on the lite model


def test_later_turns_are_retried_but_never_moved_to_another_model():
    chat, chats = make({DEFAULT: [Resp(Part(call=Call("search_documents", {}))), OVERLOADED, OVERLOADED, OVERLOADED]})
    chat.send("hi")
    with pytest.raises(FakeAPIError):
        chat.send([ToolResult("search_documents", {"count": 0})])
    assert chats.created == [DEFAULT]  # the history belongs to the first model, so the run does not hop to another


def test_a_later_turn_recovers_by_retrying_the_same_model():
    chat, chats = make({DEFAULT: [Resp(Part(call=Call("search_documents", {}))), OVERLOADED, Resp(Part(text="done"))]})
    chat.send("hi")
    assert chat.send([ToolResult("search_documents", {})]).text == "done" and chats.created == [DEFAULT]


def test_a_model_named_by_the_caller_is_not_swapped():
    chat, chats = make({LITE: [OVERLOADED] * 3}, model=LITE)
    with pytest.raises(FakeAPIError):
        chat.send("hi")
    assert chats.created == [LITE]


def test_a_bad_key_is_not_passed_to_another_model():
    chat, chats = make({DEFAULT: [FakeAPIError(401, "API key not valid")]})
    with pytest.raises(FakeAPIError):
        chat.send("hi")
    assert chats.created == [DEFAULT]


def test_when_every_model_fails_the_last_error_surfaces():
    chat, chats = make({DEFAULT: [OVERLOADED], LITE: [OVERLOADED], SECOND: [OVERLOADED], THIRD: [OVERLOADED] * 3})
    with pytest.raises(FakeAPIError):
        chat.send("hi")
    assert chats.created == [DEFAULT, LITE, SECOND, THIRD]
