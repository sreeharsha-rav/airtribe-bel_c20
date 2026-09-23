# MCP Integration Project — Design Spec

Status: draft, awaiting review
Owner: sreeharsha

## 1. Purpose

Move the filesystem tooling used in `llm_file_assistant` (and mirrored in
`agentic_profile_match`) out of a directly-imported LangChain tool module and
behind a standalone MCP server, then refactor the chat agent to discover and
call those tools exclusively through an MCP client. This is a from-scratch
project living in `mcp_integration/`; it reuses `llm_file_assistant`'s sample
data, tool logic, REPL, and agent shape as its starting point — it does not
reuse or depend on `agentic_profile_match`'s RAG/multi-round-screening
pipeline, which is out of scope here.

Two required deliverable files anchor the project: `filesystem_mcp_server.py`
(Part A, MCP server) and `matching_agent.py` (Part B, refactored agent).

## 2. Architecture

```
matching_agent.py (LangGraph agent + REPL, runs on host via `uv run`)
        |
        |  langchain.mcp.MCPAdapter — one session held open for the whole
        |  REPL, MCP over Streamable HTTP, unauthenticated, localhost only
        v
filesystem_mcp_server.py (FastMCP, runs in Docker)
        |
        |  sandboxed filesystem operations
        v
sample_data/resumes/ (bind-mounted into the container)
```

Two processes. The server is dockerized; the agent is not (it's an
interactive REPL — awkward to run well inside Compose). The agent connects to
`http://localhost:<MCP_PORT>/mcp`, the port Docker Compose publishes.

## 3. Repository layout

```
mcp_integration/
├── filesystem_mcp_server.py   # Part A — FastMCP server (entrypoint)
├── matching_agent.py          # Part B — LangGraph agent + REPL (entrypoint)
├── fs_core.py                 # pure filesystem logic, no MCP/LangChain decoration
├── config.py                  # plain Settings class, os.getenv-based (repo convention)
├── utils.py                   # CustomLogger, copied from llm_file_assistant
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── sample_data/
│   └── resumes/                # copied from llm_file_assistant/root_dir
├── tests/
│   ├── test_mcp_server.py
│   ├── test_batch_process.py
│   ├── test_watch_directory.py
│   └── test_matching_agent_mcp.py
├── docs/
│   ├── spec.md                 # this file
│   ├── architecture.md
│   ├── workflow-diagram.md
│   └── demo-script.md
├── pyproject.toml
├── README.md
├── sample.env / .env
└── .gitignore
```

`main.py`'s current placeholder content is removed; `matching_agent.py` is
the runnable entrypoint the suggested structure and grading checklist expect.

## 4. Config management

Follows the same pattern already used by `llm_file_assistant/config.py` and
`agentic_profile_match/config.py` (and the FastMCP reference repo's
`app/config.py`): a plain `Settings` class that calls `load_dotenv()` and
reads `os.getenv(...)`, raising `ValueError` on missing required values. No
new dependency (`pydantic-settings` was considered and dropped — it would be
the only project in the repo using it).

Settings, sourced from `.env` (local dev) or `docker-compose.yml`'s
`environment:` override block (container):

| Setting | Purpose | Example |
|---|---|---|
| `ROOT_DIR` | sandbox root for all filesystem tools | `sample_data/resumes` |
| `ALLOWED_EXTENSIONS` | extensions the tools will read/process | `.txt,.docx,.pdf` |
| `MAX_FILE_SIZE_BYTES` | files larger than this are skipped/rejected | `10485760` |
| `BATCH_MAX_CONCURRENCY` | concurrent file ops inside `batch_process` | `4` |
| `WATCH_POLL_INTERVAL_SECONDS` | default poll interval for `start_watch` | `5` |
| `LOG_LEVEL` | `CustomLogger` verbosity | `INFO` |
| `MCP_HOST` | bind host — `127.0.0.1` locally, `0.0.0.0` in the container | `0.0.0.0` |
| `MCP_PORT` | bind/publish port | `8000` |
| `OPENROUTER_API_KEY` | chat model provider key (agent side only) | — |

