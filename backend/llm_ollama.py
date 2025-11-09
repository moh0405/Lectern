from typing import Optional, Dict, Any
import json


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3", temperature: float = 0.2):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def is_available(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, model: Optional[str] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
        mdl = model or self.model
        temp = float(temperature if temperature is not None else self.temperature)
        # Try langchain_ollama first
        try:
            from langchain_ollama import ChatOllama
            chat = ChatOllama(model=mdl, temperature=temp, base_url=self.base_url)
            out = chat.invoke(prompt)
            text = getattr(out, "content", str(out))
            return {"ok": True, "model": mdl, "answer": text}
        except Exception:
            pass
        # Fallback to HTTP direct API
        try:
            import requests
            payload = {"model": mdl, "prompt": prompt, "stream": False, "options": {"temperature": temp}}
            r = requests.post(f"{self.base_url}/api/generate", data=json.dumps(payload), timeout=30)
            if r.status_code == 200:
                data = r.json()
                return {"ok": True, "model": mdl, "answer": data.get("response", "")}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}