from typing import Optional, Dict, Any, List
import os
import json


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = None, temperature: float = 0.2):
        self.base_url = base_url.rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.temperature = temperature

    def is_available(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return [m.get("name") for m in r.json().get("models", [])]
        except Exception:
            pass
        return []

    def has_model(self, name: Optional[str] = None) -> bool:
        mdl = name or self.model
        return mdl in set(self.list_models())

    def pull_model(self, name: Optional[str] = None) -> bool:
        mdl = name or self.model
        try:
            import requests
            payload = {"name": mdl, "stream": False}
            r = requests.post(f"{self.base_url}/api/pull", data=json.dumps(payload), timeout=300)
            return r.status_code == 200
        except Exception:
            return False

    def ensure_model(self, name: Optional[str] = None) -> bool:
        mdl = name or self.model
        if not self.is_available():
            return False
        if self.has_model(mdl):
            return True
        return self.pull_model(mdl)

    def generate(self, prompt: str, model: Optional[str] = None, temperature: Optional[float] = None, stream: bool = True, timeout: int = 180) -> Dict[str, Any]:
        mdl = model or self.model
        temp = float(temperature if temperature is not None else self.temperature)
        # Ensure model exists (attempt to pull if missing)
        if not self.ensure_model(mdl):
            return {"ok": False, "error": f"Ollama model '{mdl}' not available (pull failed). Please run: ollama pull {mdl}"}

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
            payload = {"model": mdl, "prompt": prompt, "stream": bool(stream), "options": {"temperature": temp}}
            if stream:
                resp_text = []
                with requests.post(f"{self.base_url}/api/generate", data=json.dumps(payload), timeout=timeout, stream=True) as r:
                    if r.status_code != 200:
                        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text}"}
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            chunk = obj.get("response", "")
                            if chunk:
                                resp_text.append(chunk)
                        except Exception:
                            # Ignore malformed lines
                            continue
                return {"ok": True, "model": mdl, "answer": "".join(resp_text)}
            else:
                r = requests.post(f"{self.base_url}/api/generate", data=json.dumps(payload), timeout=timeout)
                if r.status_code == 200:
                    data = r.json()
                    return {"ok": True, "model": mdl, "answer": data.get("response", "")}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}