`MCP_HOST` is the one setting that differs between local dev and Docker: kept
as `127.0.0.1` in `.env`, overridden to `0.0.0.0` in `docker-compose.yml`'s
`environment:` block — same technique the reference repo uses for its DB URL.

## 5. `filesystem_mcp_server.py` — migrated tools

`fs_core.py` carries over `_resolve_within_root`, `_extract_text` (txt/docx/pdf),
and `_file_metadata` from `llm_file_assistant/fs_tools.py`, undecorated. The
server wraps each as an `@mcp.tool`, keeping the existing structured
`{success, ..., error}` return shape:

- `list_files(directory=".", extension=None)`
- `read_file(filepath)`
- `search_in_file(filepath, keyword)`
- `write_file(filepath, content)` — create-only, refuses to overwrite

Each tool's docstring/description and pydantic `args_schema`-equivalent
(parameter `Annotated[..., Field(description=...)]`) is what makes it
discoverable — FastMCP generates the MCP `tools/list` response from these
automatically, satisfying the resource-discovery requirement with no extra
code.

A `@mcp.custom_route("/health", methods=["GET"])` returns `{"status": "ok"}`
for the Docker healthcheck. No FastAPI wrapper is used — unlike the reference
`todos` project (which needed FastAPI to also mount a REST API + JWT auth),
this server has no auth and no other API surface, so `mcp.run(transport="http",
host=settings.MCP_HOST, port=settings.MCP_PORT)` runs it directly.

## 6. New capability: `batch_process`

Input: either an explicit `files: list[str]` or a `directory` (+ optional
`extension` filter, `recursive` flag) that gets expanded the same way
`list_files` would. There is no matching/ranking pipeline in this project's
scope (that belongs to `agentic_profile_match`), so "processing" a file here
means reading and extracting its text/metadata — the same operation
`read_file` performs, run across many files with aggregate bookkeeping.

Per file, one of:
- **skipped** — filtered out before an attempt (wrong extension, over
  `MAX_FILE_SIZE_BYTES`)
- **success** — extracted; `result` holds `{content, metadata}`
- **error** — extraction raised (corrupted file, unreadable), with a
  structured `{code, message}`

One file's failure never aborts the batch. Concurrency is bounded by
`BATCH_MAX_CONCURRENCY`. In the aggregate counts, `processed` counts only
per-file `status: "success"` entries (not `error` or `skipped`) —
`processed + failed + skipped == total_files` always. Response shape:

```json
{
  "total_files": 10,
  "processed": 8,
  "failed": 1,
  "skipped": 1,
  "results": [
    {"path": "engineering/alice.pdf", "status": "success", "result": {}},
    {"path": "engineering/corrupt.pdf", "status": "error",
     "error": {"code": "FILE_PROCESSING_ERROR", "message": "Unable to read PDF"}}
  ]
}
```

## 7. New capability: `watch_directory`

MCP tools are request/response, not a push channel, so this is a
session-based trio rather than one long-lived call:

- **`start_watch(directory_path, recursive=False, allowed_extensions=None,
  poll_interval_seconds=5) -> {watch_id}`** — validates the path exists and
  is a readable directory up front (returns a structured error immediately
  otherwise); snapshots existing files; spawns a background polling thread.
- **`poll_watch(watch_id) -> {events: [...], active: bool}`** — drains
  whatever new-file events have accumulated since the last poll
  (non-blocking, returns immediately). Each event: `{path, filename,
  detected_at, ready}` — `ready` becomes `true` once a file's size is stable
  across two consecutive polls (a naive but sufficient guard against reading
  a file mid-write).
- **`stop_watch(watch_id) -> {stopped: bool}`** — signals the thread to exit
  and joins it.

A runtime failure inside the polling loop (e.g. the directory is deleted
mid-watch) is caught, logged, and surfaced as a terminal `{type: "error",
message}` event on the next `poll_watch` rather than crashing the thread
silently or taking down the server process.

## 8. Error handling

Two layers, matching how MCP itself separates protocol errors from tool
results:

