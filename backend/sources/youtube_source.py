from __future__ import annotations

import re
from typing import Dict, Any, List, Optional
import json

from .base_source import BaseSource

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

try:
    import requests
except Exception:
    requests = None


def _parse_video_id(url: str) -> Optional[str]:
    # Supports https://www.youtube.com/watch?v=ID and https://youtu.be/ID
    m = re.search(r"v=([A-Za-z0-9_\-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_\-]{6,})", url)
    if m:
        return m.group(1)
    return None


class YouTubeSource(BaseSource):
    def __init__(self) -> None:
        self._meta: Dict[str, Any] = {}

    def validate(self, input_value: str) -> bool:
        return bool(_parse_video_id(input_value))

    def _fetch_oembed(self, url: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if requests is None:
            return data
        try:
            resp = requests.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
        except Exception:
            pass
        return data

    def _fetch_duration(self, url: str) -> Optional[int]:
        if requests is None:
            return None
        try:
            r = requests.get(url, timeout=10)
            if not r.ok:
                return None
            txt = r.text
            m = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', txt)
            if m:
                return int(m.group(1))
            m2 = re.search(r'<meta itemprop="duration" content="PT(\d+)M(\d+)S">', txt)
            if m2:
                mins = int(m2.group(1))
                secs = int(m2.group(2))
                return mins * 60 + secs
        except Exception:
            return None
        return None

    def extract(self, input_value: str) -> List[Dict[str, Any]]:
        if YouTubeTranscriptApi is None:
            raise RuntimeError("youtube-transcript-api not installed. Add it to requirements.")
        vid = _parse_video_id(input_value)
        if not vid:
            raise ValueError("Invalid YouTube URL")

        # Transcript segments with timestamps
        try:
            segments = YouTubeTranscriptApi.get_transcript(vid)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch transcript: {e}")

        meta = self._fetch_oembed(input_value)
        title = meta.get("title") or f"YouTube Video {vid}"
        thumb = meta.get("thumbnail_url") or f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        duration = self._fetch_duration(input_value)
        self._meta = {
            "source_type": "youtube",
            "video_id": vid,
            "title": title,
            "thumbnail_url": thumb,
            "duration_seconds": duration,
            "url": input_value,
        }

        # Merge segments into ~800 char chunks preserving start/end timestamps
        chunks: List[Dict[str, Any]] = []
        buf_text = []
        start_ts: Optional[float] = None
        end_ts: Optional[float] = None
        approx_size = 0
        for seg in segments:
            t = seg.get("text", "")
            s = float(seg.get("start", 0.0))
            d = float(seg.get("duration", 0.0))
            e = s + d
            if start_ts is None:
                start_ts = s
            end_ts = e
            buf_text.append(t)
            approx_size += len(t)
            if approx_size >= 800:
                text = " ".join(buf_text).strip()
                ts_start = int(start_ts or 0)
                citation_url = f"https://www.youtube.com/watch?v={vid}&t={ts_start}s"
                chunk_id = f"yt-{vid}-{ts_start}-{int(end_ts or ts_start)}"
                chunks.append({
                    "text": text,
                    "doc": title,
                    "page": None,
                    "chunk_id": chunk_id,
                    "source_type": "youtube",
                    "url": input_value,
                    "extra": {
                        "start": start_ts,
                        "end": end_ts,
                        "citation_url": citation_url,
                        "thumbnail_url": thumb,
                        "duration_seconds": duration,
                    },
                })
                buf_text = []
                approx_size = 0
                start_ts = None
                end_ts = None

        if buf_text:
            text = " ".join(buf_text).strip()
            ts_start = int(start_ts or 0)
            citation_url = f"https://www.youtube.com/watch?v={vid}&t={ts_start}s"
            chunk_id = f"yt-{vid}-{ts_start}-{int(end_ts or ts_start)}"
            chunks.append({
                "text": text,
                "doc": title,
                "page": None,
                "chunk_id": chunk_id,
                "source_type": "youtube",
                "url": input_value,
                "extra": {
                    "start": start_ts,
                    "end": end_ts,
                    "citation_url": citation_url,
                    "thumbnail_url": thumb,
                    "duration_seconds": duration,
                },
            })

        return chunks

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)