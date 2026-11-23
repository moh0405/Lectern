"""The Try first eval set is well formed and its scorer measures what it claims, without any model (CI never calls one)."""

import json

from backend.attempt_feedback import split_units
from eval.attempt_eval import LEETCODE_DATA, load, main, passages, run


def oracle(note=lambda case, unit: "Compare this with the cited passage.", cite=True, verdict=None):
    """A scripted judge that answers from the labels, so the scorer's own arithmetic can be checked."""
    def reply(case, _prompt):
        doc = case["passages"][0][0]
        items = [{"unit": int(u), "verdict": verdict or v, "note": note(case, u),
                  "citations": [doc] if cite and (verdict or v) != "not_covered" else []}
                 for u, v in case["expected"].items()]
        return json.dumps({"answer_key": case["answer_key"], "summary": "Look again.", "items": items})
    return reply


def test_eval_set_is_well_formed():
    cases = load()
    assert len(cases) == 15 and len({c["id"] for c in cases}) == 15
    assert sum(any(v == "contradicted" for v in c["expected"].values()) for c in cases) >= 8  # deliberately wrong attempts
    assert {c["format"] for c in cases} == {"steps", "code", "short_answer"}
    for c in cases:
        units = split_units(c["attempt"], c["format"])
        assert passages(c), c["id"]
        for u, v in c["expected"].items():
            assert 1 <= int(u) <= len(units) and units[int(u) - 1].strip(), (c["id"], u)
            assert v in ("supported", "contradicted", "not_covered")


def test_a_perfect_judge_scores_perfectly():
    s = run(oracle())["summary"]
    assert s["accuracy"] == 1 and s["wrong_flagged"] == 1 and s["flag_precision"] == 1
    assert s["attempts_caught"] == s["attempts_with_wrong"] == 10
    assert s["false_confidence"] == 0 and s["citations_verified"] == 1 and s["leaks"] == 0


def test_a_lazy_judge_is_caught_out():
    s = run(oracle(verdict="supported"))["summary"]
    assert s["wrong_flagged"] == 0 and s["attempts_caught"] == 0
    assert s["false_confidence"] == s["wrong_units"]


def test_uncited_verdicts_are_scored_as_unchecked():
    s = run(oracle(cite=False))["summary"]
    assert s["wrong_flagged"] == 0 and s["false_confidence"] == 0 and s["unchecked"] > 0


def test_notes_that_give_the_answer_away_are_replaced_before_scoring():
    s = run(oracle(note=lambda case, unit: case["answer_key"]))["summary"]
    assert s["leaks"] == 0 and s["withheld"] > 0


def test_leetcode_set_covers_correct_wrong_and_partial_attempts():
    cases = load(LEETCODE_DATA)
    assert {c["kind"] for c in cases} == {"correct", "wrong", "partial"} and all(c["judge"] == "problem" for c in cases)
    for c in cases:
        units = split_units(c["attempt"], c["format"])
        assert [p["doc"] for p in passages(c)] == [c["doc"]]
        assert all(1 <= int(u) <= len(units) and units[int(u) - 1].strip() for u in c["expected"]), c["id"]
        assert any(v == "contradicted" for v in c["expected"].values()) == (c["kind"] != "correct"), c["id"]


def test_leetcode_set_scores_reasoned_verdicts_and_catches_a_lazy_judge():
    def judge(verdict=None):
        def reply(case, _prompt):
            items = [{"unit": int(u), "verdict": verdict or v, "basis": "problem", "note": "Trace a small case.", "citations": []}
                     for u, v in case["expected"].items()]
            return json.dumps({"answer_key": case["answer_key"], "summary": "Trace it.", "items": items})
        return reply
    cases = load(LEETCODE_DATA)
    perfect = run(judge(), cases)["summary"]
    assert perfect["accuracy"] == 1 and perfect["wrong_flagged"] == 1 and perfect["leaks"] == 0 and perfect["citations_verified"] is None
    lazy = run(judge("supported"), cases)["summary"]
    assert lazy["wrong_flagged"] == 0 and lazy["false_confidence"] == lazy["wrong_units"] > 0


def test_cli_runs_the_scripted_baseline_and_rescoring_saved_replies(tmp_path, capsys):
    saved = tmp_path / "replies.json"
    assert main(["--save", str(saved)]) == 0
    first = capsys.readouterr().out
    assert "scripted baseline" in first and "| verdict accuracy" in first
    assert main(["--outputs", str(saved)]) == 0
    second = capsys.readouterr().out
    assert first.split("|---|---:|")[1] == second.split("|---|---:|")[1]  # same numbers from the saved replies
