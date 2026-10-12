import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend import api  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep the engine from scanning local PDFs
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path)
    api._rate_state.clear()
    return TestClient(api.app)


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
