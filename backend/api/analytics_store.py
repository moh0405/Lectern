"""Tiny SQLite store for query analytics (survives restarts, unlike session state)."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List


class AnalyticsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._ready = False

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        if not self._ready:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, question TEXT NOT NULL,"
                "avg_score REAL NOT NULL, latency_ms INTEGER NOT NULL, tokens_prompt INTEGER NOT NULL,"
                "tokens_answer INTEGER NOT NULL, mode TEXT, docs TEXT NOT NULL, ok INTEGER NOT NULL)"
            )
            self._ready = True
        return conn

    def record(self, question: str, scores: List[float], latency_ms: int, prompt: str, answer: str,
               mode: str | None, docs: List[str], ok: bool) -> None:
        avg = sum(scores) / len(scores) if scores else 0.0
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO events (ts, question, avg_score, latency_ms, tokens_prompt, tokens_answer, mode, docs, ok)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (time.time(), question, avg, latency_ms, len(prompt) // 4, len(answer) // 4, mode,
                     json.dumps(docs), int(ok)),
                )
                conn.commit()
            finally:
                conn.close()

    def events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            finally:
                conn.close()
        return [{**dict(r), "docs": json.loads(r["docs"]), "ok": bool(r["ok"])} for r in rows]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()
            finally:
                conn.close()
        n = len(rows)
        doc_usage: Dict[str, int] = {}
        days = set()
        for r in rows:
            days.add(dt.datetime.fromtimestamp(r["ts"]).date())
            for d in json.loads(r["docs"]):
                if d:
                    doc_usage[d] = doc_usage.get(d, 0) + 1
        streak, day = 0, dt.date.today()
        while day in days or (streak == 0 and day - dt.timedelta(days=1) in days):
            if day in days:
                streak += 1
            day -= dt.timedelta(days=1)
        return {
            "queries": n,
            "avg_score": sum(r["avg_score"] for r in rows) / n if n else 0.0,
            "avg_latency_ms": sum(r["latency_ms"] for r in rows) / n if n else 0.0,
            "tokens_prompt": sum(r["tokens_prompt"] for r in rows),
            "tokens_answer": sum(r["tokens_answer"] for r in rows),
            "doc_usage": dict(sorted(doc_usage.items(), key=lambda kv: kv[1], reverse=True)),
            "streak_days": streak,
        }

    def clear(self) -> int:
        with self._lock:
            conn = self._conn()
            try:
                n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                conn.execute("DELETE FROM events")
                conn.commit()
            finally:
                conn.close()
        return n
