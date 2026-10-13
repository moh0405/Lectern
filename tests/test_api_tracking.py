"""Flashcards, LeetCode progress/plan and saved history through the HTTP API."""

from __future__ import annotations

import json

import pytest

LC = "/api/v1/leetcode"


def test_card_lifecycle_review_and_stats(api):
    c = api.post("/api/v1/cards", json={"front": "What is a heap?", "back": "A complete tree.", "source": "trees.md"})
    assert c.status_code == 201
    card = c.json()
    listing = api.get("/api/v1/cards", params={"due": True}).json()
    assert [x["id"] for x in listing["cards"]] == [card["id"]] and listing["stats"]["due"] == 1 and listing["stats"]["new_cards"] == 1

    r = api.post(f"/api/v1/cards/{card['id']}/review", json={"grade": 4})
    assert r.status_code == 200 and r.json()["interval_days"] == 1 and r.json()["reviews"] == 1
    assert api.get("/api/v1/cards", params={"due": True}).json()["cards"] == []
    assert api.get("/api/v1/cards").json()["stats"]["total"] == 1

    assert api.post(f"/api/v1/cards/{card['id']}/review", json={"grade": 9}).status_code == 422
    assert api.post("/api/v1/cards/999/review", json={"grade": 3}).status_code == 404
    assert api.delete(f"/api/v1/cards/{card['id']}").status_code == 204
    assert api.delete(f"/api/v1/cards/{card['id']}").status_code == 404


def test_card_validation(api):
    assert api.post("/api/v1/cards", json={"front": "", "back": "x"}).status_code == 422
    assert api.post("/api/v1/cards", json={"front": "x" * 1300, "back": "x"}).status_code == 422


def test_generate_cards_from_material(indexed, fake_gemini):
    fake_gemini.handler = lambda prompt, json_mode: json.dumps(
        {"cards": [{"front": "What is a binary heap?", "back": "A complete binary tree for priority queues."},
                   {"front": "What is a priority queue?", "back": "An abstract queue ordered by priority."}]})
    r = indexed.post("/api/v1/cards/generate", json={"topic": "heap", "n": 5})
    assert r.status_code == 201, r.text
    cards = r.json()["cards"]
    assert len(cards) == 2 and cards[0]["source"] == "heap" and r.json()["stats"]["total"] == 2
    assert "[heaps.pdf]" in fake_gemini.calls[-1]  # the prompt carried the retrieved passage


def test_generate_cards_errors(api, indexed, fake_gemini):
    fake_gemini.handler = lambda prompt, json_mode: "sorry, no JSON here"
    assert indexed.post("/api/v1/cards/generate", json={}).status_code == 502
    fake_gemini.fail_with = RuntimeError("OPENAI_API_KEY is not set.")
    r = indexed.post("/api/v1/cards/generate", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"


def test_generate_cards_needs_material(api, fake_gemini):
    r = api.post("/api/v1/cards/generate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_material"


def test_export_csv_and_empty_deck(api):
    assert api.get("/api/v1/cards/export").status_code == 409
    api.post("/api/v1/cards", json={"front": "a", "back": "b"})
    r = api.get("/api/v1/cards/export", params={"format": "csv"})
    assert r.status_code == 200 and r.text.startswith("front,back") and "flashcards.csv" in r.headers["content-disposition"]
    assert api.get("/api/v1/cards/export", params={"format": "xml"}).status_code == 422


def test_export_apkg(api):
    api.post("/api/v1/cards", json={"front": "a", "back": "b"})
    r = api.get("/api/v1/cards/export", params={"format": "apkg"})
    try:
        import genanki  # noqa: F401
    except ImportError:
        assert r.status_code == 503 and r.json()["error"]["code"] == "export_unavailable"
    else:
        assert r.status_code == 200 and r.content[:2] == b"PK"


# ------------------------------------------------------------------ LeetCode progress and plan
@pytest.fixture
def pid(api):
    problems = api.get(f"{LC}/search", params={"query": "two sum", "top_k": 1}).json()["problems"]
    assert problems, "the committed dataset should contain Two Sum"
    return problems[0]["pid"]


def test_progress_set_list_clear(api, pid):
    r = api.put(f"{LC}/progress/{pid}", json={"status": "attempted", "notes": "brute force first"})
    assert r.status_code == 200
    item = r.json()
    assert item["status"] == "attempted" and item["notes"] == "brute force first" and item["title"] and item["topics"]
    solved = api.put(f"{LC}/progress/{pid}", json={"status": "solved"}).json()
    assert solved["notes"] == "brute force first" and solved["solved_at"] is not None and solved["attempts"] == 2
    listing = api.get(f"{LC}/progress").json()
    assert listing["summary"]["solved"] == 1 and sum(listing["summary"]["solved_by_difficulty"].values()) == 1
    assert api.delete(f"{LC}/progress/{pid}").status_code == 204
    assert api.delete(f"{LC}/progress/{pid}").status_code == 404
    assert api.get(f"{LC}/progress").json()["items"] == []


def test_progress_validation(api):
    assert api.put(f"{LC}/progress/does-not-exist", json={"status": "solved"}).status_code == 404
    assert api.put(f"{LC}/progress/1", json={"status": "maybe"}).status_code == 422


def test_plan_targets_weak_topics_and_excludes_solved(api, pid):
    start = api.get(f"{LC}/plan", params={"size": 5}).json()
    assert start["weak_topics"] == [] and 0 < len(start["items"]) <= 5
    api.put(f"{LC}/progress/{pid}", json={"status": "attempted"})
    plan = api.get(f"{LC}/plan", params={"size": 8}).json()
    assert plan["weak_topics"], "an attempted-but-unsolved problem makes its topics weak"
    assert any(i["reason"].startswith("Weak topic") for i in plan["items"])
    api.put(f"{LC}/progress/{pid}", json={"status": "solved"})
    assert all(i["pid"] != pid for i in api.get(f"{LC}/plan", params={"size": 30}).json()["items"])


# ------------------------------------------------------------------ history
def test_history_save_list_delete(api):
    turn = {"question": "What is a heap?", "answer": "A tree. [trees.md]", "mode": "technical", "model": "m",
            "chunks": [{"text": "t", "doc": "trees.md", "score": 0.5}],
            "citations": [{"label": "trees.md", "doc": "trees.md", "status": "ok"}]}
    a = api.post("/api/v1/history", json=turn)
    assert a.status_code == 201 and a.json()["id"] and a.json()["chunks"][0]["doc"] == "trees.md"
    api.post("/api/v1/history", json={**turn, "question": "Second?"})
    turns = api.get("/api/v1/history").json()["turns"]
    assert [t["question"] for t in turns] == ["Second?", "What is a heap?"]
    assert api.delete(f"/api/v1/history/{turns[0]['id']}").status_code == 204
    assert api.delete(f"/api/v1/history/{turns[0]['id']}").status_code == 404
    assert api.delete("/api/v1/history").status_code == 204
    assert api.get("/api/v1/history").json()["turns"] == []


def test_history_rejects_oversized_answers(api):
    assert api.post("/api/v1/history", json={"question": "q", "answer": "x" * 30000}).status_code == 422


def test_requires_api_key_when_configured(api, monkeypatch):
    from backend.api.settings import settings
    monkeypatch.setattr(settings, "api_key", "secret")
    assert api.get("/api/v1/cards").status_code == 401
    assert api.get("/api/v1/cards", headers={"X-API-Key": "secret"}).status_code == 200
