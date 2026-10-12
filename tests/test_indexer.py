from pathlib import Path

import pytest

from backend import indexer
from backend.embeddings import HashingEmbedder
from backend.vector_store import VectorStore

EMB = HashingEmbedder()


@pytest.fixture
def fake_extract(monkeypatch):
    """Replace real PDF parsing: a file's chunks are its lines."""
    calls = []

    def extract(inp):
        calls.append(inp)
        name = Path(inp).name
        if name.startswith("broken"):
            raise RuntimeError("cannot parse")
        lines = Path(inp).read_text().splitlines()
        return [{"text": ln, "doc": name, "page": None, "source_type": "pdf"} for ln in lines]

    monkeypatch.setattr(indexer, "build_chunks_from_input", extract)
    return calls


@pytest.fixture
def dirs(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    return inp, tmp_path / "store"


def run(dirs, **kw):
    inp, store = dirs
    return indexer.index_directory(str(inp), str(store), embedder=EMB, **kw)


def test_first_run_indexes_everything(dirs, fake_extract):
    inp, store = dirs
    (inp / "a.pdf").write_text("linked lists\nhash tables")
    (inp / "b.pdf").write_text("graphs")
    report = run(dirs)
    assert sorted(report.indexed) == ["a.pdf", "b.pdf"]
    assert report.chunks_added == 3 and not report.failed
    loaded = VectorStore.load(store)
    assert len(loaded) == 3 and loaded.embedder_name == EMB.name


def test_second_run_skips_unchanged_files(dirs, fake_extract):
    inp, _ = dirs
    (inp / "a.pdf").write_text("linked lists")
    run(dirs)
    fake_extract.clear()
    report = run(dirs)
    assert report.skipped == ["a.pdf"] and not report.indexed
    assert fake_extract == []  # not even re-extracted


def test_changed_file_is_replaced(dirs, fake_extract):
    inp, store = dirs
    (inp / "a.pdf").write_text("old line one\nold line two")
    run(dirs)
    (inp / "a.pdf").write_text("brand new line")
    report = run(dirs)
    assert report.indexed == ["a.pdf"] and report.chunks_removed == 2 and report.chunks_added == 1
    texts = [c["text"] for c in VectorStore.load(store).chunks]
    assert texts == ["brand new line"]


def test_removed_file_is_pruned(dirs, fake_extract):
    inp, store = dirs
    (inp / "a.pdf").write_text("one")
    (inp / "b.pdf").write_text("two")
    run(dirs)
    (inp / "b.pdf").unlink()
    report = run(dirs)
    assert report.pruned == ["b.pdf"]
    assert VectorStore.load(store).docs() == ["a.pdf"]
    # --no-prune keeps it
    (inp / "c.pdf").write_text("three")
    run(dirs)
    (inp / "c.pdf").unlink()
    assert run(dirs, prune=False).pruned == []
    assert "c.pdf" in VectorStore.load(store).docs()


def test_failure_is_reported_and_keeps_old_data(dirs, fake_extract):
    inp, store = dirs
    (inp / "broken.pdf").write_text("x")
    report = run(dirs)
    assert "broken.pdf" in report.failed and not report.indexed


def test_identical_text_in_two_files_is_embedded_once(dirs, fake_extract):
    inp, store = dirs
    (inp / "a.pdf").write_text("same line")
    (inp / "b.pdf").write_text("same line")
    run(dirs)
    # the same text in different documents is kept per document; repeats within one document are embedded once
    (inp / "c.pdf").write_text("dup\ndup")
    report = run(dirs)
    assert report.chunks_added == 1


def test_rebuild_discards_existing_store(dirs, fake_extract):
    inp, store = dirs
    (inp / "a.pdf").write_text("one")
    run(dirs)
    fake_extract.clear()
    report = run(dirs, rebuild=True)
    assert report.indexed == ["a.pdf"] and fake_extract


def test_urls_are_indexed_once_unless_refreshed(dirs, fake_extract):
    inp, _ = dirs
    url = "https://example.com/post"
    (inp / "sources.txt").write_text(f"# comment\n{url}\n")
    # fake_extract reads files; make URLs return a chunk instead
    import backend.indexer as ix

    ix.build_chunks_from_input = lambda i: [{"text": "article", "doc": "Post", "page": None, "source_type": "web"}]
    first = run(dirs)
    assert first.indexed == [url]
    assert run(dirs).skipped == [url]
    assert run(dirs, refresh_urls=True).indexed == [url]
