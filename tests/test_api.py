"""Sources, jobs, documents, search, errors and security of the v1 API."""

import pytest

pytest.importorskip("reportlab")


def wait(api, job_id):
    job = api.app_state.jobs.wait(job_id)
    assert job is not None
    return job


# ----------------------------------------------------------------- health / errors
def test_health(api):
    body = api.get("/health").json()
    assert body["status"] == "ok" and body["chunks"] == 0 and body["version"]


def test_error_shape_for_validation_and_not_found(api):
    r = api.post("/api/v1/ask", json={"question": "hi"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["details"][0]["field"] == "question"
    r = api.get("/api/v1/jobs/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_unhandled_exception_returns_500_error_shape(api, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api import app

    def boom(*a, **k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr("backend.rag_engine.RAGEngine.retrieve_context", boom)
    r = TestClient(app, raise_server_exceptions=False).get("/api/v1/search", params={"query": "heap"})
    assert r.status_code == 500
    assert "secret internals" not in r.text


def test_rate_limit(api, monkeypatch):
    from backend.api.settings import settings

    monkeypatch.setattr(settings, "rate_limit_per_min", 2)
    assert api.get("/api/v1/stats").status_code == 200
    assert api.get("/api/v1/stats").status_code == 200
    r = api.get("/api/v1/stats")
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


def test_api_key_required_when_configured(api, monkeypatch):
    from backend.api.settings import settings

    monkeypatch.setattr(settings, "api_key", "s3cret")
    assert api.get("/api/v1/stats").status_code == 401
    assert api.get("/api/v1/stats", headers={"X-API-Key": "wrong"}).status_code == 401
    assert api.get("/api/v1/stats", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert api.get("/health").status_code == 200  # health stays open


def test_cors_only_allows_configured_origins(api):
    ok = api.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = api.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


# ----------------------------------------------------------------- uploads
def test_upload_index_search_delete_flow(indexed):
    api = indexed
    docs = api.get("/api/v1/documents").json()["documents"]
    assert [d["source_key"] for d in docs] == ["heaps.pdf"] and docs[0]["chunks"] >= 1
    stats = api.get("/api/v1/stats").json()
    assert stats["documents"] == 1 and stats["chunks"] >= 1 and stats["semantic_search"] is True
    hits = api.get("/api/v1/search", params={"query": "priority queue heap", "k": 2}).json()["chunks"]
    assert hits and hits[0]["doc"] == "heaps.pdf" and hits[0]["score"] > 0

    gone = api.delete("/api/v1/sources", params={"key": "heaps.pdf"}).json()
    assert gone["ok"] and gone["chunks_removed"] >= 1
    assert api.get("/api/v1/documents").json()["documents"] == []
    assert api.get("/api/v1/search", params={"query": "priority queue heap"}).json()["chunks"] == []
    assert api.delete("/api/v1/sources", params={"key": "heaps.pdf"}).status_code == 404


def test_job_reports_progress_and_result(api, pdf_bytes):
    pdf = pdf_bytes("graphs have nodes and edges")  # generated once: ReportLab embeds a timestamp
    r = api.post("/api/v1/sources/files", files={"files": ("a.pdf", pdf, "application/pdf")})
    job = wait(api, r.json()["job_id"])
    assert job["status"] == "done" and job["result"]["indexed"] == ["a.pdf"] and job["result"]["chunks_added"] >= 1
    assert any("embedding" in m or "extracting" in m for m in job["progress"])
    # same file again: unchanged, skipped
    r2 = api.post("/api/v1/sources/files", files={"files": ("a.pdf", pdf, "application/pdf")})
    assert wait(api, r2.json()["job_id"])["result"]["skipped"] == ["a.pdf"]
    assert api.get(f"/api/v1/jobs/{r.json()['job_id']}").json()["status"] == "done"


def test_upload_validation(api, pdf_bytes):
    files = [
        ("files", ("notes.txt", b"hello", "text/plain")),
        ("files", ("fake.pdf", b"this is not a pdf", "application/pdf")),
        ("files", ("empty.pdf", b"", "application/pdf")),
    ]
    body = api.post("/api/v1/sources/files", files=files).json()
    assert body["job_id"] is None
    assert [f["ok"] for f in body["files"]] == [False, False, False]
    assert "Unsupported" in body["files"][0]["error"] and "PDF" in body["files"][1]["error"]


def test_upload_size_and_count_limits(api, pdf_bytes, monkeypatch):
    from backend.api.settings import settings

    monkeypatch.setattr(settings, "max_upload_mb", 0)  # everything is "too large"
    body = api.post("/api/v1/sources/files", files={"files": ("a.pdf", pdf_bytes("x"), "application/pdf")}).json()
    assert body["files"][0]["ok"] is False and "exceeds" in body["files"][0]["error"]
    monkeypatch.setattr(settings, "max_files_per_request", 1)
    two = [("files", ("a.pdf", b"%PDF-1", "application/pdf")), ("files", ("b.pdf", b"%PDF-1", "application/pdf"))]
    r = api.post("/api/v1/sources/files", files=two)
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_many_files"


@pytest.mark.parametrize("evil", ["../../evil.pdf", "..\\..\\evil.pdf", "/etc/cron.d/evil.pdf", ".hidden.pdf", "a/b/c.pdf"])
def test_upload_filenames_cannot_escape_the_upload_dir(api, pdf_bytes, evil):
    from backend.api.settings import settings

    body = api.post("/api/v1/sources/files", files={"files": (evil, pdf_bytes("some text"), "application/pdf")}).json()
    name = body["files"][0]["filename"]
    assert "/" not in name and "\\" not in name and not name.startswith(".")
    written = list(settings.upload_dir.iterdir())
    assert written and all(p.parent == settings.upload_dir for p in written)
    assert not list(settings.upload_dir.parent.glob("evil*"))


def test_delete_cannot_remove_files_outside_upload_dir(api, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    r = api.delete("/api/v1/sources", params={"key": "../victim.txt"})
    assert r.status_code == 404 and victim.exists()


def test_add_urls_validates_and_persists(api, monkeypatch):
    from backend.api.settings import settings

    bad = api.post("/api/v1/sources/urls", json={"urls": ["ftp://x.example/a", "not a url"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_url"
    monkeypatch.setattr("backend.indexer.build_chunks_from_input",
                        lambda u: [{"text": "article text", "doc": "Post", "page": None, "source_type": "web"}])
    r = api.post("/api/v1/sources/urls", json={"urls": ["https://example.com/post", "https://example.com/post"]})
    assert r.status_code == 202 and r.json()["urls"] == ["https://example.com/post"]
    job = wait(api, r.json()["job_id"])
    assert job["status"] == "done", job
    assert (settings.upload_dir / "sources.txt").read_text().split() == ["https://example.com/post"]
    docs = api.get("/api/v1/documents").json()["documents"]
    assert docs[0]["source_key"] == "https://example.com/post"
    assert api.delete("/api/v1/sources", params={"key": "https://example.com/post"}).json()["chunks_removed"] == 1
    assert (settings.upload_dir / "sources.txt").read_text().strip() == ""


def test_lifespan_creates_shared_engine_and_jobs(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api import app
    from backend.api.settings import settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "store_dir", tmp_path / "store")
    app.state.engine = None
    with TestClient(app) as c:
        engine = app.state.engine
        assert engine is not None and app.state.jobs is not None
        c.get("/health")
        assert app.state.engine is engine


def test_openapi_documents_errors_and_streaming(api):
    spec = api.get("/openapi.json").json()
    assert "/api/v1/ask/stream" in spec["paths"]
    schemas = spec["components"]["schemas"]
    for name in ("ErrorResponse", "SseMeta", "SseToken", "SseDone", "SseError", "AskRequest"):
        assert name in schemas
    assert "text/event-stream" in spec["paths"]["/api/v1/ask/stream"]["post"]["responses"]["200"]["content"]
