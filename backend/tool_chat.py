"""Tool (function) calling, independent of the model provider.

A *tool chat* is a conversation in which the model may answer with text or ask for tools to be run. The
caller sends either a user message or the results of the tools the model asked for, and gets back a
`TurnResult`: some text, some tool calls, or both. The model decides what to call; the caller decides whether
to run it. Gemini implements this with its native function calling; other providers raise
`ToolCallingUnsupported` until they are added.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Union


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


class GeminiToolChat:
    """Gemini function calling through the SDK's chat object, which keeps the history (including the
    thought signatures newer models require when a function result is sent back)."""

    def __init__(self, client: Any, system: str, tools: List[ToolSpec], temperature: float | None = None):
        from .llm_config import RETRY_ATTEMPTS, _backoff_seconds, _is_model_missing, _is_transient, _should_fail_over, genai_types

        if genai_types is None:
            raise RuntimeError("google-genai is not installed. Please run: pip install google-genai")
        self._types = genai_types
        self._retry = (RETRY_ATTEMPTS, _is_transient, _backoff_seconds)
        self._switchable = lambda e: _is_model_missing(e) or _should_fail_over(e)
        declarations = [
            genai_types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters) for t in tools
        ]
        self._config = config = genai_types.GenerateContentConfig(
            system_instruction=system,
            tools=[genai_types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),  # we run the tools ourselves
            temperature=client.temperature if temperature is None else float(temperature),
        )
        # The first turn may move to another model if the chosen one is overloaded or out of quota (see GeminiClient).
        # After that the history belongs to one model, so later turns are retried but never moved.
        self._names = client._candidates() if client._fail_over else [client.model]
        self._index = 0
        self._started = False
        self.model = self._names[0]
        self._owner = client  # keeps the SDK client alive: when it is freed the SDK closes its connection mid-run
        self._chat = client._client.chats.create(model=self.model, config=config)

    def send(self, message: Union[str, List[ToolResult]]) -> TurnResult:
        types = self._types
        payload: Any = message if isinstance(message, str) else [types.Part.from_function_response(name=r.name, response=r.payload) for r in message]
        attempts, is_transient, backoff = self._retry
        attempt = 0
        while True:
            try:
                resp = self._chat.send_message(payload)
                break
            except Exception as e:
                if not self._started and self._index + 1 < len(self._names) and self._switchable(e):
                    self._index += 1
                    self.model = self._names[self._index]
                    self._chat = self._owner._client.chats.create(model=self.model, config=self._config)
                    continue  # a fresh conversation on the next model; the failed model does not use up a retry
                attempt += 1
                if is_transient(e) and attempt < attempts:
                    time.sleep(backoff(e, attempt - 1))
                    continue
                raise
        self._started = True
        parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts else []
        text = "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))
        calls = [ToolCall(p.function_call.name, dict(p.function_call.args or {})) for p in parts if getattr(p, "function_call", None)]
        return TurnResult(text=text.strip(), calls=calls)
