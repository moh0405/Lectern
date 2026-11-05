"""Flashcards from study material: the prompt, tolerant parsing of the model's reply, and Anki export.

Pure functions (no model call, no database) so they are easy to test. The router does the I/O.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Dict, Iterable, List, Sequence

MAX_SIDE = 1200


def build_prompt(chunks: Sequence[Dict[str, Any]], n: int, topic: str | None = None) -> str:
    context = "\n\n".join(f"[{c.get('doc')}] {c.get('text', '')}" for c in chunks)[:8000]
    focus = f" about '{topic}'" if topic else ""
    return (
        f"You are a flashcard author. From the CONTEXT below, write up to {n} flashcards{focus}. "
        "Each card tests one idea: a short question on the front, a concise answer (1-3 sentences) on the back. "
        "Use only facts in the context. No duplicate or trivial cards. "
        'Return only JSON: {"cards": [{"front": "...", "back": "..."}]}\n\n'
        f"CONTEXT:\n{context}\n"
    )


def parse_cards(text: str, limit: int) -> List[Dict[str, str]]:
    """Cards from a model reply. Accepts {"cards": [...]} or a bare list, ignores prose around the JSON, drops
    entries without both sides or with an over-long side, and removes duplicate fronts."""
    text = (text or "").strip()
    data: Any = None
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: text.find(p[0]) if p[0] in text else len(text))  # outermost first
    for opener, closer in pairs:
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                break
            except ValueError:
                continue
    items = data.get("cards") if isinstance(data, dict) else data
    out: List[Dict[str, str]] = []
    seen = set()
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        front, back = str(it.get("front") or "").strip(), str(it.get("back") or "").strip()
        key = re.sub(r"\W+", " ", front.lower()).strip()
        if not front or not back or len(front) > MAX_SIDE or len(back) > MAX_SIDE or key in seen:
            continue
        seen.add(key)
        out.append({"front": front, "back": back})
        if len(out) >= limit:
            break
    return out


def to_csv(cards: Iterable[Dict[str, Any]]) -> str:
    """front,back CSV with a header; Anki's importer reads it directly (File > Import)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["front", "back"])
    for c in cards:
        w.writerow([c["front"], c["back"]])
    return buf.getvalue()


# Fixed ids so re-exporting updates the same note type/deck in Anki instead of creating copies.
_MODEL_ID, _DECK_ID = 1607392319, 2059400110


def to_apkg(cards: Sequence[Dict[str, Any]], deck_name: str = "Lectern") -> bytes | None:
    """An Anki package (.apkg), or None if the optional `genanki` package is not installed."""
    try:
        import genanki
    except Exception:
        return None
    import os
    import tempfile

    model = genanki.Model(
        _MODEL_ID, "Lectern card",
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card 1", "qfmt": "{{Front}}", "afmt": '{{FrontSide}}<hr id="answer">{{Back}}'}],
    )
    deck = genanki.Deck(_DECK_ID, deck_name)
    for c in cards:
        # guid from the content so importing the same card twice does not duplicate it
        deck.add_note(genanki.Note(model=model, fields=[_esc(c["front"]), _esc(c["back"])], guid=genanki.guid_for(c["front"], c["back"])))
    fd, path = tempfile.mkstemp(suffix=".apkg")
    os.close(fd)
    try:
        genanki.Package(deck).write_to_file(path)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
