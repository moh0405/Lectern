"""The MCP server, tested the way a real client uses it: spawn it as a subprocess and speak MCP over stdio."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from backend.embeddings import HashingEmbedder
from backend.tools import ALL_TOOLS, default_tools
from backend.vector_store import VectorStore

pytest.importorskip("mcp")
from mcp import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
EMB = HashingEmbedder()
CHUNKS = [
    {"text": "A binary heap is a complete binary tree where each parent is ordered before its children.", "doc": "heaps.pdf", "page": 1},
    {"text": "Dijkstra finds shortest paths in graphs with non-negative weights using a priority queue.", "doc": "graphs.pdf", "page": 4},
]


@pytest.fixture
def env(tmp_path):
    store = VectorStore(tmp_path / "store")
    store.set_embedder(EMB.name, EMB.dim)
    chunks = [{**c, "source_type": "pdf"} for c in CHUNKS]
    store.add(chunks, EMB.encode([c["text"] for c in chunks]), "src")
    store.save()
    (tmp_path / "uploads").mkdir()
    (tmp_path / "data" / "leetcode").mkdir(parents=True)
    src = REPO / "data" / "leetcode" / "normalized_problems.jsonl"
    if src.exists():
        (tmp_path / "data" / "leetcode" / "normalized_problems.jsonl").write_bytes(src.read_bytes())
    return {
        **os.environ,
        "STORE_DIR": str(tmp_path / "store"),
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "STUDY_DB": str(tmp_path / "study.db"),
        "ANALYTICS_DB": str(tmp_path / "analytics.db"),
        "EMBEDDER": "hashing",
        "PYTHONPATH": str(REPO),
        "PYTHONUNBUFFERED": "1",
    }


def params(env, *extra):
    return StdioServerParameters(command=sys.executable, args=["-m", "backend.mcp_server", *extra], env=env, cwd=str(env["STORE_DIR"]).rsplit("/store", 1)[0])


def with_client(env, work, *extra):
    async def go():
        async with Client(params(env, *extra)) as client:
            return await work(client)

    return asyncio.run(asyncio.wait_for(go(), timeout=90))


def text_of(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


def test_a_real_client_discovers_the_tools_with_the_registry_descriptions(env):
    async def work(client):
        return await client.list_tools()

    tools = with_client(env, work).tools
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {t.name for t in default_tools()}  # read-only by default: no save_flashcard
    registry = {t.name: t for t in ALL_TOOLS}
    for name, tool in by_name.items():
        assert tool.description == registry[name].description  # one source of truth
        schema, expected = tool.input_schema, registry[name].parameters
        assert set(schema.get("properties", {})) == set(expected["properties"]), name  # the two cannot drift apart
        assert set(schema.get("required", [])) == set(expected["required"]), name


def test_searching_the_users_documents_over_mcp(env):
    async def work(client):
        return await client.call_tool("search_documents", {"query": "binary heap complete tree", "k": 2})

    result = with_client(env, work)
    assert not result.is_error
    payload = (result.structured_content or {})["result"]
    assert payload["passages"][0]["doc"] == "heaps.pdf" and payload["passages"][0]["page"] == 1
    assert "complete binary tree" in text_of(result)


def test_reading_a_page_and_listing_documents(env):
    async def work(client):
        page = await client.call_tool("read_page", {"document": "graphs.pdf", "page": 4})
        docs = await client.call_tool("list_documents", {})
        return page, docs

    page, docs = with_client(env, work)
    assert "Dijkstra" in text_of(page)
    assert {d["doc"] for d in docs.structured_content["result"]["documents"]} == {"heaps.pdf", "graphs.pdf"}


def test_math_and_leetcode_over_mcp(env):
    async def work(client):
        math = await client.call_tool("solve_math", {"expression": "integrate x^2"})
        problems = await client.call_tool("find_leetcode_problem", {"query": "two sum", "difficulty": "Easy"})
        return math, problems

    math, problems = with_client(env, work)
    assert not math.is_error and "x" in text_of(math)
    if (Path(env["STORE_DIR"]).parent / "data" / "leetcode" / "normalized_problems.jsonl").exists():
        assert "Two Sum" in text_of(problems)


def test_a_tool_failure_is_an_mcp_error_the_client_can_show(env):
    async def work(client):
        return await client.call_tool("read_page", {"document": "missing.pdf", "page": 1})

    result = with_client(env, work)
    assert result.is_error and "Unknown document" in text_of(result)


def test_the_documents_resource(env):
    async def work(client):
        listing = await client.list_resources()
        body = await client.read_resource("study://documents")
        return listing, body

    listing, body = with_client(env, work)
    assert [str(r.uri) for r in listing.resources] == ["study://documents"]
    assert "heaps.pdf" in "".join(getattr(c, "text", "") for c in body.contents)


def test_flashcards_are_offered_only_with_the_writes_flag(env):
    async def tool_names(client):
        return sorted(t.name for t in (await client.list_tools()).tools)

    assert "save_flashcard" not in with_client(env, tool_names)
    assert "save_flashcard" in with_client(env, tool_names, "--writes")


def test_the_server_keeps_stdout_clean_for_the_protocol(env):
    # If anything else printed to stdout the client above could not have parsed the stream; this checks a one-shot run too.
    import subprocess

    proc = subprocess.run([sys.executable, "-m", "backend.mcp_server", "--help"], env=env, capture_output=True, text=True, cwd=REPO, timeout=60)
    assert proc.returncode == 0 and "MCP server" in proc.stdout
