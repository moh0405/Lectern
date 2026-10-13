import importlib
import os
import shutil
import sys
import sqlite3
import types

import pytest

from backend.cloud_sync import S3Sync


class NotFound(Exception):
    response = {"Error": {"Code": "404"}}


class FakeS3:
    """A bucket kept in a local folder, with the three boto3 calls S3Sync uses."""

    def __init__(self, root):
        self.root = root

    def _p(self, bucket, key):
        return self.root / bucket / key

    def head_object(self, Bucket, Key):
        if not self._p(Bucket, Key).exists():
            raise NotFound()

    def upload_file(self, filename, bucket, key):
        dest = self._p(bucket, key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(filename, dest)

    def download_file(self, bucket, key, filename):
        shutil.copyfile(self._p(bucket, key), filename)


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("create table if not exists t (v text)")
    con.executemany("insert into t values (?)", [(r,) for r in rows])
    con.commit()
    con.close()


@pytest.fixture
def cloud(tmp_path):
    return FakeS3(tmp_path / "bucket")


def make_sync(tmp_path, cloud, name="a"):
    base = tmp_path / name
    return S3Sync("b", "pfx", base / "store", base / "study.db", client=cloud)


def seed(sync):
    sync.store_dir.mkdir(parents=True)
    (sync.store_dir / "manifest.json").write_text('{"v": 1}')
    (sync.store_dir / "chunks.jsonl").write_text("{}\n")
    (sync.store_dir / "embeddings.npy").write_bytes(b"npy")
    make_db(sync.study_db, ["card"])


def test_push_then_pull_restores_everything_on_an_empty_disk(tmp_path, cloud):
    first = make_sync(tmp_path, cloud, "a")
    seed(first)
    assert set(first.push()) == {"manifest.json", "chunks.jsonl", "embeddings.npy", "study.db"}

    fresh = make_sync(tmp_path, cloud, "b")  # a replaced container: nothing on disk
    assert set(fresh.pull()) == {"manifest.json", "chunks.jsonl", "embeddings.npy", "study.db"}
    assert (fresh.store_dir / "manifest.json").read_text() == '{"v": 1}'
    assert sqlite3.connect(fresh.study_db).execute("select v from t").fetchall() == [("card",)]


def test_push_only_sends_what_changed(tmp_path, cloud):
    s = make_sync(tmp_path, cloud)
    seed(s)
    s.push()
    assert s.push() == []
    (s.store_dir / "chunks.jsonl").write_text("{}\n{}\n")
    assert s.push() == ["chunks.jsonl"]


def test_a_changed_database_is_sent_again(tmp_path, cloud):
    s = make_sync(tmp_path, cloud)
    seed(s)
    s.push()
    make_db(s.study_db, ["another"])
    assert s.push() == ["study.db"]
    other = make_sync(tmp_path, cloud, "b")
    other.pull()
    assert len(sqlite3.connect(other.study_db).execute("select v from t").fetchall()) == 2


def test_pull_never_overwrites_files_that_exist_locally(tmp_path, cloud):
    first = make_sync(tmp_path, cloud, "a")
    seed(first)
    first.push()
    local = make_sync(tmp_path, cloud, "b")
    local.store_dir.mkdir(parents=True)
    (local.store_dir / "manifest.json").write_text("mine")
    local.pull()
    assert (local.store_dir / "manifest.json").read_text() == "mine"


def test_pull_with_an_empty_bucket_does_nothing(tmp_path, cloud):
    s = make_sync(tmp_path, cloud)
    assert s.pull() == []
    assert not s.store_dir.exists()


def test_a_failed_download_leaves_no_half_file(tmp_path, cloud):
    first = make_sync(tmp_path, cloud, "a")
    seed(first)
    first.push()

    class Flaky(FakeS3):
        def download_file(self, bucket, key, filename):
            open(filename, "w").write("partial")
            raise OSError("connection reset")

    s = make_sync(tmp_path, Flaky(cloud.root), "b")
    with pytest.raises(OSError):
        s.pull()
    assert not any(p.suffix in {".json", ".jsonl", ".npy"} for p in s.store_dir.glob("*"))


def test_other_errors_from_s3_are_not_mistaken_for_missing(tmp_path, cloud):
    class Denied(FakeS3):
        def head_object(self, Bucket, Key):
            e = Exception("denied")
            e.response = {"Error": {"Code": "403"}}
            raise e

    s = make_sync(tmp_path, Denied(cloud.root))
    with pytest.raises(Exception, match="denied"):
        s.pull()


def test_stop_does_a_final_push(tmp_path, cloud):
    s = make_sync(tmp_path, cloud)
    seed(s)
    s.start(interval=3600)
    s.stop()
    assert os.path.exists(cloud.root / "b" / "pfx" / "study.db")


def test_app_pulls_before_loading_the_engine_and_syncs_on_shutdown(tmp_path, cloud, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.cloud_sync as cs
    app_mod = importlib.import_module("backend.api.app")  # the package re-exports `app`, which shadows the module
    from backend.api.settings import settings

    seed_src = make_sync(tmp_path, cloud, "src")
    seed(seed_src)
    seed_src.push()

    monkeypatch.setattr(cs, "_client", lambda: cloud)
    monkeypatch.setattr(settings, "s3_bucket", "b")
    monkeypatch.setattr(settings, "s3_prefix", "pfx")
    monkeypatch.setattr(settings, "store_dir", tmp_path / "restored" / "store")
    monkeypatch.setattr(settings, "study_db", tmp_path / "restored" / "study.db")
    monkeypatch.setattr(app_mod, "make_engine", lambda: type("E", (), {"warm": lambda self: None})())
    with TestClient(app_mod.create_app()):
        assert (tmp_path / "restored" / "store" / "manifest.json").exists()
    assert (tmp_path / "restored" / "study.db").exists()


def test_secret_is_fetched_only_when_asked_for_and_not_already_set(monkeypatch):
    from backend.cloud_sync import load_secret_env

    class SM:
        calls = 0

        def get_secret_value(self, SecretId):
            SM.calls += 1
            return {"SecretString": " the-key\n"}

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_SECRET_ID", raising=False)
    load_secret_env(SM())
    assert "GEMINI_API_KEY" not in os.environ and SM.calls == 0

    monkeypatch.setenv("GEMINI_SECRET_ID", "x/y")
    load_secret_env(SM())
    assert os.environ["GEMINI_API_KEY"] == "the-key" and SM.calls == 1

    load_secret_env(SM())  # already set: no second call
    assert SM.calls == 1
    monkeypatch.delenv("GEMINI_API_KEY")


def test_on_lambda_changes_are_saved_after_each_request_not_on_a_timer(tmp_path, cloud, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.cloud_sync as cs
    from backend.api.settings import settings

    app_mod = importlib.import_module("backend.api.app")
    monkeypatch.setattr(cs, "_client", lambda: cloud)
    monkeypatch.setattr(cs, "ON_LAMBDA", True)
    monkeypatch.setattr(settings, "s3_bucket", "b")
    monkeypatch.setattr(settings, "s3_prefix", "pfx")
    monkeypatch.setattr(settings, "store_dir", tmp_path / "r" / "store")
    monkeypatch.setattr(settings, "study_db", tmp_path / "r" / "study.db")
    monkeypatch.setattr(app_mod, "make_engine", lambda: type("E", (), {"warm": lambda self: None})())
    pushed = []
    monkeypatch.setattr(S3Sync, "push", lambda self: pushed.append(1) or [])
    monkeypatch.setattr(S3Sync, "start", lambda self, interval: pytest.fail("no timer on Lambda"))
    app = app_mod.create_app()
    app.add_api_route("/touch", lambda: {"ok": 1}, methods=["GET", "POST"])
    with TestClient(app) as client:
        client.get("/touch")
        assert pushed == []
        client.post("/touch")
        assert pushed == [1]


def test_cli_pushes_and_pulls(tmp_path, cloud, monkeypatch, capsys):
    import backend.cloud_sync as cs
    from backend.api.settings import settings

    monkeypatch.setattr(cs, "_client", lambda: cloud)
    monkeypatch.setattr(settings, "s3_bucket", "b")
    monkeypatch.setattr(settings, "s3_prefix", "pfx")
    src = make_sync(tmp_path, cloud, "src")
    seed(src)
    monkeypatch.setattr(settings, "store_dir", src.store_dir)
    monkeypatch.setattr(settings, "study_db", src.study_db)
    assert cs.main(["push"]) == 0
    assert "manifest.json" in capsys.readouterr().out
    dst = make_sync(tmp_path, cloud, "dst")
    monkeypatch.setattr(settings, "store_dir", dst.store_dir)
    monkeypatch.setattr(settings, "study_db", dst.study_db)
    assert cs.main(["pull"]) == 0
    assert (dst.store_dir / "manifest.json").exists()


def test_both_secrets_are_loaded_and_the_api_key_turns_on_authentication(monkeypatch, tmp_path, cloud):
    from fastapi.testclient import TestClient

    import backend.cloud_sync as cs
    from backend.api.settings import settings

    app_mod = importlib.import_module("backend.api.app")

    class SM:
        def get_secret_value(self, SecretId):
            return {"SecretString": {"g/key": "gem", "a/key": "s3cret"}[SecretId]}

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda name: SM()))  # boto3 is an optional extra
    monkeypatch.setattr(cs, "_client", lambda: cloud)
    for var in ("GEMINI_API_KEY", "API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_SECRET_ID", "g/key")
    monkeypatch.setenv("API_KEY_SECRET_ID", "a/key")
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "s3_bucket", "b")
    monkeypatch.setattr(settings, "store_dir", tmp_path / "s")
    monkeypatch.setattr(settings, "study_db", tmp_path / "d.db")
    monkeypatch.setattr(app_mod, "make_engine", lambda: type("E", (), {"warm": lambda self: None, "semantic_ready": False, "store": []})())
    with TestClient(app_mod.create_app()) as client:
        assert client.get("/api/v1/stats").status_code == 401
        assert client.get("/api/v1/stats", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/health").status_code == 200  # liveness stays open
        assert os.environ["GEMINI_API_KEY"] == "gem"
    monkeypatch.setattr(settings, "api_key", None)