- **Protocol-level** (unknown tool/method, malformed params against a tool's
  schema) — handled natively by FastMCP as JSON-RPC errors (`-32601` method
  not found, `-32602` invalid params). No custom code needed.
- **App-level** (bad path, permission denied, unsupported format, corrupted
  file, invalid watch directory) — every tool keeps returning its existing
  structured `{success: false, error: {code, message}}` shape rather than
  raising, so the calling agent can branch on it. Error codes: `NOT_FOUND`,
  `PATH_ESCAPES_ROOT`, `UNSUPPORTED_FORMAT`, `FILE_PROCESSING_ERROR`,
  `PERMISSION_DENIED`, `VALIDATION_ERROR`, `WATCH_ERROR`.

This covers every row in the assignment's error-scenario table (§ Error
Handling of the requirements doc).

## 9. `matching_agent.py` — MCP client integration

```python
from langchain.mcp import MCPAdapter

async def main():
    async with MCPAdapter(config.MCP_SERVER_URL) as adapter:
        tools = await adapter.list_tools()
        agent = build_assistant_agent(tools)
        await run_chat_loop(agent, build_thread_config(), console)
```

`MCP_SERVER_URL` is built from `MCP_HOST`/`MCP_PORT` as
`http://localhost:{MCP_PORT}/mcp` (the agent always talks to the
host-published Docker port, regardless of what `MCP_HOST` is bound to
inside the container). The adapter session stays open for the entire REPL,
not reopened per turn.

No `fs_tools`/`fs_core` import exists in this file's primary path — every
filesystem capability comes from `adapter.list_tools()`.

`run_chat_loop` and `stream_assistant_reply` carry over from
`llm_file_assistant/main.py` essentially unchanged in *shape* (same REPL
commands: `clear`/`load`/`reasoning`/`exit`; same rich `Live` panels for
reasoning/assistant text/tool calls), but become `async def`, using
`await agent.ainvoke(...)` or async iteration over
`agent.stream_events(..., version="v3")` so they run on the same event loop
as the open `MCPAdapter` session. **Open question to resolve first, before
building the rest of this phase on top of it**: confirm `stream_events`'s
typed-projection iterators support `async for` cleanly when the agent's
tool-calling loop is routing calls through an async MCP session — the
existing sync code is a reference for the panel-rendering logic, not
something to port unchanged.

