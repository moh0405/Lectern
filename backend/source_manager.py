from __future__ import annotations

from typing import List, Dict, Any

from .sources.youtube_source import YouTubeSource
from .sources.web_source import WebSource
from .sources.github_source import GitHubSource
from .sources.audio_source import AudioSource


def detect_source_type(input_str: str) -> str:
    s = input_str.strip().lower()
    if s.startswith("http"):
        if "youtube.com" in s or "youtu.be" in s:
            return "youtube"
        if "github.com" in s:
            return "github"
        return "web"
    # file path or file-like
    ext = s.split(".")[-1]
    if ext in {"mp3", "mp4", "wav", "m4a"}:
        return "audio"
    return "unknown"


def get_handler(source_type: str):
    if source_type == "youtube":
        return YouTubeSource()
    if source_type == "web":
        return WebSource()
    if source_type == "github":
        return GitHubSource()
    if source_type == "audio":
        return AudioSource()
    raise ValueError(f"Unsupported source type: {source_type}")


def process_url(url: str) -> List[Dict[str, Any]]:
    stype = detect_source_type(url)
    handler = get_handler(stype)
    return handler.extract(url)


def process_file(file_path: str) -> List[Dict[str, Any]]:
    stype = detect_source_type(file_path)
    handler = get_handler(stype)
    # AudioSource expects a path string
    return handler.extract(file_path)