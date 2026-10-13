"""Flashcard generation helpers (pure) and Anki export."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend import flashcards as fc


def test_parse_accepts_object_list_and_surrounding_prose():
    obj = json.dumps({"cards": [{"front": "What is a heap?", "back": "A tree."}, {"front": "Q2", "back": "A2"}]})
    assert len(fc.parse_cards(obj, 5)) == 2
    assert len(fc.parse_cards(json.dumps([{"front": "a?", "back": "b"}]), 5)) == 1
    assert fc.parse_cards("Sure! Here you go:\n" + obj + "\nEnjoy.", 5)[0]["front"] == "What is a heap?"


def test_parse_drops_bad_entries_duplicates_and_respects_the_limit():
    items = [{"front": "Same?", "back": "x"}, {"front": "same", "back": "y"}, {"front": "", "back": "z"},
             {"front": "no back"}, "string", {"front": "x" * 2000, "back": "y"}] + [{"front": f"q{i}", "back": "a"} for i in range(10)]
    out = fc.parse_cards(json.dumps({"cards": items}), 3)
    assert [c["front"] for c in out] == ["Same?", "q0", "q1"]


@pytest.mark.parametrize("text", ["", "not json", "{broken", '{"cards": "nope"}', "null"])
def test_parse_garbage_gives_no_cards(text):
    assert fc.parse_cards(text, 5) == []


def test_prompt_contains_context_topic_and_count():
    p = fc.build_prompt([{"doc": "a.pdf", "text": "Heaps are trees."}], 4, topic="heaps")
    assert "[a.pdf] Heaps are trees." in p and "up to 4 flashcards" in p and "'heaps'" in p


def test_csv_quotes_commas_and_newlines():
    out = fc.to_csv([{"front": "a, b?", "back": 'line1\nline "2"'}])
    assert out.splitlines()[0] == "front,back"
    import csv
    assert list(csv.reader(io.StringIO(out)))[1] == ["a, b?", 'line1\nline "2"']


def test_apkg_is_a_zip_with_the_notes_when_genanki_is_installed():
    pytest.importorskip("genanki")
    data = fc.to_apkg([{"front": "Q <b>", "back": "A"}])
    assert zipfile.is_zipfile(io.BytesIO(data))
    assert "collection.anki2" in zipfile.ZipFile(io.BytesIO(data)).namelist()


def test_apkg_is_none_without_genanki(monkeypatch):
    import builtins
    real = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda n, *a, **k: (_ for _ in ()).throw(ImportError()) if n == "genanki" else real(n, *a, **k))
    assert fc.to_apkg([{"front": "a", "back": "b"}]) is None
