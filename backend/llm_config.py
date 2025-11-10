import os
from typing import Optional, Dict, Any

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class GeminiClient:
    """
    Lightweight Gemini API client for text generation.

    - Reads API key from environment `GEMINI_API_KEY`
    - Default model from `GEMINI_MODEL` (fallback to a cost-efficient text model)
    - Temperature from `GEMINI_TEMPERATURE`
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.2):
        if genai is None:
            raise RuntimeError("google-generativeai is not installed. Please run: pip install google-generativeai")
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to your environment or .env file.")
        genai.configure(api_key=key)
        requested = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
        self.model = self._resolve_model(requested)
        try:
            self.temperature = float(os.getenv("GEMINI_TEMPERATURE", str(temperature)))
        except Exception:
            self.temperature = temperature

    def _resolve_model(self, requested: str) -> str:
        """Resolve a compatible model for `generateContent`.

        - If the requested model exists and supports generateContent, use it
        - Otherwise, fall back to common aliases like `gemini-1.5-flash-latest`
        - As a last resort, pick the first model that supports generateContent
        """
        try:
            models = list(genai.list_models())
            by_base: Dict[str, Any] = {}
            for m in models:
                name = getattr(m, "name", "")
                base = name.split("/")[-1]
                by_base[base] = m
            def supports_generate(mobj: Any) -> bool:
                methods = getattr(mobj, "supported_generation_methods", [])
                return "generateContent" in methods or "generate_content" in methods

            # Use requested if available and supported
            mobj = by_base.get(requested)
            if mobj and supports_generate(mobj):
                return requested

            # Prefer flash latest, then flash, then pro latest
            for candidate in [
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash",
                "gemini-1.5-pro-latest",
                "gemini-1.5-pro",
            ]:
                mobj = by_base.get(candidate)
                if mobj and supports_generate(mobj):
                    return candidate

            # Fallback: first model that supports generate
            for base, mobj in by_base.items():
                if supports_generate(mobj):
                    return base
        except Exception:
            # If listing fails, just return the requested; SDK will raise a clear error
            pass
        return requested

    def list_supported_models(self) -> list[str]:
        """Return base model names that support `generateContent` for this key."""
        results: list[str] = []
        try:
            models = list(genai.list_models())
            for m in models:
                name = getattr(m, "name", "")
                base = name.split("/")[-1]
                methods = getattr(m, "supported_generation_methods", [])
                if "generateContent" in methods or "generate_content" in methods:
                    results.append(base)
        except Exception:
            pass
        # Prefer stable ordering: flash latest first if present
        def sort_key(x: str) -> tuple:
            pri = 0
            if "flash" in x:
                pri = -2
            if x.endswith("latest"):
                pri = -3
            return (pri, x)
        return sorted(results, key=sort_key)

    def generate(self, prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        temp = self.temperature if temperature is None else float(temperature)
        # Try primary then a sequence of common, compatible fallbacks.
        candidates = [
            self.model,
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-001",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro-001",
            "gemini-1.0-pro",
        ]
        last_err = None
        for name in candidates:
            try:
                m = genai.GenerativeModel(name)
                resp = m.generate_content(prompt, generation_config={"temperature": temp})
                text = getattr(resp, "text", "")
                if text:
                    return {"ok": True, "model": name, "answer": text}
                # Some SDK responses put text in parts; extract defensively
                try:
                    parts = getattr(resp, "candidates", [])[0].content.parts
                    if parts and getattr(parts[0], "text", ""):
                        return {"ok": True, "model": name, "answer": parts[0].text}
                except Exception:
                    pass
            except Exception as e:
                last_err = str(e)
                # Continue to next candidate on 404/unsupported errors
                if not any(s in last_err for s in ["not found", "supported for generateContent", "404", "No model"]):
                    # If it's a non-compat error (e.g., auth), break early
                    break
        return {"ok": False, "error": last_err or "Unknown generation error"}