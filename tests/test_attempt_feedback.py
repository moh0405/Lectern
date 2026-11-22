"""Try first: POST /attempt/feedback judges each step of a student's attempt against the passages, checks the citations
the way Ask does, labels uncited verdicts as unchecked, and never hands back the solution."""

import json

import pytest

from backend.attempt_feedback import AttemptTooLong, build_prompt, split_units

HEAP = {"text": "Insert places the new key at the bottom of the heap and sifts it up, swapping with its parent while the "
                "parent is larger. A complete binary tree with n nodes has height about log n, so insert takes O(log n).",
        "doc": "heaps.pdf", "page": 2}
QUEUE = {"text": "A priority queue is usually implemented with a binary heap.", "doc": "queues.md"}
Q = "Why is inserting into a binary heap O(log n)?"
ATTEMPT = "1. Put the new key at the bottom.\n2. Swap it down with its children.\n3. The height is log n."
KEY = ("The new key is added at the bottom and sifted up, swapping with its parent at most once per level, and a "
       "complete binary tree has height log n, so at most log n swaps happen.")


def reply(items, summary="Look at step 2 first.", answer_key=KEY):
    return lambda prompt, json_mode: json.dumps({"answer_key": answer_key, "summary": summary, "items": items})


def post(api, **body):
    return api.post("/api/v1/attempt/feedback", json={"question": Q, "attempt": ATTEMPT, "context": [HEAP, QUEUE], **body})


class TestSplitting:
    def test_steps_drop_blank_lines_and_own_numbering(self):
        assert split_units("1. a\n\n2) b\nStep 3: c\n  d  ", "steps") == ["a", "b", "c", "d"]

    def test_code_keeps_blank_lines_so_numbers_match_the_editor(self):
        assert split_units("\ndef f(x):\n\n    return x\n\n", "code") == ["def f(x):", "", "    return x"]

    def test_short_answer_splits_sentences(self):
        assert split_units("A heap is a tree. It is complete! Is it? yes.", "short_answer") == [
            "A heap is a tree.", "It is complete!", "Is it? yes."]

    def test_too_many_units(self):
        with pytest.raises(AttemptTooLong):
            split_units("\n".join(f"step {i}" for i in range(31)), "steps")

    def test_prompt_numbers_units_labels_passages_and_forbids_the_solution(self):
        prompt = build_prompt(Q, ["Put it at the bottom.", "Swap down."], "steps", [HEAP], None)
        assert "Step 1: Put it at the bottom.\nStep 2: Swap down." in prompt
        assert "- [heaps.pdf (page 2)] Insert places" in prompt
        for phrase in ("Never write the correct solution", "not what the right version is", "answer_key",
                       "Do not judge it from general knowledge", "TASK: ATTEMPT_FEEDBACK"):
            assert phrase in prompt

    def test_code_prompt_names_the_language(self):
        prompt = build_prompt("Reverse a list", ["def r(xs):", "    return xs[::-1]"], "code", [], "Python")
        assert "a program in Python" in prompt and "Line 2:     return xs[::-1]" in prompt
        assert "(none: nothing in the student's material matched" in prompt


