# MCP server

`backend/mcp_server.py` exposes the study tools through the [Model Context Protocol](https://modelcontextprotocol.io), so an MCP client (Claude Desktop, Claude Code, Cursor, or your own) can search and read your material, solve math and find practice problems. They are the same tools the in-app [Agent](ARCHITECTURE.md#tool-using-agent-react) uses, from one registry (`backend/tools.py`).

| Tool | What it does |
|---|---|
| `search_documents(query, k=4)` | hybrid search of your indexed material; returns passages with document and page |
| `list_documents()` | the indexed documents and their passage counts |
| `read_page(document, page)` | the full text of one page (the start of the document, for formats without pages) |
| `solve_math(expression)` | exact symbolic math in the sandboxed solver (`integrate x^2 + 3x`, `solve x^2 - 5x + 6 = 0`) |
| `find_leetcode_problem(query, difficulty?)` | search the 1,825-problem bank |
| `save_flashcard(front, back)` | **only with `--writes`**: save a card to your deck |

It also offers one resource, `study://documents`. A failing tool (unknown document, bad arguments) comes back as an MCP tool error with a readable message.

## Setup

Install the extra and index some material first (the web app's Sources page, or `python scripts/preprocess_all_documents.py`):

```bash
pip install -e ".[api,math,mcp,embeddings]"
python -m backend.mcp_server --help
```

The server reads the same environment variables as the API: `STORE_DIR` (default `data/vector_store`), `UPLOAD_DIR`, `STUDY_DB`. Run it from the repository root, or set those to absolute paths.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (use absolute paths):

```json
{
  "mcpServers": {
    "lectern": {
      "command": "/path/to/Lectern/.venv/bin/python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/Lectern"
    }
  }
}
```

### Claude Code

```bash
cd /path/to/Lectern
claude mcp add lectern -- .venv/bin/python -m backend.mcp_server
```

### Cursor

The same `command` / `args` / `cwd` block in `.cursor/mcp.json`.

### Over HTTP

```bash
python -m backend.mcp_server --http --port 8765     # streamable HTTP at http://127.0.0.1:8765/mcp
```

There is **no authentication** on this transport. Keep it on localhost; do not expose it.

## What is tested, and what is not

- Tested with the official MCP Python SDK's client, which spawns the server as a subprocess and speaks the real protocol over stdio (`tests/test_mcp_server.py`): tool discovery, searching and reading a real index, math, LeetCode, tool errors, the resource, and that `save_flashcard` appears only with `--writes`. A test also checks that each tool's input schema matches the registry, so the agent and the server cannot drift apart.
- **Not** tested inside the Claude Desktop, Claude Code or Cursor applications themselves. The config snippets above follow their documented formats but have not been run in them.
- Tool results are text from your documents. A client should treat them as data, not instructions; a document could contain text written to steer a model. The default tools are read-only for that reason.