Because MCP tools surface through the normal LangChain tool-calling loop,
the existing `Tool call: {name}({args})` panel and the `ToolMessage`
rendering already show every MCP round-trip live — no bespoke MCP-event
handling is required for basic visibility. *Investigate-only stretch*: have
`batch_process`/`poll_watch` call `ctx.info(...)` server-side for progress
messages (as the reference `todos` repo's `mcp.py` does), and check whether
LangChain's stream surfaces those; adopt only if it does cleanly and cheaply.

## 10. Docker packaging

Adapted from `sreeharsha-rav/python-apps/learn-fastmcp/todos`:

**Dockerfile** — `ghcr.io/astral-sh/uv:python3.12-trixie-slim` base (bumped
from the reference's 3.11 to match this repo's `>=3.12` requirement); layered
`uv sync --locked --no-install-project --no-dev` (deps only, cached unless
the lockfile changes) followed by a full `uv sync --locked --no-dev` after
copying source; venv put on `PATH`; `CMD` runs
`python filesystem_mcp_server.py`.

**docker-compose.yml** — one service (`filesystem-mcp-server`): `build: .`,
publishes `MCP_PORT:MCP_PORT`, `env_file: .env`, an `environment:` block
overriding `MCP_HOST=0.0.0.0`, a bind mount `./sample_data:/app/sample_data`
(so agent-written files are visible on the host and persist across
rebuilds — deliberately a bind mount, not a named volume, since the point is
host visibility for grading/demo, not just persistence), a `healthcheck`
hitting `/health`, `restart: unless-stopped`.

**.dockerignore** — `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `.git/`,
`tests/`.

Running the server: `docker compose up --build` (primary/documented path) or
`uv run python filesystem_mcp_server.py` (local dev/debugging, reads
`MCP_HOST=127.0.0.1` from `.env`). Running the agent (always host-side):
`uv run python matching_agent.py`.

## 11. Testing

`pytest` (new dev dependency — no sibling project in this repo uses a test
framework yet; the assignment's required `tests/test_*.py` layout calls for
one).

- `test_mcp_server.py` — server started in-process (FastMCP's test client, or
  an `httpx.AsyncClient` against a locally bound instance); exercises
  discovery (`tools/list` names/schemas match §5) and each migrated tool
  including the full error-scenario table from §8.
- `test_batch_process.py` — mixed success/failure/skip batch; asserts
  aggregate counts and per-file `results[]`.
- `test_watch_directory.py` — start/poll/stop happy path (add a file mid-test,
  confirm it's detected on the next poll); invalid directory at start;
  runtime failure surfaced as a terminal event.
- `test_matching_agent_mcp.py` — agent connects to a locally-started test
  server instance via `MCPAdapter`, discovers tools, and invokes at least one
  real filesystem operation end-to-end. The chat-model call itself is
  mocked/stubbed so this doesn't require a live `OPENROUTER_API_KEY`, in the
  spirit of `agentic_profile_match/scripts/smoke_test.py`.

## 12. Docs & demo artifacts

- `docs/architecture.md` — the component diagram from §2, expanded with a
  short description of each piece.
- `docs/workflow-diagram.md` — a Mermaid state diagram of one full agent ↔
  MCP interaction (discovery → tool call → server-side filesystem op →
  structured result → agent continues), satisfying the required
  state-machine/workflow diagram deliverable.
- `docs/demo-script.md` — mapped to the assignment's suggested 9-step demo
  sequence (architecture intro → server config/startup → discovery → a
  migrated op → `batch_process` → `watch_directory` → full agent run →
  results/logs/tests → note bonus is not implemented).
- `README.md` — setup (`.env`, `docker compose up`), the two-process run
  model, REPL commands, testing instructions.

## 13. Explicitly out of scope

- The bonus multi-MCP integration (web-search/DB server) — skipped per
  earlier decision; can be a later add-on phase.
- Auth/access control on the MCP HTTP endpoint — localhost-only, no token,
  per earlier decision.
- Any reuse of `agentic_profile_match`'s RAG/Qdrant/multi-round-screening
  pipeline — this project only carries forward `llm_file_assistant`'s
  simpler tool-calling agent shape.

## 14. Phased implementation plan

1. **Scaffolding** — repo layout, `config.py`, `utils.py`, copy
   `llm_file_assistant/root_dir` → `sample_data/resumes/`, dependency updates
   in `pyproject.toml` (`fastmcp` already present; add `pytest` dev dep; no
   `pydantic-settings`, no `langchain-mcp-adapters`).
2. **Server: migrated tools** — `fs_core.py`, `filesystem_mcp_server.py` with
   `list_files`/`read_file`/`search_in_file`/`write_file` + `/health` route;
   manually verify discovery and each tool over HTTP.
3. **Server: new capabilities** — `batch_process`, then the `start_watch`/
   `poll_watch`/`stop_watch` trio.
4. **Server: error-handling hardening** — work through §8's scenario table
   explicitly; make sure every row is covered.
5. **Docker packaging** — `Dockerfile`, `docker-compose.yml`,
   `.dockerignore`; verify `docker compose up --build` serves the same
   behavior as local `uv run`.
6. **Agent refactor** — `matching_agent.py`: resolve the async
   `stream_events` + `MCPAdapter` question first (small spike within this
   phase), then port the REPL/agent shape from `llm_file_assistant/main.py`
   on top of it, removing all direct `fs_tools` usage.
7. **Tests** — the four `tests/test_*.py` files from §11.
8. **Docs & polish** — `docs/architecture.md`, `docs/workflow-diagram.md`,
   `docs/demo-script.md`, `README.md` updates.

Each phase becomes one or more tasks in the implementation plan (next step,
via the `writing-plans` skill).
