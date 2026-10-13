"""One interface for every language-model provider.

Callers never name a provider. They ask `create_llm(model=..., temperature=...)` and get an object with
the methods below; `LLM_PROVIDER` decides which backend answers:

    gemini   (default)   Google Gemini through `google-genai`      GEMINI_API_KEY, GEMINI_MODEL
    openai               OpenAI, or any OpenAI-compatible server   OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
                         (Ollama, vLLM, LM Studio, OpenRouter ... set OPENAI_BASE_URL)

The interface is exactly what the rest of the code already used on `GeminiClient`:

    client.generate(prompt, temperature=None, json_mode=False) -> {"ok": True, "model", "answer"} | {"ok": False, "error"}
    client.stream(prompt, temperature=None, json_mode=False)   -> iterator of text pieces
    client.list_supported_models()                             -> list of model names
    client.model                                               -> the model in use

Adding a provider means writing a class with those four members and registering it in `PROVIDERS`.
Providers are tested with injected fake SDK clients, so no network or key is needed.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, runtime_checkable

from .llm_config import RETRY_ATTEMPTS, GeminiClient, _is_transient

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


@runtime_checkable
class LLMProvider(Protocol):
    model: str

    def generate(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Dict[str, Any]: ...

    def stream(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Iterator[str]: ...

    def list_supported_models(self) -> List[str]: ...


class OpenAICompatClient:
    """Chat-completions client for OpenAI and OpenAI-compatible servers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        base_url: Optional[str] = None,
        client: Any = None,
    ) -> None:
        """`client` lets tests inject a fake SDK client."""
        if client is None:
            try:
                from openai import OpenAI
            except Exception as e:  # package missing
                raise RuntimeError("openai is not installed. Please run: pip install openai") from e
            base_url = base_url or os.getenv("OPENAI_BASE_URL") or None
            key = api_key or os.getenv("OPENAI_API_KEY") or ("not-needed" if base_url else None)
            if not key:
                raise RuntimeError("OPENAI_API_KEY is not set. Add it to your environment or .env file.")
            client = OpenAI(api_key=key, base_url=base_url)
        self._client = client
        self.model = model or os.getenv("OPENAI_MODEL", OPENAI_DEFAULT_MODEL)
        self.temperature = temperature

    def _kwargs(self, prompt: str, temperature: Optional[float], json_mode: bool) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature if temperature is None else float(temperature),
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    def generate(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Dict[str, Any]:
        last_err: Optional[str] = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                resp = self._client.chat.completions.create(**self._kwargs(prompt, temperature, json_mode))
            except Exception as e:
                last_err = str(e)
                if _is_transient(e) and attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                return {"ok": False, "error": last_err}
            text = ""
            try:
                text = resp.choices[0].message.content or ""
            except Exception:
                pass
            if text:
                return {"ok": True, "model": self.model, "answer": text}
            return {"ok": False, "error": "Model returned an empty response (it may have been filtered)"}
        return {"ok": False, "error": last_err or "Unknown generation error"}

    def stream(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Iterator[str]:
        """Retries only before the first piece; after that, errors propagate."""
        for attempt in range(RETRY_ATTEMPTS):
            started = False
            try:
                for chunk in self._client.chat.completions.create(**self._kwargs(prompt, temperature, json_mode), stream=True):
                    try:
                        piece = chunk.choices[0].delta.content
                    except Exception:
                        piece = None
                    if piece:
                        started = True
                        yield piece
                return
            except Exception as e:
                if started or not _is_transient(e) or attempt == RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(0.8 * (attempt + 1))

    def list_supported_models(self) -> List[str]:
        try:
            return sorted(m.id for m in self._client.models.list())
        except Exception:
            return []


PROVIDERS: Dict[str, Callable[..., LLMProvider]] = {
    "gemini": GeminiClient,
    "openai": OpenAICompatClient,
}


def provider_name() -> str:
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def create_llm(model: Optional[str] = None, temperature: float = 0.2, **kwargs: Any) -> LLMProvider:
    """The configured provider's client. Raises RuntimeError (like GeminiClient always did) when it cannot be used."""
    name = provider_name()
    factory = PROVIDERS.get(name)
    if factory is None:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{name}'. Choose one of: {', '.join(sorted(PROVIDERS))}")
    return factory(model=model, temperature=temperature, **kwargs)