class TestRoute:
    def test_verdicts_are_checked_like_ask_citations(self, api, fake_gemini):
        fake_gemini.handler = reply([
            {"unit": 1, "verdict": "supported", "note": "Yes, see the start of the passage.", "citations": ["heaps.pdf (page 2)"]},
            {"unit": 2, "verdict": "contradicted", "note": "Re-read which direction [heaps.pdf (page 2)] moves the key.", "citations": ["heaps.pdf (page 9)"]},
            {"unit": 3, "verdict": "supported", "note": "Right.", "citations": ["Invented.pdf (page 1)"]},
        ])
        r = post(api)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["units"] == ["Put the new key at the bottom.", "Swap it down with its children.", "The height is log n."]
        assert [i["ref"] for i in body["items"]] == ["Step 1", "Step 2", "Step 3"]
        one, two, three = body["items"]
        assert one["checked"] is True and one["citations"][0]["status"] == "ok"
        # A wrong page is flagged, but the inline citation in the note verifies the contradiction.
        assert {c["status"] for c in two["citations"]} == {"page_not_retrieved", "ok"} and two["checked"] is True
        # Supported by an invented source: not checked against your sources.
        assert three["citations"][0]["status"] == "unknown_source" and three["checked"] is False
        assert body["unverified_citations"] == 2
        assert [c["doc"] for c in body["chunks"]] == ["heaps.pdf", "queues.md"]
        assert body["model"] == "fake-model"
        assert len(fake_gemini.calls) == 1  # one model call per feedback request

    def test_uncited_verdict_is_unchecked_and_not_covered_never_cites(self, api, fake_gemini):
        fake_gemini.handler = reply([
            {"unit": 1, "verdict": "supported", "note": "Looks fine.", "citations": []},
            {"unit": 2, "verdict": "not_covered", "note": "Not in your notes.", "citations": ["heaps.pdf (page 2)"]},
        ])
        items = post(api).json()["items"]
        assert items[0]["checked"] is False and items[0]["citations"] == []
        assert items[1]["checked"] is False and items[1]["citations"] == []

    def test_bad_items_are_dropped(self, api, fake_gemini):
        fake_gemini.handler = reply([
            {"unit": 9, "verdict": "supported", "note": "x", "citations": []},
            {"unit": "two", "verdict": "supported", "note": "x"},
            {"unit": 1, "verdict": "maybe", "note": "x"},
            {"unit": 2, "verdict": "Not covered", "note": "Nothing on this."},
            {"unit": 2, "verdict": "supported", "note": "duplicate"},
            "junk",
        ])
        items = post(api).json()["items"]
        assert [(i["unit"], i["verdict"]) for i in items] == [(2, "not_covered")]

    def test_feedback_that_gives_the_answer_away_is_replaced(self, api, fake_gemini):
        leaky = ("Wrong direction: the key is sifted up, swapping with its parent at most once per level, and the "
                 "complete tree has height log n so there are at most log n swaps.")
        fake_gemini.handler = reply(
            [{"unit": 2, "verdict": "contradicted", "note": leaky, "citations": ["heaps.pdf (page 2)"]},
             {"unit": 1, "verdict": "supported", "note": "```python\nheap.append(x)\n```", "citations": ["heaps.pdf (page 2)"]}],
            summary="The answer is that insert sifts up once per level.",
        )
        body = post(api).json()
        assert body["withheld"] == 2
        notes = {i["unit"]: i["note"] for i in body["items"]}
        assert notes[2].startswith("This does not match the cited passage")
        assert "```" not in notes[1] and notes[1].startswith("Your sources back this")  # a code fix is removed
        assert body["summary"].startswith("Compare the flagged parts")
        assert "answer_key" not in json.dumps(body) and KEY not in json.dumps(body)

    def test_repeating_what_the_student_wrote_is_not_a_leak(self, api, fake_gemini):
        note = "Yes: the passage says the new key goes at the bottom of the heap."
        fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "note": note, "citations": ["heaps.pdf (page 2)"]}])
        body = post(api).json()
        assert body["items"][0]["note"] == note and body["withheld"] == 0

    def test_retrieves_from_the_index_without_context(self, indexed, fake_gemini):
        fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "note": "ok", "citations": ["heaps.pdf (page 1)"]}])
        r = indexed.post("/api/v1/attempt/feedback", json={"question": "What is a binary heap?", "attempt": "A complete binary tree.", "format": "short_answer"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["chunks"][0]["doc"] == "heaps.pdf" and body["items"][0]["checked"] is True
        assert "- [heaps.pdf (page 1)]" in fake_gemini.calls[-1]

    def test_k_zero_without_context_judges_against_nothing(self, api, fake_gemini):
        fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "note": "ok", "citations": ["heaps.pdf (page 2)"]}])
        body = api.post("/api/v1/attempt/feedback", json={"question": Q, "attempt": "Swap up.", "k": 0}).json()
        assert body["chunks"] == [] and body["items"][0]["checked"] is False
        assert "(none: nothing in the student's material matched" in fake_gemini.calls[-1]

    def test_model_named_in_request_is_passed_through(self, api, fake_gemini):
        fake_gemini.handler = reply([])
        assert post(api, model="gemini-2.5-flash-lite").json()["model"] == "gemini-2.5-flash-lite"

    @pytest.mark.parametrize("body, code", [
        ({"attempt": "\n\n  \n"}, "attempt_empty"),
        ({"attempt": "\n".join(f"s{i}" for i in range(40))}, "attempt_too_long"),
        ({"format": "essay"}, "validation_error"),
        ({"attempt": ""}, "validation_error"),
    ])
    def test_invalid_attempts(self, api, fake_gemini, body, code):
        r = post(api, **body)
        assert r.status_code == 422 and r.json()["error"]["code"] == code
        assert fake_gemini.calls == []

    def test_unreadable_reply_is_a_model_error(self, api, fake_gemini):
        fake_gemini.handler = lambda p, j: "I think it's mostly right!"
        r = post(api)
        assert r.status_code == 502 and r.json()["error"]["code"] == "llm_error"

    def test_daily_limit_and_missing_key(self, api, fake_gemini):
        fake_gemini.fail_with = RuntimeError("Daily limit of model calls reached; calls are paused until midnight UTC")
        assert post(api).json()["error"]["code"] == "daily_limit"
        fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set")
        r = post(api)
        assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"

    def test_scripted_judge_flags_a_negated_step(self, api, fake_gemini):
        """The deterministic judge the e2e server uses (tests/fake_gemini.py)."""
        attempt = "Insert places the new key at the bottom.\nThe key is never swapped with its parent.\nHeaps are blue."
        body = post(api, attempt=attempt).json()
        assert [(i["verdict"], i["checked"]) for i in body["items"]] == [("supported", True), ("contradicted", True), ("not_covered", False)]
        assert body["summary"] == "Look at step 2 first."
