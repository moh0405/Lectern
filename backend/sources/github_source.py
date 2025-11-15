from __future__ import annotations

import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse

from .base_source import BaseSource

try:
    from git import Repo
except Exception:
    Repo = None

try:
    import requests
except Exception:
    requests = None


def _repo_parts(url: str) -> Optional[tuple[str, str]]:
    try:
        p = urlparse(url)
        if p.netloc != "github.com":
            return None
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None


class GitHubSource(BaseSource):
    def __init__(self, work_dir: str = "data/repos") -> None:
        self.work_dir = Path(work_dir)
        self.repo_dir: Optional[Path] = None
        self._meta: Dict[str, Any] = {}

    def validate(self, input_value: str) -> bool:
        return _repo_parts(input_value) is not None

    def _clone(self, url: str) -> Path:
        if Repo is None:
            raise RuntimeError("gitpython not installed. Add it to requirements.")
        owner, repo = _repo_parts(url) or (None, None)
        if not owner or not repo:
            raise ValueError("Invalid GitHub repo URL")
        target = self.work_dir / f"{owner}__{repo}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and any(target.iterdir()):
            # Already cloned
            self.repo_dir = target
            return target
        Repo.clone_from(url, str(target))
        self.repo_dir = target
        return target

    def _fetch_readme_api(self, owner: str, repo: str) -> Optional[str]:
        if requests is None:
            return None
        try:
            resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", timeout=10)
            if resp.status_code == 200:
                import base64
                content = resp.json().get("content")
                if content:
                    return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return None
        return None

    def _fetch_repo_meta(self, owner: str, repo: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {}
        if requests is None:
            return info
        try:
            resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
            if resp.ok:
                j = resp.json()
                info = {
                    "full_name": j.get("full_name"),
                    "description": j.get("description"),
                    "stars": j.get("stargazers_count"),
                    "language": j.get("language"),
                    "license": (j.get("license") or {}).get("spdx_id"),
                }
        except Exception:
            pass
        return info

    def _iter_files(self, root: Path) -> List[Path]:
        allow_ext = {".md", ".rst", ".txt", ".py"}
        files: List[Path] = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in allow_ext:
                if any(part.startswith(".") for part in p.parts):
                    continue
                files.append(p)
        return files

    def _read_text(self, fp: Path) -> str:
        try:
            return fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _extract_from_py(self, content: str) -> str:
        # Simple heuristic: collect leading comments and docstrings
        lines = content.splitlines()
        comments = []
        in_doc = False
        for ln in lines[:5000]:  # limit
            s = ln.strip()
            if s.startswith("#"):
                comments.append(s.lstrip("# "))
            if '"""' in s or "'''" in s:
                in_doc = not in_doc
                comments.append(s)
            elif in_doc:
                comments.append(s)
        return "\n".join(comments)

    def extract(self, input_value: str) -> List[Dict[str, Any]]:
        owner, repo = _repo_parts(input_value) or (None, None)
        if not owner or not repo:
            raise ValueError("Invalid GitHub repo URL")
        # Prefer fast README via API; fall back to clone for broader docs
        readme_text = self._fetch_readme_api(owner, repo)
        chunks: List[Dict[str, Any]] = []
        tree: List[str] = []
        if readme_text:
            label = f"{repo}/README.md"
            for i, c in enumerate(self.chunk_text(readme_text)):
                chunks.append({
                    "text": c,
                    "doc": label,
                    "page": None,
                    "chunk_id": f"gh-{repo}-README-{i}",
                    "source_type": "github",
                    "url": input_value,
                    "extra": {
                        "file_path": "README.md",
                    },
                })
            root = None
        else:
            root = self._clone(input_value)
        meta = self._fetch_repo_meta(owner, repo)
        self._meta = {
            "source_type": "github",
            "url": input_value,
            "owner": owner,
            "repo": repo,
            **meta,
        }

        if root is not None:
            files = self._iter_files(root)
            for p in files:
                rel = p.relative_to(root)
                tree.append(str(rel))
                text = self._read_text(p)
                if p.suffix == ".py":
                    text = self._extract_from_py(text)
                label = f"{repo}/{rel}"
                for i, c in enumerate(self.chunk_text(text)):
                    chunks.append({
                        "text": c,
                        "doc": label,
                        "page": None,
                        "chunk_id": f"gh-{repo}-{rel}-{i}",
                        "source_type": "github",
                        "url": input_value,
                        "extra": {
                            "file_path": str(rel),
                        },
                    })

        self._meta["tree"] = tree
        return chunks

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)