"""GeminiToolChat: any turn may move to the next model in the failover chain; a named model is never swapped."""

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
        self.model, self.plan, self.sent = model, plan, []

    def send_message(self, payload):
        self.sent.append(payload)
        item = self.plan.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Chats:
    def __init__(self, plans):
        self.plans, self.created = plans, []

    def create(self, model, config):
        self.created.append(model)
        self.last = Chat(model, self.plans.setdefault(model, []))
        return self.last


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


QUOTA_DAY = FakeAPIError(
    429,
    "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash, "
    "description: Generate content requests per day limit exceeded on Free Tier. Please retry in 6h48m42.99s. "
    "'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'retryDelay': '24522s'",
)
SEARCH = Resp(Part(call=Call("search_documents", {"query": "heap"})))
RESULTS = [ToolResult("search_documents", {"count": 1, "passages": [{"doc": "heaps.pdf", "page": 1, "text": "A binary heap is a complete tree."}]})]


def test_a_later_turn_out_of_quota_moves_to_the_next_model_with_the_results_so_far():
    # The live failure (2026-11-22 01:11 UTC): turn 2 got a daily-quota 429 and the run ended with an error.
    chat, chats = make({DEFAULT: [SEARCH, QUOTA_DAY], LITE: [Resp(Part(text="A heap is a tree. [heaps.pdf (page 1)]"))]})
    chat.send("what is a heap")
    turn = chat.send(RESULTS)
    assert turn.text.startswith("A heap is a tree") and chats.created == [DEFAULT, LITE]
    assert chat.model == LITE and chat.turn_models == [DEFAULT, LITE]
    replay = chats.last.sent[0]
    assert isinstance(replay, str)  # plain text: the first model's thought signatures would not be valid on another
    assert "what is a heap" in replay and 'CALL search_documents {"query": "heap"}' in replay and "A binary heap is a complete tree." in replay
    assert "Do not repeat these calls" in replay


def test_a_later_turn_overloaded_moves_on_without_waiting_on_retries():
    chat, chats = make({DEFAULT: [SEARCH, OVERLOADED], LITE: [Resp(Part(text="done"))]})
    chat.send("hi")
    assert chat.send(RESULTS).text == "done" and chats.created == [DEFAULT, LITE]


def test_after_moving_the_next_turn_continues_the_new_conversation():
    chat, chats = make({DEFAULT: [SEARCH, QUOTA_DAY], LITE: [SEARCH, Resp(Part(text="answer"))]})
    chat.send("hi")
    chat.send(RESULTS)
    assert chat.send(RESULTS).text == "answer"
    assert chats.created == [DEFAULT, LITE] and not isinstance(chats.last.sent[1], str)  # function results, not another replay
    assert chat.turn_models == [DEFAULT, LITE, LITE]


def test_a_later_turn_with_every_model_exhausted_raises_the_last_error():
    chat, chats = make({DEFAULT: [SEARCH, QUOTA_DAY], LITE: [QUOTA_DAY], SECOND: [QUOTA_DAY], THIRD: [QUOTA_DAY]})
    chat.send("hi")
    with pytest.raises(FakeAPIError, match="RESOURCE_EXHAUSTED"):
        chat.send(RESULTS)
    assert chats.created == [DEFAULT, LITE, SECOND, THIRD]


def test_a_named_model_is_retried_on_later_turns_but_never_swapped():
    chat, chats = make({LITE: [SEARCH, OVERLOADED, Resp(Part(text="done"))]}, model=LITE)
    chat.send("hi")
    assert chat.send(RESULTS).text == "done" and chats.created == [LITE]


def test_no_model_is_tried_after_the_run_deadline(monkeypatch):
    chat, chats = make({DEFAULT: [SEARCH, OVERLOADED], LITE: [Resp(Part(text="too late"))]})
    chat.send("hi")
    chat.limit_to(tool_chat.time.monotonic() - 1)  # the agent run is already over its deadline
    with pytest.raises(FakeAPIError):
        chat.send(RESULTS)
    assert chats.created == [DEFAULT]


def test_a_model_out_of_daily_quota_is_skipped_by_the_next_run():
    chat, chats = make({DEFAULT: [QUOTA_DAY], LITE: [Resp(Part(text="one"))]})
    assert chat.send("hi").text == "one"
    chat2, chats2 = make({LITE: [Resp(Part(text="two"))]})
    assert chat2.send("hi").text == "two"
    assert chats2.created == [LITE] and chat2.turn_models == [LITE]  # no wasted call to the exhausted model


def test_quota_memory_expires(monkeypatch):
    chat, _ = make({DEFAULT: [QUOTA_DAY], LITE: [Resp(Part(text="one"))]})
    chat.send("hi")
    now = tool_chat.time.monotonic()
    monkeypatch.setattr(llm_config.time, "monotonic", lambda: now + llm_config.QUOTA_MEMORY_MAX_S + 1)
    chat2, chats2 = make({DEFAULT: [Resp(Part(text="back"))]})
    assert chat2.send("hi").text == "back" and chats2.created == [DEFAULT]


def test_an_overload_is_not_remembered():
    chat, _ = make({DEFAULT: [OVERLOADED], LITE: [Resp(Part(text="one"))]})
    chat.send("hi")
    chat2, chats2 = make({DEFAULT: [Resp(Part(text="fine now"))]})
    assert chat2.send("hi").text == "fine now" and chats2.created == [DEFAULT]


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
