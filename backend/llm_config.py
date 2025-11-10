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
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        try:
            self.temperature = float(os.getenv("GEMINI_TEMPERATURE", str(temperature)))
        except Exception:
            self.temperature = temperature

    def generate(self, prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        temp = self.temperature if temperature is None else float(temperature)
        try:
            m = genai.GenerativeModel(self.model)
            resp = m.generate_content(prompt, generation_config={"temperature": temp})
            text = getattr(resp, "text", "")
            return {"ok": True, "model": self.model, "answer": text}
        except Exception as e:
            return {"ok": False, "error": str(e)}