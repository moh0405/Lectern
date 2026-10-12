"""Ask (JSON + SSE), tutor tools, LeetCode, notes/export and analytics, using a fake Gemini."""

import json
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

REPO = Path(__file__).resolve().parents[1]


def parse_sse(text: str):
    events = []
    for frame in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


# ----------------------------------------------------------------- ask
def test_ask_returns_answer_chunks_and_prompt(indexed, fake_gemini):
    r = indexed.post("/api/v1/ask", json={"question": "what is a binary heap", "k": 2, "mode": "interview", "include_prompt": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"].startswith("A linked list") and body["model"] == "fake-model"
    assert body["chunks"][0]["doc"] == "heaps.pdf"
    assert "Interview Prep mode" in body["prompt"] and "binary heap" in body["prompt"]
    assert len(fake_gemini.calls) == 1  # retrieval happened once, one model call


def test_ask_hides_prompt_by_default_and_rejects_bad_mode(indexed, fake_gemini):
    assert indexed.post("/api/v1/ask", json={"question": "what is a heap"}).json()["prompt"] is None
    assert indexed.post("/api/v1/ask", json={"question": "what is a heap", "mode": "poem"}).status_code == 422


def test_ask_without_api_key_is_503_with_clear_code(indexed, fake_gemini, monkeypatch):
    fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set. Add it to your environment or .env file.")
    r = indexed.post("/api/v1/ask", json={"question": "what is a heap"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"


def test_ask_upstream_failure_is_502(indexed, fake_gemini):
    fake_gemini.fail_with = ValueError("upstream exploded")
    r = indexed.post("/api/v1/ask", json={"question": "what is a heap"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "llm_error"


def test_ask_stream_event_order_and_content(indexed, fake_gemini):
    r = indexed.post("/api/v1/ask/stream", json={"question": "what is a binary heap", "include_prompt": True})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    events = parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "meta" and names[-1] == "done" and set(names[1:-1]) == {"token"}
    assert events[0][1]["chunks"][0]["doc"] == "heaps.pdf" and "binary heap" in events[0][1]["prompt"]
    assert "".join(d["text"] for e, d in events if e == "token").startswith("A linked list is a chain")
    assert events[-1][1] == {"model": "fake-model"}


def test_ask_stream_reports_errors_as_events(indexed, fake_gemini):
    fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set")
    events = parse_sse(indexed.post("/api/v1/ask/stream", json={"question": "what is a heap"}).text)
    assert [e for e, _ in events] == ["meta", "error"]
    assert events[-1][1]["code"] == "llm_unavailable"


def test_ask_stream_error_after_partial_output(indexed, fake_gemini):
    def handler(prompt, json_mode):
        raise ValueError("boom")

    fake_gemini.handler = handler
    events = parse_sse(indexed.post("/api/v1/ask/stream", json={"question": "what is a heap"}).text)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "llm_error"


def test_ask_stream_validates_before_streaming(indexed):
    assert indexed.post("/api/v1/ask/stream", json={"question": ""}).status_code == 422


def test_suggestions_fall_back_when_model_unavailable(indexed, fake_gemini):
    fake_gemini.fail_with = RuntimeError("no key")
    qs = indexed.get("/api/v1/suggestions", params={"n": 3}).json()["questions"]
    assert len(qs) == 3 and all(isinstance(q, str) and q for q in qs)


# ----------------------------------------------------------------- tutor tools
def test_concept_map_is_cleaned_and_has_dot(indexed, fake_gemini):
    body = indexed.post("/api/v1/concept-map", json={"topic": "linked lists"}).json()
    assert [n["id"] for n in body["nodes"]] == ["list", "node"]  # duplicate id dropped
    assert body["edges"] == [{"from": "list", "to": "node", "label": "has"}]  # edge to unknown node dropped
    assert body["dot"].startswith("digraph G {") and '"list" -> "node"' in body["dot"]


def test_concept_map_non_json_model_output_is_502(indexed, fake_gemini):
    fake_gemini.handler = lambda p, j: "not json at all"
    r = indexed.post("/api/v1/concept-map", json={"topic": "linked lists"})
    assert r.status_code == 502


def test_socratic_returns_questions_and_hints(indexed, fake_gemini):
    body = indexed.post("/api/v1/socratic", json={"question": "why use a heap", "depth": 1}).json()
    assert body["questions"][0] == "What is a node?" and len(body["hints"]) == 3


def test_socratic_offline_fallback_flags_warning(indexed, fake_gemini):
    fake_gemini.fail_with = RuntimeError("no key")
    body = indexed.post("/api/v1/socratic", json={"question": "why use a heap"}).json()
    assert body["questions"] and body["warning"]


def test_synthesis_normalizes_citations(indexed, fake_gemini):
    body = indexed.post("/api/v1/synthesis", json={"topic": "heaps"}).json()
    assert body["synthesis"] == "Unified view."
    assert body["citations"] == [{"doc": "a.pdf", "point": "defines it"}, {"doc": "", "point": "loose citation"}]


def test_adaptive_uses_level_and_context(indexed, fake_gemini):
    body = indexed.post("/api/v1/adaptive", json={"question": "what is a heap", "level": "ELI5"}).json()
    assert body["level"] == "ELI5" and body["answer"] and body["chunks"]
    assert "5 years old" in fake_gemini.calls[-1]
    assert indexed.post("/api/v1/adaptive", json={"question": "what is a heap", "level": "Wizard"}).status_code == 422


def test_math_endpoint(api):
    ok = api.post("/api/v1/math", json={"input": "differentiate sin(x)"}).json()
    assert ok["kind"] == "differentiate" and "cos" in ok["latex"] and ok["steps"]
    bad = api.post("/api/v1/math", json={"input": "__import__('os').system('id')"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "math_error"
    assert api.post("/api/v1/math", json={"input": "x" * 300}).status_code == 422


# ----------------------------------------------------------------- LeetCode
needs_data = pytest.mark.skipif(not (REPO / "data/leetcode/normalized_problems.jsonl").exists(), reason="dataset missing")


@needs_data
def test_leetcode_stats_search_and_problem(api, fake_gemini):
    stats = api.get("/api/v1/leetcode/stats").json()
    assert stats["total"] > 1000 and "Easy" in stats["by_difficulty"]
    res = api.get("/api/v1/leetcode/search", params={"query": "two sum", "top_k": 5, "difficulty": ["Easy"]}).json()
    assert 0 < len(res["problems"]) <= 5 and all(p["difficulty"] == "Easy" for p in res["problems"])
    pid = res["problems"][0]["pid"]
    prob = api.get(f"/api/v1/leetcode/problems/{pid}").json()
    assert prob["pid"] == pid and prob["description"]
    guide = api.post(f"/api/v1/leetcode/problems/{pid}/explain").json()
    assert guide["markdown"] and guide["model"] == "fake-model"
    assert api.get("/api/v1/leetcode/problems/does-not-exist").status_code == 404
    assert api.post("/api/v1/leetcode/problems/does-not-exist/explain").status_code == 404


@needs_data
def test_leetcode_search_validation(api):
    assert api.get("/api/v1/leetcode/search", params={"top_k": 500}).status_code == 422


def test_leetcode_unavailable_dataset_is_503(api, tmp_path):
    (tmp_path / "data" / "leetcode" / "normalized_problems.jsonl").unlink(missing_ok=True)
    api.app_state.leetcode = None
    r = api.get("/api/v1/leetcode/stats")
    assert r.status_code == 503 and r.json()["error"]["code"] == "dataset_unavailable"


# ----------------------------------------------------------------- notes / export
def test_notes_from_history(indexed, fake_gemini):
    body = indexed.post("/api/v1/notes", json={"history": [{"q": "what is a heap", "answer": "a tree"}]}).json()
    assert body["markdown"]
    assert indexed.post("/api/v1/notes", json={"history": []}).status_code == 422


def test_export_formats(api):
    md = "# Notes\n\n- one <script>alert(1)</script>\n"
    r = api.post("/api/v1/export", json={"markdown": md, "format": "md", "filename": "my notes"})
    assert r.headers["content-type"].startswith("text/markdown") and 'filename="my notes.md"' in r.headers["content-disposition"]
    html = api.post("/api/v1/export", json={"markdown": md, "format": "html"})
    assert html.headers["content-type"].startswith("text/html") and "<script" not in html.text.lower()
    pdf = api.post("/api/v1/export", json={"markdown": md, "format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_export_rejects_dangerous_filenames(api):
    for name in ('../x', 'a"b', "a\r\nSet-Cookie: x=1", "a/b"):
        r = api.post("/api/v1/export", json={"markdown": "# hi", "format": "md", "filename": name})
        assert r.status_code == 422, name


# ----------------------------------------------------------------- analytics
def test_analytics_records_questions_and_can_be_cleared(indexed, fake_gemini):
    assert indexed.get("/api/v1/analytics").json()["queries"] == 0
    indexed.post("/api/v1/ask", json={"question": "what is a binary heap", "mode": "technical"})
    indexed.post("/api/v1/ask/stream", json={"question": "heap versus stack please"})
    summary = indexed.get("/api/v1/analytics").json()
    assert summary["queries"] == 2 and summary["streak_days"] == 1
    assert summary["doc_usage"]["heaps.pdf"] == 2
    assert summary["recent"][0]["question"] == "heap versus stack please" and summary["recent"][1]["mode"] == "technical"
    assert summary["avg_latency_ms"] >= 0 and summary["tokens_prompt"] > 0
    assert indexed.delete("/api/v1/analytics").json()["removed"] == 2
    assert indexed.get("/api/v1/analytics").json()["queries"] == 0


def test_failed_questions_are_recorded_as_not_ok(indexed, fake_gemini):
    fake_gemini.fail_with = ValueError("boom")
    indexed.post("/api/v1/ask", json={"question": "what is a binary heap"})
    assert indexed.get("/api/v1/analytics").json()["recent"][0]["ok"] is False
