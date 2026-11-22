"""Tool (function) calling, independent of the model provider.

A *tool chat* is a conversation in which the model may answer with text or ask for tools to be run. The
caller sends either a user message or the results of the tools the model asked for, and gets back a
`TurnResult`: some text, some tool calls, or both. The model decides what to call; the caller decides whether
to run it. Gemini implements this with its native function calling; other providers raise
`ToolCallingUnsupported` until they are added.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Tuple, Union


class ToolCallingUnsupported(RuntimeError):
    """The configured provider cannot do tool calling."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema object


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    name: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class TurnResult:
    text: str = ""
    calls: List[ToolCall] = field(default_factory=list)


class ToolChat(Protocol):
    def send(self, message: Union[str, List[ToolResult]]) -> TurnResult: ...


REPLAY_NOTE = (
    "This conversation started on another model, which became unavailable part-way. Below are the student's task and "
    "every tool call made so far with its result. Do not repeat these calls; continue from here: call another tool if you "
    "still need one, or write the final answer."
)


def replay_message(task: str, history: List[Tuple[List[ToolCall], List[ToolResult]]], text: str = "") -> str:
    """The run so far as one plain-text message, for a model that did not see it. Plain text, not the original turns:
    function-call turns carry the first model's thought signatures, which another model would reject."""
    lines = [REPLAY_NOTE, "", "TASK:", task]
    for i, (calls, results) in enumerate(history, 1):
        for call in calls:
            lines.append(f"\nSTEP {i} CALL {call.name} {json.dumps(call.args, sort_keys=True, default=str)}")
        for r in results:
            lines.append(f"STEP {i} RESULT {r.name} {json.dumps(r.payload, default=str)}")
    if text:
        lines += ["", text]
    return "\n".join(lines)


class GeminiToolChat:
    """Gemini function calling through the SDK's chat object, which keeps the history (including the
    thought signatures newer models require when a function result is sent back).

    Any turn may move to the next model in the failover chain when the current one is overloaded or out of quota (see
    GeminiClient). The first turn simply starts again there; a later turn starts a fresh conversation on the next model
    that replays the task and the tool results collected so far, so no tool is run twice. A model the caller named is
    never swapped. `model` is the model that served the latest turn, and `turn_models` lists one per turn."""

    def __init__(self, client: Any, system: str, tools: List[ToolSpec], temperature: float | None = None):
        from .llm_config import RETRY_ATTEMPTS, _backoff_seconds, _is_model_missing, _is_transient, _should_fail_over, _total_budget_s, genai_types

        if genai_types is None:
            raise RuntimeError("google-genai is not installed. Please run: pip install google-genai")
        self._types = genai_types
        self._retry = (RETRY_ATTEMPTS, _is_transient, _backoff_seconds)
        self._switchable = lambda e: _is_model_missing(e) or _should_fail_over(e)
        self._budget = _total_budget_s()
        self._deadline: float | None = None
        declarations = [
            genai_types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters) for t in tools
        ]
        self._config = config = genai_types.GenerateContentConfig(
            system_instruction=system,
            tools=[genai_types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),  # we run the tools ourselves
            temperature=client.temperature if temperature is None else float(temperature),
        )
        self._names = client._candidates() if client._fail_over else [client.model]
        self._index = 0
        self._task: str | None = None
        self._history: List[Tuple[List[ToolCall], List[ToolResult]]] = []  # completed (calls, their results) pairs
        self._last_calls: List[ToolCall] = []
        self.model = self._names[0]
        self.turn_models: List[str] = []
        self._owner = client  # keeps the SDK client alive: when it is freed the SDK closes its connection mid-run
        self._chat = client._client.chats.create(model=self.model, config=config)

    def limit_to(self, deadline: float) -> None:
        """Start no new model attempt after `deadline` (a time.monotonic() value), e.g. the agent run's deadline."""
        self._deadline = deadline

    def _out_of_time(self, started_at: float) -> bool:
        now = time.monotonic()
        return now - started_at > self._budget or (self._deadline is not None and now >= self._deadline)

    def _payload(self, message: Union[str, List[ToolResult]], replay: bool) -> Any:
        if replay:  # a fresh conversation on another model: it needs the whole run as text
            if isinstance(message, str):
                return replay_message(self._task or "", self._history, message)
            return replay_message(self._task or "", [*self._history, (self._last_calls, list(message))])
        if isinstance(message, str):
            return message
        return [self._types.Part.from_function_response(name=r.name, response=r.payload) for r in message]

    def send(self, message: Union[str, List[ToolResult]]) -> TurnResult:
        from .llm_config import logger

        attempts, is_transient, backoff = self._retry
        attempt = 0
        started_at = time.monotonic()
        replay = False
        first_turn = not self.turn_models
        while True:
            try:
                resp = self._chat.send_message(self._payload(message, replay and not first_turn))
                break
            except Exception as e:
                note = getattr(self._owner, "note_failure", None)
                if note is not None:
                    note(self.model, e)
                if self._index + 1 < len(self._names) and self._switchable(e) and not self._out_of_time(started_at):
                    failed = self.model
                    self._index += 1
                    self.model = self._names[self._index]
                    logger.warning("Model '%s' failed on agent turn %d (%s); trying '%s'", failed, len(self.turn_models) + 1, str(e)[:90], self.model)
                    self._chat = self._owner._client.chats.create(model=self.model, config=self._config)
                    replay, attempt = True, 0
                    continue  # the failed model does not use up a retry
                attempt += 1
                if is_transient(e) and attempt < attempts and not self._out_of_time(started_at):
                    time.sleep(backoff(e, attempt - 1))
                    continue
                raise
        if isinstance(message, str) and self._task is None:
            self._task = message
        elif not isinstance(message, str):
            self._history.append((self._last_calls, list(message)))
        self.turn_models.append(self.model)
        parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts else []
        text = "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))
        calls = [ToolCall(p.function_call.name, dict(p.function_call.args or {})) for p in parts if getattr(p, "function_call", None)]
        self._last_calls = calls
        return TurnResult(text=text.strip(), calls=calls)
