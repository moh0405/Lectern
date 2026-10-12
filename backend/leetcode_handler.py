from __future__ import annotations

import re
import json
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

try:
    import pandas as pd  # optional but recommended
except Exception:
    pd = None

try:
    from huggingface_hub import hf_hub_download  # optional; used for dataset fetch
except Exception:
    hf_hub_download = None


from .document_processor import embed_texts
from .llm_config import GeminiClient


def _import_kaggle():
    """Lazily import the optional `kaggle` package.

    Depending on the version, importing it or calling `api.authenticate()`
    calls `sys.exit()` when credentials (~/.kaggle/kaggle.json) are missing,
    so it must not run at module import time, and SystemExit has to be
    caught explicitly.
    """
    try:
        import kaggle  # type: ignore
        return kaggle
    except (Exception, SystemExit):
        return None


@dataclass
class LCProblem:
    pid: str
    title: str
    difficulty: str
    topics: List[str]
    description: str
    url: Optional[str] = None
    acceptance: Optional[float] = None
    likes: Optional[int] = None
    dislikes: Optional[int] = None
    source: Optional[str] = None  # which dataset contributed


class LeetCodeHandler:
    """Unified handler for loading and searching LeetCode problems from multiple datasets.

    Supported datasets (best-effort downloads with graceful fallbacks):
      1. HuggingFace: kaysss/leetcode-problem-set
      2. Kaggle: gzipchrist/leetcode-problem-dataset
      3. Kaggle: mohitkumar282/leetcode-questions-dataset

    If remote downloads fail, looks for local files under `data/leetcode/` and
    a normalized dump `data/leetcode/normalized_problems.jsonl`.
    """

    def __init__(self, cache_dir: str = "data/leetcode", model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._problems: List[LCProblem] = []
        self._id_index: Dict[str, int] = {}
        self._embeddings: Optional[np.ndarray] = None
        self._loaded = False

    # ----------------------
    # Public API
    # ----------------------
    def is_loaded(self) -> bool:
        return self._loaded and bool(self._problems)

    def load_all(self, force: bool = False, generate_embeddings: bool = True, refresh: bool = False) -> Tuple[int, str]:
        """Load problems; returns (count, status).

        Reads the cached normalized file when present (fast, no network, no writes).
        `refresh=True` also re-downloads and re-parses the raw datasets; `force=True` reloads
        even if already loaded.
        """
        if self._loaded and not force:
            return (len(self._problems), "already loaded")

        problems: List[LCProblem] = []
        status_parts: List[str] = []

        # 1) Try normalized local file first (fast path)
        norm_path = self.cache_dir / "normalized_problems.jsonl"
        if norm_path.exists():
            try:
                problems.extend(self._read_normalized_jsonl(norm_path))
                status_parts.append(f"loaded {len(problems)} from normalized_problems.jsonl")
            except Exception as e:
                status_parts.append(f"failed to read normalized jsonl: {e}")

        # Steps 2-4 touch the network and rewrite the normalized file, so they only run when there
        # is nothing cached yet or the caller asks for a refresh (scripts/prepare_leetcode_data.py).
        if refresh or not problems:
            # 2) HuggingFace dataset (best-effort)
            if not problems:  # prefer normalized if present
                try:
                    hf_count = self._try_load_huggingface()
                    status_parts.append(f"huggingface: {hf_count}")
                    problems.extend(self._read_normalized_jsonl(norm_path)) if norm_path.exists() else None
                except Exception as e:
                    status_parts.append(f"huggingface failed: {e}")

            # 3) Kaggle datasets (best-effort)
            try:
                k1 = self._try_load_kaggle_competition("gzipchrist/leetcode-problem-dataset")
                k2 = self._try_load_kaggle_competition("mohitkumar282/leetcode-questions-dataset")
                status_parts.append(f"kaggle gzipchrist: {k1}, mohitkumar282: {k2}")
            except Exception as e:
                status_parts.append(f"kaggle failed: {e}")

            # 4) Local CSV/JSON fallbacks in data/leetcode
            try:
                local_added = self._try_load_local_files()
                if local_added:
                    status_parts.append(f"local files added: {local_added}")
            except Exception as e:
                status_parts.append(f"local read failed: {e}")

        # If still no normalized file, build from raw pieces and write it
        if not norm_path.exists():
            if problems:
                self._write_normalized_jsonl(norm_path, problems)

        # Read normalized one last time to ensure consistency
        if norm_path.exists():
            problems = self._read_normalized_jsonl(norm_path)

        # Deduplicate by title (robust to missing IDs across sources)
        uniq: Dict[str, LCProblem] = {}
        for p in problems:
            key = (p.title or p.pid).strip().lower()
            if key not in uniq:
                uniq[key] = p
            else:
                # Merge fields if new data has more metadata
                prev = uniq[key]
                uniq[key] = self._merge_problem(prev, p)

        self._problems = list(uniq.values())
        self._id_index = {p.pid or f"title:{p.title}": i for i, p in enumerate(self._problems)}
        self._loaded = True

        # Best-effort embeddings (optional)
        if generate_embeddings:
            try:
                self._ensure_embeddings()
                status_parts.append("embeddings ready")
            except Exception as e:
                status_parts.append(f"embeddings unavailable: {e}")
        elif self._load_cached_embeddings():
            status_parts.append("cached embeddings loaded")

        return (len(self._problems), "; ".join(status_parts) or "ok")

    def search(
        self,
        query: str,
        top_k: int = 10,
        difficulty: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search problems by semantic similarity (fallback to keyword) and filters."""
        if not self._problems:
            return []
        idxs = list(range(len(self._problems)))

        # Apply filters
        if difficulty:
            diffs = {d.lower() for d in difficulty}
            idxs = [i for i in idxs if (self._problems[i].difficulty or "").lower() in diffs]
        if topics:
            req = {t.strip().lower() for t in topics}
            idxs = [i for i in idxs if req.intersection({t.lower() for t in (self._problems[i].topics or [])})]

        q = (query or "").strip()
        if not q:
            # Browse: no query means dataset order (filters still apply), nothing to score.
            scores: List[float] = [0.0] * len(idxs)
            order = list(range(len(idxs)))
        else:
            semantic = False
            scores = []
            if self._embeddings is not None:
                try:
                    qv = embed_texts([q], model_name=self.model_name)[0]
                    scores = (self._embeddings[idxs] @ qv).tolist()
                    semantic = True
                except Exception:
                    semantic = False
            if not semantic:
                scores = self._keyword_scores(q, [(self._problems[i].title, self._problems[i].description) for i in idxs])
            order = np.argsort(-np.asarray(scores), kind="stable").tolist()
            if not semantic:
                order = [j for j in order if scores[j] > 0]  # no term in common: not a match
        results: List[Dict[str, Any]] = []
        for j in order[:top_k]:
            i = idxs[j]
            p = self._problems[i]
            results.append({
                "pid": p.pid,
                "title": p.title,
                "difficulty": p.difficulty,
                "topics": p.topics,
                "acceptance": p.acceptance,
                "likes": p.likes,
                "dislikes": p.dislikes,
                "url": p.url,
                "score": float(scores[j] if j < len(scores) else 0.0),
                "source": p.source,
                "index": i,
            })
        return results

    def explain_problem(self, pid: str, temperature: float = 0.2, model: Optional[str] = None) -> Dict[str, Any]:
        """Generate a step-by-step explanation, approach, and complexity using Gemini.

        Falls back to a heuristic Markdown if Gemini is unavailable.
        """
        p = self.get_by_id(pid)
        if p is None:
            return {"ok": False, "error": f"Problem '{pid}' not found"}
        prompt = (
            "You are a senior algorithms mentor. Given the LeetCode problem below, "
            "produce a clear, practical study guide:\n\n"
            "- Title and difficulty\n"
            "- Key observations\n"
            "- Step-by-step approach\n"
            "- Time and space complexity\n"
            "- Common pitfalls\n"
            "- 2–3 hints (progressively revealing)\n"
            "- Clean Python solution (if appropriate)\n\n"
            f"Title: {p.title}\nDifficulty: {p.difficulty}\nTopics: {', '.join(p.topics or [])}\n\n"
            f"Description:\n{p.description}\n\n"
        )
        try:
            client = GeminiClient(model=model, temperature=temperature)
            res = client.generate(prompt, temperature=temperature)
            if res.get("ok"):
                return {"ok": True, "markdown": res.get("answer"), "model": res.get("model")}
            return {"ok": False, "error": res.get("error")}
        except Exception:
            # Fallback heuristic
            md = [
                f"# {p.title} ({p.difficulty})",
                f"Topics: {', '.join(p.topics or [])}",
                "",
                "## Observations",
                "- Identify input constraints and target output",
                "- Consider edge cases (empty input, duplicates, extremes)",
                "",
                "## Approach",
                "- Use a standard DS/Algo aligned with topics",
                "- Maintain invariants and verify correctness",
                "",
                "## Complexity",
                "- Time: O(n log n) or as appropriate",
                "- Space: O(n)",
                "",
                "## Pitfalls",
                "- Off-by-one errors, overflow, incorrect base cases",
                "",
                "## Hints",
                "1. Try a simpler subproblem first",
                "2. Consider using an auxiliary structure",
                "3. Optimize by avoiding repeated work",
            ]
            return {"ok": True, "markdown": "\n".join(md), "model": None}

    def get_stats(self) -> Dict[str, Any]:
        """Return dataset stats for UI (counts by difficulty/topics)."""
        by_diff: Dict[str, int] = {}
        topics: Dict[str, int] = {}
        for p in self._problems:
            d = (p.difficulty or "").strip().title()
            by_diff[d] = by_diff.get(d, 0) + 1
            for t in p.topics or []:
                t = t.strip().title()
                topics[t] = topics.get(t, 0) + 1
        return {
            "total": len(self._problems),
            "by_difficulty": by_diff,
            "top_topics": sorted(topics.items(), key=lambda x: x[1], reverse=True)[:30],
        }

    def get_by_id(self, pid: str) -> Optional[LCProblem]:
        i = self._id_index.get(pid)
        if i is None:
            # try match by title key
            for p in self._problems:
                if p.pid == pid:
                    return p
            return None
        return self._problems[i]

    # ----------------------
    # Internal helpers
    # ----------------------
    def _load_cached_embeddings(self) -> bool:
        """Use embeddings.npy if it matches the problem list; never computes anything."""
        emb_path = self.cache_dir / "embeddings.npy"
        if not emb_path.exists():
            return False
        try:
            arr = np.load(str(emb_path), allow_pickle=False)
        except Exception:
            return False
        if arr.ndim != 2 or arr.shape[0] != len(self._problems):
            return False
        self._embeddings = arr
        return True

    def _ensure_embeddings(self) -> None:
        """Create embeddings for all problems' text (title + description)."""
        emb_path = self.cache_dir / "embeddings.npy"
        if emb_path.exists():
            try:
                self._embeddings = np.load(str(emb_path))
                return
            except Exception:
                pass
        texts = [f"{p.title}\n\n{p.description}" for p in self._problems]
        arr = embed_texts(texts, model_name=self.model_name)
        np.save(str(emb_path), arr)
        self._embeddings = arr

    _STOP = frozenset("a an the of in on at to for from by with and or is are be it this that given return find".split())

    def _terms(self, text: str) -> set:
        return {t for t in re.findall(r"\w+", text.lower()) if t not in self._STOP}

    def _keyword_scores(self, query: str, docs: List[Tuple[str, str]]) -> List[float]:
        """Rank (title, description) pairs: query-term coverage of the title counts triple,
        an exact title match gets a bonus, and description coverage breaks ties."""
        q = self._terms(query)
        if not q:
            return [0.0] * len(docs)
        q_norm = " ".join(sorted(q))
        scores: List[float] = []
        for title, description in docs:
            t = self._terms(title)
            cov_title = len(q & t) / len(q)
            cov_desc = len(q & self._terms(description)) / len(q)
            exact = 1.0 if t and " ".join(sorted(t)) == q_norm else 0.0
            scores.append(3.0 * cov_title + cov_desc + 2.0 * exact)
        return scores

    def _merge_problem(self, a: LCProblem, b: LCProblem) -> LCProblem:
        def pick(x, y):
            return x if x not in [None, "", 0] else y
        return LCProblem(
            pid=pick(a.pid, b.pid),
            title=pick(a.title, b.title),
            difficulty=pick(a.difficulty, b.difficulty),
            topics=list(sorted(set((a.topics or []) + (b.topics or [])))) or [],
            description=pick(a.description, b.description),
            url=pick(a.url, b.url),
            acceptance=pick(a.acceptance, b.acceptance),
            likes=pick(a.likes, b.likes),
            dislikes=pick(a.dislikes, b.dislikes),
            source=pick(a.source, b.source),
        )

    def rebuild_from_local(self) -> int:
        """Re-create normalized_problems.jsonl from the raw CSV/JSON files under cache_dir.

        Offline only (no downloads). Use after the parsing rules change, since `load_all`
        prefers an existing normalized file. Returns the number of problems written.
        """
        probs: List[LCProblem] = []
        for p in sorted(self.cache_dir.rglob("*")):
            if p.is_file() and p.name != "normalized_problems.jsonl" and p.suffix.lower() in {".csv", ".json", ".jsonl"}:
                if "hf_" in p.parent.name or p.parent == self.cache_dir or "kaggle" in p.parts:
                    try:
                        probs.extend(self._parse_any_file(p, source="local"))
                    except Exception:
                        continue
        uniq: Dict[str, LCProblem] = {}
        for pr in probs:
            key = (pr.title or pr.pid).strip().lower()
            uniq[key] = self._merge_problem(uniq[key], pr) if key in uniq else pr
        merged = list(uniq.values())
        self._write_normalized_jsonl(self.cache_dir / "normalized_problems.jsonl", merged)
        (self.cache_dir / "embeddings.npy").unlink(missing_ok=True)  # row order changed
        self._problems, self._loaded, self._embeddings = [], False, None
        return len(merged)

    # ----------------------
    # Reading / Writing normalized
    # ----------------------
    def _write_normalized_jsonl(self, path: Path, problems: List[LCProblem]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for p in problems:
                f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")

    def _read_normalized_jsonl(self, path: Path) -> List[LCProblem]:
        out: List[LCProblem] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    out.append(LCProblem(**obj))
                except Exception:
                    continue
        return out

    # ----------------------
    # HuggingFace loader
    # ----------------------
    def _try_load_huggingface(self) -> int:
        if hf_hub_download is None:
            raise RuntimeError("huggingface_hub not installed")
        repo_id = "kaysss/leetcode-problem-set"
        # Attempt to download a known file; if unknown, try index
        # Many HF datasets provide a JSONL or CSV; we handle both paths.
        target_dir = self.cache_dir / "hf_kaysss"
        target_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        candidates = [
            "leetcode-problemset.jsonl",
            "data.jsonl",
            "dataset.json",
            "dataset.csv",
        ]
        downloaded = None
        for fname in candidates:
            try:
                p = hf_hub_download(repo_id=repo_id, filename=fname, local_dir=str(target_dir))
                downloaded = Path(p)
                break
            except Exception:
                continue
        if downloaded is None:
            # Try to download repo index file list; if not available, bail out.
            raise RuntimeError("could not locate dataset file in HF repo")
        # Parse
        problems = self._parse_any_file(downloaded, source="huggingface:kaysss")
        self._write_normalized_jsonl(self.cache_dir / "normalized_problems.jsonl", problems)
        count = len(problems)
        return count

    # ----------------------
    # Kaggle loader
    # ----------------------
    def _try_load_kaggle_competition(self, dataset: str) -> int:
        kaggle = _import_kaggle()
        if kaggle is None:
            # Attempt to read pre-downloaded content from cache_dir
            return self._try_parse_local_kaggle_dump(dataset)
        dest = self.cache_dir / "kaggle"
        dest.mkdir(parents=True, exist_ok=True)
        try:
            kaggle.api.authenticate()
            kaggle.api.dataset_download_files(dataset, path=str(dest), unzip=True)
        except (Exception, SystemExit):
            # kaggle calls sys.exit() when credentials are missing; use the local dump instead
            return self._try_parse_local_kaggle_dump(dataset)
        # parse any CSV/JSON found in dest/dataset_name
        return self._parse_dir_for_dataset(dest, dataset)

    def _try_parse_local_kaggle_dump(self, dataset: str) -> int:
        root = self.cache_dir / "kaggle"
        if not root.exists():
            return 0
        return self._parse_dir_for_dataset(root, dataset)

    def _parse_dir_for_dataset(self, root: Path, dataset: str) -> int:
        found = 0
        probs: List[LCProblem] = []
        for p in root.rglob("*"):
            if p.is_file() and any(p.name.lower().endswith(ext) for ext in [".csv", ".json", ".jsonl"]):
                try:
                    ps = self._parse_any_file(p, source=f"kaggle:{dataset}")
                    probs.extend(ps)
                except Exception:
                    continue
        if probs:
            self._write_normalized_jsonl(self.cache_dir / "normalized_problems.jsonl", probs)
            found = len(probs)
        return found

    # ----------------------
    # Local loader
    # ----------------------
    def _try_load_local_files(self) -> int:
        count = 0
        probs: List[LCProblem] = []
        for p in self.cache_dir.rglob("*"):
            if p.is_file() and any(p.name.lower().endswith(ext) for ext in [".csv", ".json", ".jsonl"]):
                if p.name == "normalized_problems.jsonl":
                    continue
                try:
                    ps = self._parse_any_file(p, source="local")
                    probs.extend(ps)
                except Exception:
                    continue
        if probs:
            self._write_normalized_jsonl(self.cache_dir / "normalized_problems.jsonl", probs)
            count = len(probs)
        return count

    # ----------------------
    # Parsing helpers: accept common schemas
    # ----------------------
    def _parse_any_file(self, path: Path, source: str) -> List[LCProblem]:
        name = path.name.lower()
        if name.endswith(".csv"):
            return self._parse_csv(path, source)
        if name.endswith(".jsonl"):
            return self._parse_jsonl(path, source)
        if name.endswith(".json"):
            return self._parse_json(path, source)
        return []

    def _parse_csv(self, path: Path, source: str) -> List[LCProblem]:
        problems: List[LCProblem] = []
        # Prefer pandas if available for robust parsing
        if pd is not None:
            try:
                df = pd.read_csv(path)
                for _, row in df.iterrows():
                    problems.append(self._row_to_problem(row.to_dict(), source))
                return [p for p in problems if p.title and p.description]
            except Exception:
                pass
        # Fallback CSV reader
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                problems.append(self._row_to_problem(row, source))
        return [p for p in problems if p.title and p.description]

    def _parse_jsonl(self, path: Path, source: str) -> List[LCProblem]:
        out: List[LCProblem] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    out.append(self._row_to_problem(obj, source))
                except Exception:
                    continue
        return [p for p in out if p.title and p.description]

    def _parse_json(self, path: Path, source: str) -> List[LCProblem]:
        out: List[LCProblem] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return out
        # Accept both list of dicts and dict with key containing list
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ["data", "items", "problems", "rows"]:
                if isinstance(data.get(key), list):
                    rows = data[key]
                    break
            else:
                rows = []
        else:
            rows = []
        for row in rows:
            try:
                out.append(self._row_to_problem(row, source))
            except Exception:
                continue
        return [p for p in out if p.title and p.description]

    # ----------------------
    # Normalization
    # ----------------------
    def _row_to_problem(self, row: Dict[str, Any], source: str) -> LCProblem:
        # Attempt to map common fields across datasets
        # Known columns across different sources include:
        #  - id, question_id, problem_id
        #  - title, question_title
        #  - difficulty, level
        #  - topics, tags, topic_tags
        #  - description, content, body
        #  - url, link
        def get_any(keys: List[str], default=None):
            for k in keys:
                v = row.get(k)
                if v not in [None, ""]:
                    return v
            return default
        pid = str(get_any(["id", "question_id", "problem_id", "qid", "slug"], default=""))
        title = str(get_any(["title", "question_title", "name"], default="")).strip()
        difficulty = str(get_any(["difficulty", "level"], default="")).strip().title()
        topics_raw = get_any(["topics", "tags", "topic_tags", "Topic_tags", "related_topics", "category", "categories"], default=[])
        if isinstance(topics_raw, str):
            topics = [t.strip() for t in re.split(r"[,;]", topics_raw) if t.strip()]
        elif isinstance(topics_raw, list):
            topics = [str(t).strip() for t in topics_raw if str(t).strip()]
        else:
            topics = []
        description = str(get_any(["description", "content", "body", "question"], default="")).strip()
        url = get_any(["url", "link", "leetcode_url", "question_url"], default=None)
        acceptance = get_any(["acceptance", "acceptance_rate"], default=None)
        try:
            acceptance = float(acceptance) if acceptance is not None and str(acceptance) not in ["", "nan"] else None
        except Exception:
            acceptance = None
        likes = get_any(["likes", "thumbs_up"], default=None)
        try:
            likes = int(likes) if likes is not None and str(likes) not in ["", "nan"] else None
        except Exception:
            likes = None
        dislikes = get_any(["dislikes", "thumbs_down"], default=None)
        try:
            dislikes = int(dislikes) if dislikes is not None and str(dislikes) not in ["", "nan"] else None
        except Exception:
            dislikes = None

        # Ensure minimal fields
        if not title or not description:
            # Some datasets store HTML; attempt basic cleanup
            description = re.sub(r"<[^>]+>", " ", description or "").strip()
        if difficulty not in {"Easy", "Medium", "Hard"}:
            # Attempt to infer from topics or leave blank
            pass
        if not pid:
            pid = f"{title.lower().replace(' ', '-')[:50]}"

        return LCProblem(
            pid=pid,
            title=title,
            difficulty=difficulty or "",
            topics=topics,
            description=description,
            url=url,
            acceptance=acceptance,
            likes=likes,
            dislikes=dislikes,
            source=source,
        )


if __name__ == "__main__":
    h = LeetCodeHandler()
    n, status = h.load_all()
    print(f"Loaded {n} problems ({status})")
    print("Stats:", json.dumps(h.get_stats(), indent=2))
    res = h.search("binary search tree", top_k=5, difficulty=["Easy", "Medium"], topics=["Tree", "Binary Search"])
    for r in res:
        print(f" - {r['title']} [{r['difficulty']}] score={r['score']:.3f}")