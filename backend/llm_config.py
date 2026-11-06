"""Gemini client on top of the current Google Gen AI SDK (`google-genai`).

The public surface is small and unchanged for callers:

    client = GeminiClient(model=None, temperature=0.2)
    client.generate(prompt)            -> {"ok": True, "model": ..., "answer": ...} | {"ok": False, "error": ...}
    client.generate(prompt, json_mode=True)   # ask for a JSON response
    for piece in client.stream(prompt): ...   # text deltas as they are produced
    client.list_supported_models()

Configuration (environment or `.env`):
    GEMINI_API_KEY, GEMINI_MODEL (default gemini-3.6-flash), GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT_S (per attempt, default 30), GEMINI_FALLBACK_MODELS (models tried in order when the chosen one is
    overloaded or out of quota; default gemini-flash-lite-latest,gemini-2.5-flash; "none" disables)
"""

from __future__ import annotations

import logging
import os
import re
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

# gemini-3.8-flash was the default until it was found to answer "503 high demand" or time out most of the time
# (a live Lambda sat on it for weeks while gemini-3.6-flash and the lite model answered in seconds).
DEFAULT_MODEL = "gemini-3.6-flash"
# Used to pick a substitute when the requested model does not exist for the key.
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-pro-latest",
]
# Used when the chosen model is overloaded, rate-limited or timing out: tried in this order, immediately. Every model has
# its own quota, so this also lets a free key serve more questions. Override with GEMINI_FALLBACK_MODELS ("none" turns it off).
DEFAULT_FALLBACKS = ["gemini-flash-lite-latest", "gemini-2.5-flash"]
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


# Gemini says how long to wait when it rate-limits a call ("Please retry in 14.6s", or retryDelay: '14s').
_RETRY_HINTS = (re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.I), re.compile(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s", re.I))
MAX_RETRY_WAIT_S = 30.0  # a longer wait (a daily quota) will not clear inside one request, so it is not worth retrying


def retry_delay_seconds(exc: Any) -> Optional[float]:
    """How long the provider asked us to wait, if its error says so."""
    text = str(exc)
    for rx in _RETRY_HINTS:
        m = rx.search(text)
        if m:
            return float(m.group(1))
    return None


def _backoff_seconds(exc: Exception, attempt: int) -> float:
    """Pause before retrying: the provider's own hint when it gave one (a per-minute limit clears in seconds), else a short step."""
    delay = retry_delay_seconds(exc)
    return min(delay + 0.5, MAX_RETRY_WAIT_S) if delay is not None else 0.8 * (attempt + 1)


def _is_transient(exc: Exception) -> bool:
    delay = retry_delay_seconds(exc)
    if delay is not None and delay > MAX_RETRY_WAIT_S:
        return False
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    text = str(exc).lower()
    return any(m in text for m in _TRANSIENT_MARKERS)


def fallback_models() -> List[str]:
    raw = os.getenv("GEMINI_FALLBACK_MODELS")
    if raw is None:
        return list(DEFAULT_FALLBACKS)
    if raw.strip().lower() in ("", "none", "off", "false", "0"):
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def _is_quota(exc: Exception) -> bool:
    text = str(exc).lower()
    return getattr(exc, "code", None) == 429 or "resource_exhausted" in text or "quota" in text


def _should_fail_over(exc: Exception) -> bool:
    """Errors that mean "this model, right now": overloaded, timing out, or out of quota. Another model may well answer.
    Not for bad requests, bad keys or blocked content: those would fail the same way on every model."""
    return _is_transient(exc) or _is_quota(exc)


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
        # A model the caller asked for by name is respected: no silent swapping. The server's default may fail over.
        self._fail_over = model is None
        self._fallbacks = fallback_models() if self._fail_over else []
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

    def start_tool_chat(self, system: str, tools: List[Any], temperature: Optional[float] = None) -> Any:
        """A conversation in which the model can ask for tools to be run (see backend/tool_chat.py)."""
        from .tool_chat import GeminiToolChat

        return GeminiToolChat(self, system, tools, temperature)

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
        for m in [DEFAULT_MODEL, *self._fallbacks]:
            if m not in names:
                names.append(m)
        return names

    def _next_model_exists(self, names: List[str], i: int) -> bool:
        return self._fail_over and i < len(names) - 1

    def generate(self, prompt: str, temperature: Optional[float] = None, json_mode: bool = False) -> Dict[str, Any]:
        """One-shot generation. Retries transient errors, then tries the default model once."""
        config = self._config(temperature, json_mode)
        last_err: Optional[str] = None
        names = self._candidates()
        for i, name in enumerate(names):
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    resp = self._client.models.generate_content(model=name, contents=prompt, config=config)
                except Exception as e:
                    last_err = str(e)
                    if _is_model_missing(e):
                        break  # try the next candidate model
                    if self._next_model_exists(names, i) and _should_fail_over(e):
                        logger.warning("Model '%s' failed (%s); trying '%s'", name, last_err[:90], names[i + 1])
                        break  # overloaded or out of quota: do not wait on it, ask the next model
                    if _is_transient(e) and attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(_backoff_seconds(e, attempt))
                        continue
                    return {"ok": False, "error": last_err}
                text = self._text_of(resp)
                if text:
                    self.model = name  # report the model that really answered
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
        names = self._candidates()
        for i, name in enumerate(names):
            for attempt in range(RETRY_ATTEMPTS):
                started = False
                try:
                    for chunk in self._client.models.generate_content_stream(model=name, contents=prompt, config=config):
                        piece = self._text_of(chunk)
                        if piece:
                            if not started:
                                self.model = name  # report the model that really answered
                            started = True
                            yield piece
                    return
                except Exception as e:
                    last_exc = e
                    if started:
                        raise
                    if _is_model_missing(e):
                        break
                    if self._next_model_exists(names, i) and _should_fail_over(e):
                        logger.warning("Model '%s' failed (%s); trying '%s'", name, str(e)[:90], names[i + 1])
                        break
                    if _is_transient(e) and attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(_backoff_seconds(e, attempt))
                        continue
                    raise
        if last_exc is not None:
            raise last_exc
