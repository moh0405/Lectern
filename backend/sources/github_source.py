from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse

from ..safe_fetch import safe_get
from .base_source import BaseSource

try:
    import requests
except Exception:
    requests = None


CLONE_TIMEOUT_S = 60
MAX_FILES = 2000
MAX_FILE_BYTES = 1024 * 1024
_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$")


def _repo_parts(url: str) -> Optional[tuple[str, str]]:
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"} or p.netloc != "github.com":
            return None
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].removesuffix(".git")
            if _NAME.match(owner) and _NAME.match(repo):
                return owner, repo
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
        if shutil.which("git") is None:
            raise RuntimeError("git is not installed.")
        owner, repo = _repo_parts(url) or (None, None)
        if not owner or not repo:
            raise ValueError("Invalid GitHub repo URL")
        target = self.work_dir / f"{owner}__{repo}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and any(target.iterdir()):
            # Already cloned
            self.repo_dir = target
            return target
        # Built from the checked owner and repo, shallow, https only, no redirects, no prompts, and bounded in time.
        command = [
            "git", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always", "-c", "http.followRedirects=false",
            "-c", "core.symlinks=false", "clone", "--depth=1", "--single-branch", "--no-tags", "--",
            f"https://github.com/{owner}/{repo}.git", str(target),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=CLONE_TIMEOUT_S, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except (subprocess.SubprocessError, OSError) as e:
            shutil.rmtree(target, ignore_errors=True)  # a partial clone must not look "already cloned" next time
            raise RuntimeError(f"Could not clone {owner}/{repo}.") from e
        self.repo_dir = target
        return target

    def _fetch_readme_api(self, owner: str, repo: str) -> Optional[str]:
        if requests is None:
            return None
        try:
            resp = safe_get(f"https://api.github.com/repos/{owner}/{repo}/readme", max_seconds=10)
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
            resp = safe_get(f"https://api.github.com/repos/{owner}/{repo}", max_seconds=10)
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
        base = root.resolve()
        for p in root.rglob("*"):
            # A repository can hold a symlink to a server file (/proc/self/environ, say): never follow one.
            if p.is_symlink() or not p.is_file() or p.suffix.lower() not in allow_ext:
                continue
            rel = p.relative_to(root)
            if any(part.startswith(".") for part in rel.parts) or not p.resolve().is_relative_to(base):
                continue
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
            files.append(p)
            if len(files) >= MAX_FILES:
                break
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