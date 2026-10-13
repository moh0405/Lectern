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
    assert body["cached"] is False and body["uncited"] is False and body["unverified_citations"] == 0
    assert body["citations"] == [{"label": "heaps.pdf (page 1)", "doc": "heaps.pdf", "page": 1, "status": "ok"}]


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
    done = events[-1][1]
    assert done["model"] == "fake-model" and done["cached"] is False and done["unverified_citations"] == 0
    assert done["citations"][0]["status"] == "ok" and done["uncited"] is False


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


# ----------------------------------------------------------------- visualization
def test_projection_of_an_empty_index(api):
    body = api.get("/api/v1/embeddings/projection").json()
    assert body["points"] == [] and body["total_chunks"] == 0 and body["semantic"] is False


def test_projection_returns_points_with_variance_and_honest_semantic_flag(indexed):
    body = indexed.get("/api/v1/embeddings/projection", params={"limit": 50}).json()
    assert body["method"] == "pca" and body["total_chunks"] >= 1
    p = body["points"][0]
    assert {"x", "y", "z", "doc", "page", "text", "index"} <= set(p) and p["doc"] == "heaps.pdf"
    assert len(body["explained_variance"]) == 3
    assert body["embedder"].startswith("hashing") and body["semantic"] is False  # tests use the hashing embedder


def test_projection_limit_is_validated(api):
    assert api.get("/api/v1/embeddings/projection", params={"limit": 5}).status_code == 422
    assert api.get("/api/v1/embeddings/projection", params={"limit": 5000}).status_code == 422


# ----------------------------------------------------------------- models
def test_models_lists_what_the_key_can_use(api, fake_gemini):
    body = api.get("/api/v1/models").json()
    assert body["models"][0] == "gemini-3.8-flash" and body["default"] == "fake-model"


def test_models_without_a_key_is_503(api, fake_gemini):
    fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set")
    r = api.get("/api/v1/models")
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"


# ----------------------------------------------------------------- citation checking
def test_invented_and_wrong_page_citations_are_flagged(indexed, fake_gemini):
    fake_gemini.handler = lambda p, j: "Heaps are trees [heaps.pdf (page 1)], [Operating Systems.pdf (page 3)] and [heaps.pdf (page 40)]."
    body = indexed.post("/api/v1/ask", json={"question": "what is a binary heap"}).json()
    by_label = {c["label"]: c["status"] for c in body["citations"]}
    assert by_label == {
        "heaps.pdf (page 1)": "ok",
        "Operating Systems.pdf (page 3)": "unknown_source",
        "heaps.pdf (page 40)": "page_not_retrieved",
    }
    assert body["unverified_citations"] == 2


def test_a_long_answer_that_cites_nothing_is_marked_uncited(indexed, fake_gemini):
    fake_gemini.handler = lambda p, j: "A heap is a tree with an ordering property. " * 10
    assert indexed.post("/api/v1/ask", json={"question": "what is a binary heap"}).json()["uncited"] is True


def test_stream_reports_flagged_citations_in_the_done_event(indexed, fake_gemini):
    fake_gemini.handler = lambda p, j: "See [Invented.pdf (page 2)] for details."
    done = parse_sse(indexed.post("/api/v1/ask/stream", json={"question": "what is a binary heap"}).text)[-1]
    assert done[0] == "done" and done[1]["unverified_citations"] == 1
    assert done[1]["citations"][0]["status"] == "unknown_source"


# ----------------------------------------------------------------- answer cache
def test_repeating_a_question_reuses_the_answer_without_calling_the_model(indexed, fake_gemini):
    q = {"question": "what is a binary heap"}
    first = indexed.post("/api/v1/ask", json=q).json()
    second = indexed.post("/api/v1/ask", json={"question": "  What is a  binary HEAP "}).json()  # same question, different spacing
    assert first["cached"] is False and second["cached"] is True
    assert second["answer"] == first["answer"] and second["citations"] == first["citations"]
    assert len(fake_gemini.calls) == 1


def test_no_cache_asks_again(indexed, fake_gemini):
    q = {"question": "what is a binary heap"}
    indexed.post("/api/v1/ask", json=q)
    fresh = indexed.post("/api/v1/ask", json={**q, "no_cache": True}).json()
    assert fresh["cached"] is False and len(fake_gemini.calls) == 2


@pytest.mark.parametrize("change", [{"mode": "eli5"}, {"k": 2}, {"temperature": 0.9}, {"model": "gemini-3.7-flash"}])
def test_anything_that_can_change_the_answer_is_part_of_the_cache_key(indexed, fake_gemini, change):
    q = {"question": "what is a binary heap"}
    indexed.post("/api/v1/ask", json=q)
    assert indexed.post("/api/v1/ask", json={**q, **change}).json()["cached"] is False


def test_changing_the_index_invalidates_cached_answers(indexed, fake_gemini, pdf_bytes):
    q = {"question": "what is a binary heap"}
    indexed.post("/api/v1/ask", json=q)
    assert indexed.post("/api/v1/ask", json=q).json()["cached"] is True
    res = indexed.post("/api/v1/sources/files", files={"files": ("graphs.pdf", pdf_bytes("a graph has vertices and edges joined together"), "application/pdf")})
    indexed.app_state.jobs.wait(res.json()["job_id"])
    assert indexed.post("/api/v1/ask", json=q).json()["cached"] is False  # the material changed, so ask again


def test_failures_and_empty_answers_are_never_cached(indexed, fake_gemini):
    q = {"question": "what is a binary heap"}
    fake_gemini.fail_with = ValueError("boom")
    assert indexed.post("/api/v1/ask", json=q).status_code == 502
    fake_gemini.fail_with = None
    assert indexed.post("/api/v1/ask", json=q).json()["cached"] is False  # the failure was not remembered


def test_streaming_replays_a_cached_answer_and_a_stream_fills_the_cache(indexed, fake_gemini):
    q = {"question": "what is a binary heap"}
    live = parse_sse(indexed.post("/api/v1/ask/stream", json=q).text)
    replay = parse_sse(indexed.post("/api/v1/ask/stream", json=q).text)
    text = lambda evs: "".join(d["text"] for e, d in evs if e == "token")  # noqa: E731
    assert live[-1][1]["cached"] is False and replay[-1][1]["cached"] is True
    assert text(replay) == text(live)
    assert [e for e, _ in replay][0] == "meta" and replay[-1][0] == "done"
    assert len(fake_gemini.calls) == 1
    # and a non-streaming request reuses what the stream produced
    assert indexed.post("/api/v1/ask", json=q).json()["cached"] is True
