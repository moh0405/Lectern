"""Adding, listing and removing study material, plus the background jobs that index it."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

from ...rag_engine import RAGEngine
from ..deps import common_dependencies, get_engine, get_jobs
from ..errors import ERROR_RESPONSES, ApiError
from ..jobs import JobManager
from ..schemas import (
    DeleteResult,
    DocumentInfo,
    DocumentsResponse,
    FileResult,
    Job,
    SourcesAccepted,
    Stats,
    UrlsRequest,
)
from ..settings import AUDIO_EXTS, PDF_EXTS, settings

router = APIRouter(prefix="/api/v1", tags=["sources"], dependencies=common_dependencies, responses=ERROR_RESPONSES)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ ()\-]")


def safe_filename(name: str) -> str:
    """Last path component only, restricted characters, never hidden or empty."""
    base = _SAFE_NAME.sub("_", Path((name or "").replace("\\", "/")).name).strip(" .")
    return base or "upload"


def _sources_file() -> Path:
    return settings.upload_dir / "sources.txt"


def _read_urls() -> List[str]:
    f = _sources_file()
    return [ln.strip() for ln in f.read_text().splitlines() if ln.strip()] if f.exists() else []


def _write_urls(urls: List[str]) -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _sources_file().write_text("\n".join(urls) + ("\n" if urls else ""))


def _report_to_dict(report) -> Dict:
    return {
        "indexed": report.indexed,
        "skipped": report.skipped,
        "pruned": report.pruned,
        "failed": report.failed,
        "chunks_added": report.chunks_added,
        "chunks_removed": report.chunks_removed,
    }


def _index_job(engine: RAGEngine, inputs: List[str], refresh_urls: bool = False):
    def run(progress):
        return _report_to_dict(engine.add_sources(inputs, refresh_urls=refresh_urls, progress=progress))

    return run


@router.post("/sources/files", response_model=SourcesAccepted, status_code=202,
             summary="Upload PDFs or audio and index them in the background")
async def upload_files(
    files: List[UploadFile] = File(..., description="PDF (.pdf) or audio/video (.mp3 .mp4 .wav .m4a) files"),
    engine: RAGEngine = Depends(get_engine),
    jobs: JobManager = Depends(get_jobs),
):
    if len(files) > settings.max_files_per_request:
        raise ApiError(413, f"At most {settings.max_files_per_request} files per request", code="too_many_files")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    results: List[FileResult] = []
    saved: List[str] = []
    for f in files:
        name = safe_filename(f.filename or "")
        ext = Path(name).suffix.lower()
        if ext not in PDF_EXTS | AUDIO_EXTS:
            results.append(FileResult(filename=name, ok=False, error="Unsupported type. Allowed: .pdf .mp3 .mp4 .wav .m4a"))
            continue
        data = await f.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            results.append(FileResult(filename=name, ok=False, error=f"File exceeds {settings.max_upload_mb} MB"))
            continue
        if not data:
            results.append(FileResult(filename=name, ok=False, error="File is empty"))
            continue
        if ext in PDF_EXTS and not data.lstrip()[:5] == b"%PDF-":
            results.append(FileResult(filename=name, size_bytes=len(data), ok=False, error="Not a valid PDF file"))
            continue
        dest = settings.upload_dir / name
        dest.write_bytes(data)
        saved.append(str(dest))
        results.append(FileResult(filename=name, size_bytes=len(data), ok=True))
    job_id = jobs.submit("index_files", _index_job(engine, saved)) if saved else None
    return SourcesAccepted(job_id=job_id, files=results, urls=[])


@router.post("/sources/urls", response_model=SourcesAccepted, status_code=202,
             summary="Add YouTube, GitHub or web URLs and index them in the background")
def add_urls(
    req: UrlsRequest,
    engine: RAGEngine = Depends(get_engine),
    jobs: JobManager = Depends(get_jobs),
):
    clean: List[str] = []
    for u in req.urls:
        u = u.strip()
        p = urlparse(u)
        if p.scheme not in {"http", "https"} or not p.hostname:
            raise ApiError(422, f"Not a valid http(s) URL: {u[:120]}", code="invalid_url")
        if u not in clean:
            clean.append(u)
    known = _read_urls()
    _write_urls(known + [u for u in clean if u not in known])
    job_id = jobs.submit("index_urls", _index_job(engine, clean))
    return SourcesAccepted(job_id=job_id, files=[], urls=clean)


@router.get("/jobs/{job_id}", response_model=Job, summary="Status and progress of a background job")
def get_job(job_id: str, jobs: JobManager = Depends(get_jobs)):
    job = jobs.get(job_id)
    if job is None:
        raise ApiError(404, "Job not found (jobs are kept in memory and are lost on restart)")
    return job


@router.get("/documents", response_model=DocumentsResponse, summary="Indexed sources and how many chunks each has")
def list_documents(engine: RAGEngine = Depends(get_engine)):
    by_source: Dict[str, DocumentInfo] = {}
    for c in engine.store.chunks:
        key = c.get("source_key") or c.get("doc") or ""
        info = by_source.setdefault(key, DocumentInfo(source_key=key, docs=[], chunks=0, source_type=c.get("source_type")))
        info.chunks += 1
        if c.get("doc") and c["doc"] not in info.docs:
            info.docs.append(c["doc"])
    return DocumentsResponse(documents=sorted(by_source.values(), key=lambda d: d.source_key.lower()))


@router.get("/stats", response_model=Stats, summary="Corpus statistics")
def stats(engine: RAGEngine = Depends(get_engine)):
    items = engine._docstore_iter()
    pages = [i.get("page") for i in items if i.get("page") is not None]
    return Stats(
        documents=len({i.get("doc") for i in items if i.get("doc")}),
        chunks=len(items),
        min_page=min(pages) if pages else None,
        max_page=max(pages) if pages else None,
        embedder=engine.store.embedder_name,
        semantic_search=engine.semantic_ready,
    )


@router.delete("/sources", response_model=DeleteResult, summary="Remove a source and its chunks from the index")
async def delete_source(
    key: str = Query(..., min_length=1, max_length=2000, description="source_key from GET /documents"),
    engine: RAGEngine = Depends(get_engine),
):
    is_url = key.startswith(("http://", "https://"))
    in_index = key in engine.store.sources
    target = None if is_url else (settings.upload_dir / safe_filename(key))
    exists_on_disk = target is not None and target.is_file()
    known_url = is_url and key in _read_urls()
    if not (in_index or exists_on_disk or known_url):
        raise ApiError(404, "Source not found")
    if exists_on_disk:
        target.unlink()
    if known_url:
        _write_urls([u for u in _read_urls() if u != key])
    removed = await run_in_threadpool(engine.remove_source, key)
    return DeleteResult(ok=True, deleted=key, chunks_removed=removed)
