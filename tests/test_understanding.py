"""The Understanding step: a similar practice question (grounded, answer never returned), explanations from the same
passages, and the student's own-words note on a saved turn."""

import json
import sqlite3

from backend.api.study_store import StudyStore
from backend.similar_practice import gives_answer_away

HEAP = {"text": "Insert places the new key at the bottom of the heap and sifts it up, swapping with its parent while the "
                "parent is larger. A complete binary tree with n nodes has height about log n, so insert takes O(log n).",
        "doc": "heaps.pdf", "page": 2}
QUEUE = {"text": "A priority queue is usually implemented with a binary heap.", "doc": "queues.md"}
Q = "Why is inserting into a binary heap O(log n)?"
GOOD = "A heap holds 1023 keys. How many parent swaps can one insert need at most, and what limits that number?"
KEY = "At most nine swaps, because the tree height limits the sift-up path."


def reply(question=GOOD, answer_key=KEY, citations=("heaps.pdf (page 2)",)):
    return lambda prompt, json_mode: json.dumps({"question": question, "answer_key": answer_key, "citations": list(citations)})


def post(api, **body):
    return api.post("/api/v1/practice/similar", json={"question": Q, "context": [HEAP, QUEUE], **body})


class TestSimilarQuestion:
    def test_returns_a_grounded_question_and_never_the_answer(self, api, fake_gemini):
        fake_gemini.handler = reply()
        res = post(api)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["question"] == GOOD
        assert [c["status"] for c in body["citations"]] == ["ok"]
        assert "answer_key" not in body and KEY not in res.text
        assert len(fake_gemini.calls) == 1
        assert "TASK: SIMILAR_QUESTION" in fake_gemini.calls[0] and HEAP["text"][:40] in fake_gemini.calls[0]

    def test_previous_questions_reach_the_prompt(self, api, fake_gemini):
        fake_gemini.handler = reply()
        assert post(api, previous=["What is the height of a heap with 7 keys?"]).status_code == 200
        assert "* What is the height of a heap with 7 keys?" in fake_gemini.calls[0]

    def test_a_question_containing_its_answer_is_refused(self, api, fake_gemini):
        fake_gemini.handler = reply(question=f"True or false: {KEY}")
        res = post(api)
        assert res.status_code == 502 and KEY not in res.text

    def test_a_question_that_states_the_answer_is_refused(self, api, fake_gemini):
        fake_gemini.handler = reply(question="For a heap of 1023 keys the answer is nine swaps, so how does insert behave?")
        assert post(api).status_code == 502

    def test_sharing_the_answers_topic_words_is_not_a_leak(self):
        # Answer keys a real model wrote; the questions state the premise and leave the answer to the student.
        chaining = "It maintains constant average-time operations by resizing the table whenever the load factor exceeds a set threshold."
        assert not gives_answer_away("What should a hash table do when its load factor exceeds a threshold, so that operations stay constant on average?", chaining)
        bfs = "Breadth-first search uses a queue to visit vertices in order of their distance from the source."
        assert not gives_answer_away("Which traversal would you pick to visit vertices in order of their distance from a source, and what structure does it need?", bfs)
        assert gives_answer_away("Since breadth-first search uses a queue to visit vertices in order of distance from the source, why is that useful?", bfs)

    def test_an_uncited_or_invented_source_is_refused(self, api, fake_gemini):
        for citations in ((), ("invented.pdf (page 9)",)):
            fake_gemini.handler = reply(citations=citations)
            assert post(api).status_code == 502

    def test_a_citation_the_question_shares_nothing_with_is_refused(self, api, fake_gemini):
        fake_gemini.handler = reply(question="Which year did the French Revolution begin in Paris?", citations=("queues.md",))
        assert post(api).status_code == 502

    def test_a_rewording_of_the_original_or_a_previous_question_is_refused(self, api, fake_gemini):
        fake_gemini.handler = reply(question="Why is insert into a binary heap O(log n)?")
        assert post(api).status_code == 502
        fake_gemini.handler = reply()
        assert post(api, previous=[GOOD]).status_code == 502

    def test_unreadable_reply_and_missing_key_are_errors(self, api, fake_gemini):
        fake_gemini.handler = lambda prompt, json_mode: "not json"
        assert post(api).status_code == 502
        fake_gemini.handler = reply(answer_key="")
        assert post(api).status_code == 502

    def test_passages_are_required(self, api):
        assert api.post("/api/v1/practice/similar", json={"question": Q, "context": []}).status_code == 422
        assert api.post("/api/v1/practice/similar", json={"question": Q}).status_code == 422


def test_adaptive_explains_from_the_given_passages(api, fake_gemini):
    fake_gemini.handler = lambda prompt, json_mode: "Think of a ladder."
    res = api.post("/api/v1/adaptive", json={"question": Q, "level": "ELI5", "context": [HEAP]})
    assert res.status_code == 200, res.text
    assert [c["doc"] for c in res.json()["chunks"]] == ["heaps.pdf"]
    assert HEAP["text"][:40] in fake_gemini.calls[0]


class TestHistoryNote:
    def test_note_is_saved_returned_and_cleared(self, api):
        saved = api.post("/api/v1/history", json={"question": Q, "answer": "Because of the height."}).json()
        assert saved["note"] is None
        res = api.put(f"/api/v1/history/{saved['id']}/note", json={"note": "  Height bounds the swaps. "})
        assert res.status_code == 200 and res.json()["note"] == "Height bounds the swaps."
        assert api.get("/api/v1/history").json()["turns"][0]["note"] == "Height bounds the swaps."
        assert api.put(f"/api/v1/history/{saved['id']}/note", json={"note": ""}).json()["note"] is None

    def test_unknown_turn_and_long_note(self, api):
        assert api.put("/api/v1/history/999/note", json={"note": "x"}).status_code == 404
        saved = api.post("/api/v1/history", json={"question": Q, "answer": "a"}).json()
        assert api.put(f"/api/v1/history/{saved['id']}/note", json={"note": "x" * 2001}).status_code == 422

    def test_an_older_database_gains_the_column_and_keeps_its_rows(self, tmp_path):
        path = tmp_path / "study.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, question TEXT NOT NULL, "
                     "answer TEXT NOT NULL, mode TEXT, model TEXT, cached INTEGER NOT NULL DEFAULT 0, chunks TEXT NOT NULL DEFAULT '[]', "
                     "citations TEXT NOT NULL DEFAULT '[]', unverified INTEGER NOT NULL DEFAULT 0, uncited INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT INTO history (ts, question, answer) VALUES (1, 'old question', 'old answer')")
        conn.commit()
        conn.close()
        store = StudyStore(path)
        assert store.list_history()[0]["question"] == "old question"
        assert store.set_history_note(1, "mine")["note"] == "mine"
