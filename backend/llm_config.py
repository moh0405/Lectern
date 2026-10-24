"""Gemini client on top of the current Google Gen AI SDK (`google-genai`).

The public surface is small and unchanged for callers:

    client = GeminiClient(model=None, temperature=0.2)
    client.generate(prompt)            -> {"ok": True, "model": ..., "answer": ...} | {"ok": False, "error": ...}
    client.generate(prompt, json_mode=True)   # ask for a JSON response
    for piece in client.stream(prompt): ...   # text deltas as they are produced
    client.list_supported_models()

Configuration (environment or `.env`):
    GEMINI_API_KEY, GEMINI_MODEL (default gemini-3.8-flash), GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT_S (per attempt, default 30)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # SDK not installed
    genai = None
    genai_types = None

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("ai-study-mentor.llm")

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-pro-latest",
]
RETRY_ATTEMPTS = 3
# Per-attempt limit. Without one a stalled model call outlives the host (Lambda stops at 120 s) and the user
# sees a stream that just ends. 3 attempts of 30 s fit inside 120 s and end in a normal `llm_error` event.
DEFAULT_TIMEOUT_S = 30.0
_TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}
_TRANSIENT_MARKERS = ("unavailable", "timeout", "timed out", "rate limit", "resource exhausted", "overloaded")

# (api key suffix, requested model) -> resolved model, so listing models is not repeated per request
_resolved_models: Dict[tuple, str] = {}


def _timeout_s() -> float:
    try:
        return max(1.0, float(os.getenv("GEMINI_TIMEOUT_S", str(DEFAULT_TIMEOUT_S))))
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _is_transient(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    text = str(exc).lower()
    return any(m in text for m in _TRANSIENT_MARKERS)


def _is_model_missing(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    text = str(exc).lower()
    return code == 404 or "not found" in text or "not supported for generatecontent" in text


def _base_name(name: str) -> str:
    return (name or "").split("/")[-1]


class GeminiClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        client: Any = None,
    ):
        """`client` lets tests (or callers) inject a pre-built SDK client."""
        if client is None:
            if genai is None:
                raise RuntimeError("google-genai is not installed. Please run: pip install google-genai")
            key = api_key or os.getenv("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY is not set. Add it to your environment or .env file.")
            client = genai.Client(api_key=key, http_options=genai_types.HttpOptions(timeout=int(_timeout_s() * 1000)))
            self._key_id = key[-6:]
        else:
            self._key_id = "injected"
        self._client = client
        requested = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.model = self._resolve_model(requested)
        try:
            self.temperature = float(os.getenv("GEMINI_TEMPERATURE", str(temperature)))
        except Exception:
            self.temperature = temperature

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------
    def _supported_models(self) -> List[str]:
        """Base names of models that can generate text for this key."""
        out: List[str] = []
        for m in self._client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions:
                out.append(_base_name(getattr(m, "name", "")))
        return out

    def _resolve_model(self, requested: str) -> str:
        """Use `requested` if it can generate content; otherwise the best available alternative."""
        cache_key = (self._key_id, requested)
        if cache_key in _resolved_models:
            return _resolved_models[cache_key]
        try:
            supported = self._supported_models()
        except Exception as e:
            logger.warning("Could not list Gemini models (%s); using '%s' as is", e, requested)
            return requested
        resolved = requested
        if requested not in supported:
            resolved = next((c for c in FALLBACK_MODELS if c in supported), supported[0] if supported else requested)
            if resolved != requested:
                logger.warning("Model '%s' unavailable for this key; using '%s'", requested, resolved)
        _resolved_models[cache_key] = resolved
        return resolved

    def list_supported_models(self) -> List[str]:
        """Model names that support text generation, newest Flash first."""
        try:
            names = self._supported_models()
        except Exception:
            return []

        def sort_key(x: str) -> tuple:
            pri = 0
            if "flash" in x:
                pri = -2
            if x.endswith("latest"):
                pri = -3
            return (pri, x)

        return sorted(names, key=sort_key)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _config(self, temperature: Optional[float], json_mode: bool) -> Any:
        temp = self.temperature if temperature is None else float(temperature)
        kwargs: Dict[str, Any] = {"temperature": temp}
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        return genai_types.GenerateContentConfig(**kwargs) if genai_types is not None else kwargs

    @staticmethod
    def _text_of(resp: Any) -> str:
        text = getattr(resp, "text", None)
        if text:
            return text
        try:  # some responses only carry parts
            return "".join(getattr(p, "text", "") or "" for p in resp.candidates[0].content.parts)
        except Exception:
            return ""

    def _candidates(self) -> List[str]:
        names = [self.model]
        if DEFAULT_MODEL not in names:
            names.append(DEFAULT_MODEL)
        return names

    def generate(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Dict[str, Any]:
        """One-shot generation. Retries transient errors, then tries the default model once."""
        config = self._config(temperature, json_mode)
        last_err: Optional[str] = None
        for name in self._candidates():
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    resp = self._client.models.generate_content(model=name, contents=prompt, config=config)
                except Exception as e:
                    last_err = str(e)
                    if _is_transient(e) and attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    if _is_model_missing(e):
                        break  # try the next candidate model
                    return {"ok": False, "error": last_err}
                text = self._text_of(resp)
                if text:
                    return {"ok": True, "model": name, "answer": text}
                last_err = "Model returned an empty response (it may have been blocked by a safety filter)"
                break
        return {"ok": False, "error": last_err or "Unknown generation error"}

    def stream(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Iterator[str]:
        """Yield text deltas as the model produces them.

        Retries and model fallback only happen before the first delta; once text has
        been yielded, an error propagates to the caller.
        """
        config = self._config(temperature, json_mode)
        last_exc: Optional[Exception] = None
        for name in self._candidates():
            for attempt in range(RETRY_ATTEMPTS):
                started = False
                try:
                    for chunk in self._client.models.generate_content_stream(model=name, contents=prompt, config=config):
                        piece = self._text_of(chunk)
                        if piece:
                            started = True
                            yield piece
                    return
                except Exception as e:
                    last_exc = e
                    if started:
                        raise
                    if _is_transient(e) and attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    if _is_model_missing(e):
                        break
                    raise
        if last_exc is not None:
            raise last_exc
