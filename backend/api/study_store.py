"""SQLite store for the single user's study state: flashcards, LeetCode progress and Ask history.

One file (`data/study.db`), no accounts: this is a personal tool. Timestamps are epoch seconds.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import srs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT, front TEXT NOT NULL, back TEXT NOT NULL, source TEXT,
  created_at REAL NOT NULL, ef REAL NOT NULL, interval_days INTEGER NOT NULL, repetitions INTEGER NOT NULL,
  lapses INTEGER NOT NULL, due_at REAL NOT NULL, last_reviewed REAL, reviews INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS lc_progress (
  pid TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0, topics TEXT NOT NULL DEFAULT '[]', difficulty TEXT NOT NULL DEFAULT '',
  updated_at REAL NOT NULL, solved_at REAL);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
  mode TEXT, model TEXT, cached INTEGER NOT NULL DEFAULT 0, chunks TEXT NOT NULL DEFAULT '[]',
  citations TEXT NOT NULL DEFAULT '[]', unverified INTEGER NOT NULL DEFAULT 0, uncited INTEGER NOT NULL DEFAULT 0);
"""

MAX_HISTORY = 500


class StudyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._ready = False

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        if not self._ready:
            conn.executescript(_SCHEMA)
            self._ready = True
        return conn

    def _run(self, sql: str, args: tuple = (), fetch: str = "none") -> Any:
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(sql, args)
                conn.commit()
                if fetch == "all":
                    return [dict(r) for r in cur.fetchall()]
                if fetch == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                return cur.lastrowid if cur.lastrowid else cur.rowcount
            finally:
                conn.close()

    # ------------------------------------------------------------------ flashcards
    def add_card(self, front: str, back: str, source: Optional[str] = None, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        cid = self._run(
            "INSERT INTO cards (front, back, source, created_at, ef, interval_days, repetitions, lapses, due_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)", (front.strip(), back.strip(), source, now, 2.5, 0, 0, 0, now))
        return self.get_card(cid)  # type: ignore[return-value]

    def get_card(self, cid: int) -> Optional[Dict[str, Any]]:
        return self._run("SELECT * FROM cards WHERE id=?", (cid,), "one")

    def list_cards(self, due_only: bool = False, now: Optional[float] = None, limit: int = 500) -> List[Dict[str, Any]]:
        now = time.time() if now is None else now
        if due_only:
            return self._run("SELECT * FROM cards WHERE due_at<=? ORDER BY due_at, id LIMIT ?", (now, limit), "all")
        return self._run("SELECT * FROM cards ORDER BY due_at, id LIMIT ?", (limit,), "all")

    def delete_card(self, cid: int) -> bool:
        return bool(self._run("DELETE FROM cards WHERE id=?", (cid,)))

    def review_card(self, cid: int, grade: int, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
        now = time.time() if now is None else now
        card = self.get_card(cid)
        if card is None:
            return None
        state = srs.review(srs.CardState(card["ef"], card["interval_days"], card["repetitions"], card["lapses"]), grade)
        self._run(
            "UPDATE cards SET ef=?, interval_days=?, repetitions=?, lapses=?, due_at=?, last_reviewed=?, reviews=reviews+1 WHERE id=?",
            (state.ef, state.interval_days, state.repetitions, state.lapses, srs.due_at(now, state), now, cid))
        return self.get_card(cid)

    def card_stats(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        r = self._run(
            "SELECT COUNT(*) AS total, COALESCE(SUM(due_at<=?),0) AS due, COALESCE(SUM(reviews=0),0) AS new_cards,"
            " COALESCE(SUM(interval_days>=21),0) AS mature, COALESCE(SUM(reviews),0) AS reviews FROM cards", (now,), "one")
        return {k: int(v) for k, v in r.items()}

    # ------------------------------------------------------------------ LeetCode progress
    def set_progress(self, pid: str, title: str, status: str, notes: Optional[str] = None, topics: Optional[List[str]] = None,
                     difficulty: str = "", now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        old = self.get_progress(pid)
        attempts = (old["attempts"] if old else 0) + (1 if status in ("attempted", "solved") and (not old or old["status"] != status) else 0)
        solved_at = ((old or {}).get("solved_at") or now) if status == "solved" else None
        self._run(
            "INSERT INTO lc_progress (pid, title, status, notes, attempts, topics, difficulty, updated_at, solved_at)"
            " VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(pid) DO UPDATE SET status=excluded.status, notes=excluded.notes,"
            " attempts=excluded.attempts, topics=excluded.topics, difficulty=excluded.difficulty, updated_at=excluded.updated_at,"
            " solved_at=excluded.solved_at",
            (pid, title, status, (notes if notes is not None else (old or {}).get("notes", "")), attempts,
             json.dumps(topics if topics is not None else (old or {}).get("topics", [])), difficulty or (old or {}).get("difficulty", ""),
             now, solved_at))
        return self.get_progress(pid)  # type: ignore[return-value]

    @staticmethod
    def _decode_progress(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if row is not None:
            row["topics"] = json.loads(row["topics"])
        return row

    def get_progress(self, pid: str) -> Optional[Dict[str, Any]]:
        return self._decode_progress(self._run("SELECT * FROM lc_progress WHERE pid=?", (pid,), "one"))

    def list_progress(self) -> List[Dict[str, Any]]:
        return [self._decode_progress(r) for r in self._run("SELECT * FROM lc_progress ORDER BY updated_at DESC", (), "all")]  # type: ignore[misc]

    def clear_progress(self, pid: str) -> bool:
        return bool(self._run("DELETE FROM lc_progress WHERE pid=?", (pid,)))

    # ------------------------------------------------------------------ Ask history
    def add_history(self, turn: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        hid = self._run(
            "INSERT INTO history (ts, question, answer, mode, model, cached, chunks, citations, unverified, uncited)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (now, turn["question"], turn["answer"], turn.get("mode"), turn.get("model"), int(bool(turn.get("cached"))),
             json.dumps(turn.get("chunks") or []), json.dumps(turn.get("citations") or []),
             int(turn.get("unverified_citations") or 0), int(bool(turn.get("uncited")))))
        self._run("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)", (MAX_HISTORY,))
        return self.get_history_item(hid)  # type: ignore[return-value]

    @staticmethod
    def _decode_history(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if row is not None:
            row["chunks"], row["citations"] = json.loads(row["chunks"]), json.loads(row["citations"])
            row["cached"], row["uncited"] = bool(row["cached"]), bool(row["uncited"])
        return row

    def get_history_item(self, hid: int) -> Optional[Dict[str, Any]]:
        return self._decode_history(self._run("SELECT * FROM history WHERE id=?", (hid,), "one"))

    def list_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [self._decode_history(r) for r in self._run("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,), "all")]  # type: ignore[misc]

    def delete_history(self, hid: Optional[int] = None) -> int:
        if hid is None:
            return self._run("DELETE FROM history")
        return self._run("DELETE FROM history WHERE id=?", (hid,))
