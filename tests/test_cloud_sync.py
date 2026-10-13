import importlib
import os
import shutil
import sqlite3

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
