"""SM-2 scheduling, the LeetCode study plan, and the SQLite study store."""

from __future__ import annotations

import pytest

from backend import srs
from backend.api.study_store import StudyStore
from backend.study_plan import build_plan, topic_stats


# ------------------------------------------------------------------ SM-2
def test_first_reviews_follow_1_6_then_ef_multiples():
    s = srs.CardState()
    s = srs.review(s, 4)
    assert (s.interval_days, s.repetitions, s.ef) == (1, 1, 2.5)  # grade 4 leaves EF unchanged
    s = srs.review(s, 4)
    assert s.interval_days == 6
    s = srs.review(s, 4)
    assert s.interval_days == 15 and s.repetitions == 3  # round(6 * 2.5)


def test_a_lapse_resets_progress_but_remembers_it():
    s = srs.CardState(ef=2.5, interval_days=15, repetitions=3)
    s = srs.review(s, 1)
    assert (s.repetitions, s.interval_days, s.lapses) == (0, 1, 1)
    assert s.ef < 2.5


def test_ease_moves_with_grade_and_never_falls_below_the_floor():
    s = srs.CardState()
    assert srs.review(s, 5).ef == pytest.approx(2.6)
    assert srs.review(s, 3).ef == pytest.approx(2.36)
    for _ in range(20):
        s = srs.review(s, 0)
    assert s.ef == srs.MIN_EF


def test_easy_cards_space_out_faster_than_hard_ones():
    easy = hard = srs.CardState()
    for _ in range(5):
        easy, hard = srs.review(easy, 5), srs.review(hard, 3)
    assert easy.interval_days > hard.interval_days


def test_invalid_grade_is_rejected():
    for g in (-1, 6):
        with pytest.raises(ValueError):
            srs.review(srs.CardState(), g)


def test_due_at_adds_whole_days():
    assert srs.due_at(1000.0, srs.CardState(interval_days=2)) == 1000.0 + 2 * 86400


# ------------------------------------------------------------------ study plan
BANK = [
    {"pid": "1", "title": "Two Sum", "difficulty": "Easy", "topics": ["Array", "Hash Table"]},
    {"pid": "2", "title": "Valid Anagram", "difficulty": "Easy", "topics": ["Hash Table", "String"]},
    {"pid": "3", "title": "Climbing Stairs", "difficulty": "Easy", "topics": ["Dynamic Programming"]},
    {"pid": "4", "title": "House Robber", "difficulty": "Medium", "topics": ["Dynamic Programming"]},
    {"pid": "5", "title": "Edit Distance", "difficulty": "Hard", "topics": ["Dynamic Programming", "String"]},
    {"pid": "6", "title": "Binary Search", "difficulty": "Easy", "topics": ["Binary Search"]},
]


def test_topic_stats_counts_attempts_and_solves():
    progress = {"1": {"status": "solved"}, "3": {"status": "attempted"}, "4": {"status": "attempted"}, "6": {"status": "todo"}}
    stats = {s["topic"]: s for s in topic_stats(progress, {p["pid"]: p for p in BANK})}
    assert stats["Array"]["solve_rate"] == 1.0
    assert (stats["Dynamic Programming"]["attempted"], stats["Dynamic Programming"]["solved"]) == (2, 0)
    assert "Binary Search" not in stats  # a todo is not an attempt


def test_plan_puts_weak_topics_first_easiest_first_and_skips_solved():
    progress = {"1": {"status": "solved"}, "3": {"status": "attempted"}}
    plan = build_plan(progress, BANK, size=4)
    assert plan["weak_topics"] == ["Dynamic Programming"]
    assert [i["pid"] for i in plan["items"][:2]] == ["4", "5"]  # 3 is attempted-not-solved: still offered, easiest first
    assert all(i["pid"] != "1" for i in plan["items"])
    assert plan["items"][0]["reason"] == "Weak topic: Dynamic Programming"


def test_plan_with_no_history_suggests_easy_starting_points():
    plan = build_plan({}, BANK, size=3)
    assert plan["weak_topics"] == [] and len(plan["items"]) == 3
    assert {i["difficulty"] for i in plan["items"]} == {"Easy"}
    assert plan["items"][0]["reason"] == "Good place to start"


# ------------------------------------------------------------------ store
@pytest.fixture
def store(tmp_path):
    return StudyStore(tmp_path / "study.db")


def test_new_cards_are_due_immediately_and_reviews_reschedule_them(store):
    card = store.add_card("What is a heap?", "A complete binary tree with the heap property.", now=1000.0)
    assert [c["id"] for c in store.list_cards(due_only=True, now=1000.0)] == [card["id"]]
    after = store.review_card(card["id"], 4, now=1000.0)
    assert after["interval_days"] == 1 and after["due_at"] == 1000.0 + 86400 and after["reviews"] == 1
    assert store.list_cards(due_only=True, now=1000.0) == []
    assert len(store.list_cards(due_only=True, now=1000.0 + 86400)) == 1
    assert store.review_card(999, 4) is None


def test_card_stats_and_delete(store):
    a = store.add_card("a", "b", now=0.0)
    store.add_card("c", "d", now=0.0)
    store.review_card(a["id"], 5, now=0.0)
    st = store.card_stats(now=0.0)
    assert (st["total"], st["due"], st["new_cards"], st["reviews"]) == (2, 1, 1, 1)
    assert store.delete_card(a["id"]) and not store.delete_card(a["id"])


def test_progress_upsert_keeps_notes_and_counts_attempts(store):
    store.set_progress("1", "Two Sum", "attempted", notes="used brute force", topics=["Array"], difficulty="Easy", now=1.0)
    row = store.set_progress("1", "Two Sum", "solved", now=5.0)
    assert row["status"] == "solved" and row["notes"] == "used brute force" and row["topics"] == ["Array"]
    assert row["attempts"] == 2 and row["solved_at"] == 5.0
    again = store.set_progress("1", "Two Sum", "solved", now=9.0)
    assert again["solved_at"] == 5.0 and again["attempts"] == 2  # re-marking does not move the date or inflate attempts
    assert store.set_progress("1", "Two Sum", "todo", now=10.0)["solved_at"] is None
    assert store.clear_progress("1") and store.list_progress() == []


def test_history_round_trips_and_is_newest_first(store):
    store.add_history({"question": "q1", "answer": "a1", "chunks": [{"doc": "d"}], "citations": [{"label": "d"}]}, now=1.0)
    store.add_history({"question": "q2", "answer": "a2", "cached": True, "uncited": True}, now=2.0)
    items = store.list_history()
    assert [i["question"] for i in items] == ["q2", "q1"]
    assert items[1]["chunks"] == [{"doc": "d"}] and items[0]["cached"] is True and items[0]["uncited"] is True
    assert store.delete_history(items[0]["id"]) == 1 and len(store.list_history()) == 1
    store.delete_history()
    assert store.list_history() == []


def test_history_is_capped(store, monkeypatch):
    monkeypatch.setattr("backend.api.study_store.MAX_HISTORY", 3)
    for i in range(6):
        store.add_history({"question": f"q{i}", "answer": "a"}, now=float(i))
    assert [h["question"] for h in store.list_history()] == ["q5", "q4", "q3"]


def test_state_survives_reopening(tmp_path):
    StudyStore(tmp_path / "s.db").add_card("front", "back")
    assert StudyStore(tmp_path / "s.db").list_cards()[0]["front"] == "front"
