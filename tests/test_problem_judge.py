"""LeetCode Try first: `judge: problem` may judge reasoning against the problem statement, labels it as such, never gives
it a verified citation and never lets it carry the solution. The default judge is unchanged."""

import json

import pytest

from backend.attempt_feedback import PROBLEM_NOTE, PROBLEM_SUMMARY, PROMPT, build_prompt

STATEMENT = {"text": "Given an array of integers nums and an integer target, return indices of the two numbers such that "
                     "they add up to target.", "doc": "LeetCode 1. Two Sum"}
Q = "Solve LeetCode problem 1: Two Sum"
RIGHT = "Store each number's index in a hash map.\nLook up target minus the number."
KEY = "Keep a dictionary from value to index and check whether the complement was already seen during one pass."
LABEL = "LeetCode 1. Two Sum"


def reply(items, summary="Step 1 is on track.", answer_key=KEY):
    return lambda prompt, json_mode: json.dumps({"answer_key": answer_key, "summary": summary, "items": items})


def post(api, attempt=RIGHT, judge="problem", **body):
    return api.post("/api/v1/attempt/feedback", json={"question": Q, "attempt": attempt, "context": [STATEMENT], "judge": judge, **body})


def test_default_judge_keeps_the_source_prompt_and_ignores_a_claimed_basis(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "problem", "note": "Fine.", "citations": [LABEL]}])
    r = api.post("/api/v1/attempt/feedback", json={"question": Q, "attempt": RIGHT, "context": [STATEMENT]})
    item = r.json()["items"][0]
    assert item["basis"] == "sources" and item["checked"] is True
    assert fake_gemini.calls[0] == build_prompt(Q, RIGHT.split("\n"), "steps", [{**STATEMENT, "page": None, "end_page": None, "score": None}])
    assert "JUDGE: problem" not in PROMPT and "JUDGE: problem" not in fake_gemini.calls[0]


def test_correct_method_is_reasoned_with_one_call_and_no_citation(api, fake_gemini):
    fake_gemini.handler = reply([
        {"unit": 1, "verdict": "supported", "basis": "problem", "note": "This works for the statement.", "citations": []},
        {"unit": 2, "verdict": "supported", "basis": "problem", "note": "Good.", "citations": []},
    ])
    body = post(api).json()
    assert len(fake_gemini.calls) == 1 and "JUDGE: problem" in fake_gemini.calls[0]
    assert [(i["verdict"], i["basis"], i["checked"], i["citations"]) for i in body["items"]] == [("supported", "problem", False, [])] * 2


def test_wrong_step_is_still_flagged(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 2, "verdict": "contradicted", "basis": "problem", "note": "What if the same element is used twice?", "citations": []}])
    item = post(api).json()["items"][0]
    assert (item["verdict"], item["basis"], item["checked"]) == ("contradicted", "problem", False)
    assert item["note"] == "What if the same element is used twice?"


@pytest.mark.parametrize("claimed", ["problem", "sources", None])
def test_citing_the_statement_for_a_method_it_never_mentions_is_not_source_backed(api, fake_gemini, claimed):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": claimed, "note": "Fine.", "citations": [LABEL]}])
    item = post(api, attempt="Keep a hash map of seen values for constant time lookups.").json()["items"][0]
    assert item["basis"] == "problem" and item["checked"] is False
    assert not [c for c in item["citations"] if c["status"] == "ok"]


def test_a_claim_the_statement_really_makes_stays_source_backed(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "sources", "note": "Yes.", "citations": [LABEL]}])
    item = post(api, attempt="Return indices of the two numbers that add up to target.").json()["items"][0]
    assert item["basis"] == "sources" and item["checked"] is True and item["citations"][0]["status"] == "ok"


def test_invented_citation_is_still_reported(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "sources", "note": "Fine.", "citations": ["Invented.pdf (page 3)"]}])
    body = post(api).json()
    item = body["items"][0]
    assert item["basis"] == "problem" and item["citations"][0]["status"] == "unknown_source" and body["unverified_citations"] == 1


def test_a_reasoned_note_that_cites_a_passage_is_replaced(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "problem", "note": f"See [{LABEL}].", "citations": []}])
    item = post(api).json()["items"][0]
    assert item["note"] == PROBLEM_NOTE["supported"] and item["citations"] == []


@pytest.mark.parametrize("note", [
    "Use a hash map here.",
    "You should store the complement.",
    "Replace this with a dictionary.",
    "Write `seen[x] = i` on this line.",
    "Set seen[num] = i before moving on.",
    "```python\nreturn [i, j]\n```",
    "The answer is a dictionary from value to index.",
    "Keep a dictionary from value to index and check the complement already seen during one pass.",
])
def test_a_problem_verdict_cannot_carry_the_fix(api, fake_gemini, note):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "contradicted", "basis": "problem", "note": note, "citations": []}])
    body = post(api, attempt="Compare every pair with two nested loops and stop at the end.").json()
    assert body["items"][0]["note"] == PROBLEM_NOTE["contradicted"]
    assert body["withheld"] == (0 if note.startswith("```") else 1)  # a fence is stripped before the guards see the note


def test_a_summary_that_states_the_fix_is_replaced(api, fake_gemini):
    fake_gemini.handler = reply([], summary="You should use a dictionary instead.")
    assert post(api).json()["summary"] == PROBLEM_SUMMARY


def test_without_an_answer_key_problem_notes_fail_closed(api, fake_gemini):
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "problem", "note": "A custom note.", "citations": []}], answer_key="")
    body = post(api).json()
    assert body["items"][0]["note"] == PROBLEM_NOTE["supported"] and body["summary"] == PROBLEM_SUMMARY


def test_quoting_the_students_own_code_is_not_a_leak(api, fake_gemini):
    attempt = "seen[num] = i"
    fake_gemini.handler = reply([{"unit": 1, "verdict": "supported", "basis": "problem", "note": "Why does `seen[num] = i` come after the check?", "citations": []}])
    assert post(api, attempt=attempt, format="code").json()["items"][0]["note"].startswith("Why does")


def test_unknown_judge_is_rejected(api, fake_gemini):
    assert post(api, judge="vibes").status_code == 422 and fake_gemini.calls == []
