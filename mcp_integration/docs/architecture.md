# Architecture

Two processes, one sandboxed data directory:

```
matching_agent.py (LangGraph agent + REPL, runs on host via `uv run`)
        |
        |  langchain.mcp.MCPAdapter -- one session held open for the whole
        |  REPL, MCP over Streamable HTTP, unauthenticated, localhost only
        v
filesystem_mcp_server.py (FastMCP, runs in Docker)
        |
        |  sandboxed filesystem operations (fs_core.py)
        v
sample_data/resumes/ (bind-mounted into the container)
```

- **`matching_agent.py`** -- a `create_agent`-built LangGraph agent with an
  `InMemorySaver` checkpointer, run through a Rich-based terminal REPL. Holds
  no direct filesystem access; every tool it can call comes from
  `MCPAdapter(settings.MCP_SERVER_URL).list_tools()` at startup.
- **`filesystem_mcp_server.py`** -- a `FastMCP` server exposing 8 tools
  (`list_files`, `read_file`, `search_in_file`, `write_file`, `batch_process`,
  `start_watch`, `poll_watch`, `stop_watch`) plus a `/health` route, over
  Streamable HTTP. Runs in Docker; the container publishes `MCP_PORT` to the
  host. `list_files` is the one tool whose return shape differs from the
  rest: it returns a bare `list[dict]` (file-metadata dicts on success, or a
  list containing one `{"error": {...}}` entry on failure) rather than the
  `{"success": bool, ..., "error": ...}` dict shape every other tool uses.
- **`fs_core.py`** -- pure, undecorated filesystem and watch-state logic
  (path sandboxing, text extraction, background watch threads). Has no
  dependency on MCP or LangChain, so it's testable directly.
- **`config.py`** -- a plain `Settings` class reading `.env`/environment
  variables, shared by both processes (though each process only reads the
  settings relevant to it: the server binds `MCP_HOST`/`MCP_PORT` and enforces
  `ROOT_DIR` everywhere; `ALLOWED_EXTENSIONS`/`MAX_FILE_SIZE_BYTES` are
  enforced only by `batch_process` -- the single-file tools (`list_files`/
  `read_file`/`search_in_file`/`write_file`) are constrained only by
  `extract_text`'s hard-coded `.txt`/`.docx`/`.pdf` support and have no size
  cap; the agent only reads `MCP_SERVER_URL` and `OPENROUTER_API_KEY`).
- **`sample_data/resumes/`** -- copied from `llm_file_assistant/root_dir`,
  bind-mounted into the container so agent-written files are visible on the
  host.
