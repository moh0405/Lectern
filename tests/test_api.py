import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend import api  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep the engine from scanning local PDFs
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(api, "STORE_DIR", tmp_path / "store")
    (tmp_path / "uploads").mkdir()
    api.app.state.engine = None  # each test gets a fresh engine bound to tmp dirs
    api._rate_state.clear()
    return TestClient(api.app)


def make_pdf(text: str) -> bytes:
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    import io

    buf = io.BytesIO()
    c = reportlab.Canvas(buf)
    y = 800
    for line in text.splitlines():
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_upload_rejects_non_pdf(client):
    res = client.post("/api/upload", files={"files": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["results"][0]["ok"] is False


def test_delete_missing_document_is_404(client):
    assert client.delete("/api/documents/nope.pdf").status_code == 404


def test_query_validates_input(client):
    assert client.post("/api/query", json={"question": "hi"}).status_code == 422


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(api, "RATE_LIMIT_PER_MIN", 2)
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429


def test_lifespan_creates_shared_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(api, "STORE_DIR", tmp_path / "store")
    api.app.state.engine = None
    with TestClient(api.app) as c:
        engine = api.app.state.engine
        assert engine is not None
        c.get("/health")
        assert api.app.state.engine is engine  # requests reuse it


def test_upload_indexes_search_finds_and_delete_removes(client, monkeypatch):
    monkeypatch.setenv("EMBEDDER", "hashing")
    pdf = make_pdf("A binary heap is a complete binary tree used to implement a priority queue.")
    res = client.post("/api/upload", files={"files": ("heaps.pdf", pdf, "application/pdf")})
    body = res.json()
    assert res.status_code == 200 and body["results"][0]["ok"], body
    assert body["results"][0]["chunks_indexed"] >= 1

    assert client.get("/api/documents").json()["documents"] == ["heaps.pdf"]
    assert client.get("/api/stats").json()["chunks"] >= 1
    hits = client.get("/api/search", params={"query": "priority queue heap", "k": 2}).json()["chunks"]
    assert hits and hits[0]["doc"] == "heaps.pdf"

    gone = client.delete("/api/documents/heaps.pdf").json()
    assert gone["ok"] and gone["chunks_removed"] >= 1
    assert client.get("/api/documents").json()["documents"] == []
    assert client.get("/api/search", params={"query": "priority queue heap"}).json()["chunks"] == []


def test_upload_strips_directory_components(client, monkeypatch):
    monkeypatch.setenv("EMBEDDER", "hashing")
    pdf = make_pdf("some text about graphs")
    res = client.post("/api/upload", files={"files": ("../../evil.pdf", pdf, "application/pdf")})
    assert res.json()["results"][0]["filename"] == "evil.pdf"
    assert (api.UPLOAD_DIR / "evil.pdf").exists()
