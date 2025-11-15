from __future__ import annotations

from typing import Dict, Any, List, Optional
from pathlib import Path
import os

from .base_source import BaseSource

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class AudioSource(BaseSource):
    def __init__(self) -> None:
        self._meta: Dict[str, Any] = {}

    def validate(self, input_value: str) -> bool:
        p = Path(input_value)
        return p.exists() and p.suffix.lower() in {".mp3", ".mp4", ".wav", ".m4a"}

    def _transcribe(self, file_path: str) -> Dict[str, Any]:
        if OpenAI is None:
            raise RuntimeError("openai not installed. Add it to requirements.")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in environment.")
        client = OpenAI(api_key=api_key)
        fp = Path(file_path)
        with fp.open("rb") as f:
            # Request verbose JSON to include segments and timestamps if available
            try:
                resp = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                )
                # Convert pydantic-like to dict
                if hasattr(resp, "model_dump"):
                    return resp.model_dump()
                if hasattr(resp, "to_dict"):
                    return resp.to_dict()
                return dict(resp)
            except Exception:
                # Fallback: plain text response
                f.seek(0)
                resp = client.audio.transcriptions.create(model="whisper-1", file=f)
                return {"text": getattr(resp, "text", "")}

    def extract(self, input_value: str) -> List[Dict[str, Any]]:
        if not self.validate(input_value):
            raise ValueError("Invalid or unsupported audio file.")
        fp = Path(input_value)
        result = self._transcribe(str(fp))

        title = fp.name
        self._meta = {
            "source_type": "audio",
            "file": str(fp),
            "title": title,
        }

        chunks: List[Dict[str, Any]] = []
        # If segments with timestamps exist, chunk by segments
        segments = result.get("segments") or []
        buf: List[str] = []
        start_ts: Optional[float] = None
        end_ts: Optional[float] = None
        approx = 0
        if segments:
            for seg in segments:
                t = seg.get("text", "")
                s = float(seg.get("start", 0.0))
                e = float(seg.get("end", s))
                if start_ts is None:
                    start_ts = s
                end_ts = e
                buf.append(t)
                approx += len(t)
                if approx >= 800:
                    text = " ".join(buf).strip()
                    chunk_id = f"au-{fp.stem}-{int(start_ts)}-{int(end_ts or start_ts)}"
                    chunks.append({
                        "text": text,
                        "doc": title,
                        "page": None,
                        "chunk_id": chunk_id,
                        "source_type": "audio",
                        "url": None,
                        "extra": {"start": start_ts, "end": end_ts},
                    })
                    buf = []
                    approx = 0
                    start_ts = None
                    end_ts = None
            if buf:
                text = " ".join(buf).strip()
                chunk_id = f"au-{fp.stem}-{int(start_ts or 0)}-{int(end_ts or (start_ts or 0))}"
                chunks.append({
                    "text": text,
                    "doc": title,
                    "page": None,
                    "chunk_id": chunk_id,
                    "source_type": "audio",
                    "url": None,
                    "extra": {"start": start_ts, "end": end_ts},
                })
        else:
            # Fallback: single-text chunking
            text = result.get("text", "")
            for i, c in enumerate(self.chunk_text(text)):
                chunks.append({
                    "text": c,
                    "doc": title,
                    "page": None,
                    "chunk_id": f"au-{fp.stem}-{i}",
                    "source_type": "audio",
                    "url": None,
                    "extra": {},
                })

        return chunks

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)