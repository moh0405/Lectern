from backend.document_processor import _detect_source, chunk_text
from backend.sources.base_source import BaseSource


class _Dummy(BaseSource):
    def validate(self, input_value):
        return True

    def extract(self, input_value):
        return []

    def get_metadata(self):
        return {}


def test_chunk_text_overlaps_and_covers_text():
    text = "".join(chr(65 + i % 26) for i in range(2000))
    chunks = chunk_text(text, chunk_size=800, overlap=160)
    assert len(chunks) == 3
    assert all(len(c) <= 800 for c in chunks)
    # consecutive chunks share the overlap region
    assert chunks[0][-160:] == chunks[1][:160]
    assert chunks[-1].endswith(text[-10:])


def test_chunk_text_empty_and_whitespace():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_base_source_chunk_text_matches_pdf_chunker():
    text = "word " * 600
    assert _Dummy().chunk_text(text) == chunk_text(text)


def test_detect_source_urls_and_files(tmp_path):
    assert _detect_source("https://www.youtube.com/watch?v=abcdefghijk") == "youtube"
    assert _detect_source("https://youtu.be/abcdefghijk") == "youtube"
    assert _detect_source("https://github.com/owner/repo") == "github"
    assert _detect_source("https://example.com/post") == "web"
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert _detect_source(str(pdf)) == "pdf"
    assert _detect_source("not a source") is None
