# MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `filesystem_mcp_server.py` (a Dockerized FastMCP server exposing sandboxed filesystem tools, `batch_process`, and `watch_directory`) and `matching_agent.py` (an async LangGraph agent/REPL that discovers and calls those tools exclusively through `langchain.mcp.MCPAdapter`), per `docs/spec.md`.

**Architecture:** Two processes. `fs_core.py` holds pure, undecorated filesystem logic ported from `llm_file_assistant/fs_tools.py`; `filesystem_mcp_server.py` wraps it as `@mcp.tool`s over Streamable HTTP and runs in Docker. `matching_agent.py` runs on the host, opens one `MCPAdapter` session for the whole REPL, discovers tools via `adapter.list_tools()`, and streams replies with `agent.stream_events(..., version="v3")` adapted to run on the same event loop as the MCP session.

**Tech Stack:** Python >=3.12, `fastmcp>=4.0.5`, `langchain>=1.3.16` (native `langchain.mcp.MCPAdapter`), `langgraph`, `pydantic>=2.12.5`, `pypdf`, `python-docx`, `rich`, `uv` workspace, Docker/Docker Compose, `pytest` + `pytest-asyncio` (new to this repo).

**Spec:** `mcp_integration/docs/spec.md`

## Global Constraints

- Python `>=3.12` everywhere (Dockerfile base image included).
- `mcp_integration` is a member of the root `uv` workspace (one shared `uv.lock` at repo root) — dependency resolution and Docker builds must account for this, not treat the project as standalone.
- Keep existing dependency floors as-is: `fastmcp>=4.0.5`, `langchain>=1.3.16`, `langchain-openrouter>=0.2.8`, `pydantic>=2.12.5`, `pypdf>=6.16.2`, `python-docx>=1.2.0`, `rich>=15.0.0`.
- No `pydantic-settings` and no `langchain-mcp-adapters` — explicitly dropped design decisions (spec §4, §9).
- Config is a plain `Settings` class (`__init__` calling `load_dotenv()` + `os.getenv(...)`, raising `ValueError` only for values with no safe default — i.e. `OPENROUTER_API_KEY`), matching `llm_file_assistant/config.py`, `agentic_profile_match/config.py`, and the FastMCP reference repo's `app/config.py` pattern.
- Every app-level tool failure returns `{"success": false, "error": {"code": ..., "message": ...}}` and never raises; protocol-level errors (unknown tool, bad params) are left to FastMCP's native JSON-RPC handling. Error codes are exactly: `NOT_FOUND`, `PATH_ESCAPES_ROOT`, `UNSUPPORTED_FORMAT`, `FILE_PROCESSING_ERROR`, `PERMISSION_DENIED`, `VALIDATION_ERROR`, `WATCH_ERROR` (spec §8).
- Filesystem sandbox: absolute paths and `..` segments are rejected before joining to the root; the resolved path is also checked for containment after resolution (spec §5, ported from `_resolve_within_root`).
- MCP transport is Streamable HTTP, unauthenticated, localhost-only — no auth code, no token checks (spec §2, §13).
- Out of scope, do not build: bonus multi-MCP integration, any auth/access control, any reuse of `agentic_profile_match`'s RAG/Qdrant pipeline (spec §13).
- Docker base image: `ghcr.io/astral-sh/uv:python3.12-trixie-slim`.

---

## Repository layout this plan produces

```
mcp_integration/
├── filesystem_mcp_server.py   # Part A entrypoint
├── matching_agent.py          # Part B entrypoint (main.py is deleted)
├── fs_core.py                 # pure filesystem + watch-state logic
├── config.py                  # Settings class
├── utils.py                   # CustomLogger (copied from llm_file_assistant)
├── Dockerfile
├── docker-compose.yml
├── sample_data/resumes/       # copied from llm_file_assistant/root_dir
├── tests/
│   ├── test_mcp_server.py
│   ├── test_batch_process.py
│   ├── test_watch_directory.py
│   └── test_matching_agent_mcp.py
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   ├── workflow-diagram.md
│   ├── demo-script.md
│   └── superpowers/plans/2026-09-23-mcp-integration-implementation.md  # this file
├── pyproject.toml
├── README.md
└── sample.env / .env
```

`.dockerignore` moves to the **repo root** (`/.dockerignore`), not `mcp_integration/.dockerignore` — see Task 6 for why. No per-project `.gitignore` is added; the root `.gitignore` already covers `.env`/`.envrc` for every workspace member, matching every sibling project (none of them has its own `.gitignore` either).

---

### Task 1: Scaffolding — config, logger, sample data, dependencies

**Files:**
- Create: `mcp_integration/config.py`
- Create: `mcp_integration/utils.py`
- Create: `mcp_integration/sample_data/resumes/` (copied tree, see step 3)
- Modify: `mcp_integration/pyproject.toml`
- Modify: `mcp_integration/sample.env`
- Delete: `mcp_integration/main.py` is **not** deleted yet — that happens in Task 8 when `matching_agent.py` replaces it as the entrypoint.

**Interfaces:**
- Produces: `config.settings` — a module-level `Settings()` singleton with attributes `ROOT_DIR: Path`, `ALLOWED_EXTENSIONS: set[str]`, `MAX_FILE_SIZE_BYTES: int`, `BATCH_MAX_CONCURRENCY: int`, `WATCH_POLL_INTERVAL_SECONDS: float`, `LOG_LEVEL: str`, `MCP_HOST: str`, `MCP_PORT: int`, `MCP_SERVER_URL: str`, `OPENROUTER_API_KEY: str`. Every later task imports `from config import settings`.
- Produces: `utils.logger` — a `CustomLogger` instance with `.debug/.info/.warning/.error(message: str)`. Every later task imports `from utils import logger`.

- [ ] **Step 1: Write `config.py`**

```python
import os
from pathlib import Path

from dotenv import load_dotenv


class Settings:
    def __init__(self):
        load_dotenv()

        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not self.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. Please set it in the environment "
                "variables or in a .env file."
            )

        self.MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
        self.MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
        # The agent always talks to the host-published Docker port, regardless
        # of what MCP_HOST is bound to inside the container.
        self.MCP_SERVER_URL = f"http://localhost:{self.MCP_PORT}/mcp"

        self.ROOT_DIR = (Path(__file__).parent / os.getenv("ROOT_DIR", "sample_data/resumes")).resolve()

        self.ALLOWED_EXTENSIONS = {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in os.getenv("ALLOWED_EXTENSIONS", ".txt,.docx,.pdf").split(",")
            if ext.strip()
        }
        self.MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", "10485760"))
        self.BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "4"))
        self.WATCH_POLL_INTERVAL_SECONDS = float(os.getenv("WATCH_POLL_INTERVAL_SECONDS", "5"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
```

- [ ] **Step 2: Write `utils.py`** (copied verbatim from `llm_file_assistant/utils.py`)

```python
class CustomLogger:
    """
    A simple wrapper around print to provide styled logging without conflicting with rich.Live.
    """
    def debug(self, message: str):
        # Dim Cyan
        print(f"\033[2;36mDEBUG:\033[0m {message}")

    def info(self, message: str):
        # Bold Blue
        print(f"\033[1;34mINFO:\033[0m {message}")

    def warning(self, message: str):
        # Bold Yellow
        print(f"\033[1;33mWARNING:\033[0m {message}")

    def error(self, message: str):
        # Bold Red
        print(f"\033[1;31mERROR:\033[0m {message}")

logger = CustomLogger()
```

- [ ] **Step 3: Copy the sample resume tree**

```bash
mkdir -p mcp_integration/sample_data
cp -r llm_file_assistant/root_dir mcp_integration/sample_data/resumes
```

Verify the copy has all 16 files (matches `llm_file_assistant/root_dir`'s current tree — `ats_summary_devops_bob.txt`, `resume_john_doe.pdf`, and one `.txt`/`.docx`/`.pdf` each under `data/`, `design/`, `engineering/`, `marketing/`, `sales/`):

```bash
find mcp_integration/sample_data/resumes -type f | wc -l
```

Expected: `16`.

- [ ] **Step 4: Update `pyproject.toml`** — add `python-dotenv` (imported directly by `config.py`; don't rely on it resolving transitively) and a `dependency-groups.dev` block for testing:

```toml
[project]
name = "mcp-integration"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=4.0.5",
    "langchain>=1.3.16",
    "langchain-openrouter>=0.2.8",
    "pydantic>=2.12.5",
    "pypdf>=6.16.2",
    "python-dotenv>=1.2.2",
    "python-docx>=1.2.0",
    "rich>=15.0.0",
]

[dependency-groups]
dev = [
    "httpx>=0.27",
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "uvicorn>=0.30",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 5: Add the new settings to `sample.env`**

```bash
OPENROUTER_API_KEY='your_openrouter_api_key_here'

# Optional
LANGSMITH_API_KEY='your_langsmith_api_key_here'
LANGSMITH_TRACING='your_langsmith_tracing_key_here'

# Filesystem MCP server
ROOT_DIR='sample_data/resumes'
ALLOWED_EXTENSIONS='.txt,.docx,.pdf'
MAX_FILE_SIZE_BYTES='10485760'
BATCH_MAX_CONCURRENCY='4'
WATCH_POLL_INTERVAL_SECONDS='5'
LOG_LEVEL='INFO'
MCP_HOST='127.0.0.1'
MCP_PORT='8000'
```

Copy `mcp_integration/sample.env` to `mcp_integration/.env` locally (already gitignored via the root `.gitignore`) and fill in a real `OPENROUTER_API_KEY` before running anything that imports `config`.

- [ ] **Step 6: Sync dependencies and smoke-test the config module**

```bash
cd mcp_integration
uv sync
uv run python -c "from config import settings; print(settings.ROOT_DIR, settings.MCP_SERVER_URL, sorted(settings.ALLOWED_EXTENSIONS))"
```

Expected: prints the resolved `sample_data/resumes` path, `http://localhost:8000/mcp`, and `['.docx', '.pdf', '.txt']`, with no `ValueError`.

- [ ] **Step 7: Commit**

```bash
git add mcp_integration/config.py mcp_integration/utils.py mcp_integration/sample_data \
        mcp_integration/pyproject.toml mcp_integration/sample.env
git commit -m "feat(mcp_integration): scaffold config, logger, sample data, test deps"
```

---

### Task 2: `fs_core.py` — pure filesystem logic

**Files:**
- Create: `mcp_integration/fs_core.py`
- Create: `mcp_integration/tests/test_mcp_server.py` (unit-level section; the server/tool-level section is added in Task 3)

**Interfaces:**
- Consumes: `config.settings` (Task 1) — `ROOT_DIR`, `ALLOWED_EXTENSIONS`, `MAX_FILE_SIZE_BYTES`.
- Produces: `fs_core.resolve_within_root(relative_path: str) -> Path`, `fs_core.extract_text(path: Path) -> str`, `fs_core.file_metadata(path: Path) -> dict`, `fs_core.is_allowed_extension(path: Path) -> bool`, `fs_core.exceeds_max_size(path: Path) -> bool`. `filesystem_mcp_server.py` (Task 3) and the `batch_process`/watch logic (Tasks 4-5, also added to this file) all build on these.

- [ ] **Step 1: Write the failing tests**

```python
# mcp_integration/tests/test_mcp_server.py
import pytest

import fs_core
from config import settings


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    return tmp_path


def test_resolve_within_root_accepts_nested_relative_path(sandbox):
    (sandbox / "engineering").mkdir()
    (sandbox / "engineering" / "alice.txt").write_text("hi", encoding="utf-8")
    resolved = fs_core.resolve_within_root("engineering/alice.txt")
    assert resolved == sandbox / "engineering" / "alice.txt"


def test_resolve_within_root_rejects_absolute_path(sandbox):
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("/etc/passwd")


def test_resolve_within_root_rejects_dotdot_escape(sandbox):
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("../outside.txt")


def test_extract_text_reads_txt_file(sandbox):
    (sandbox / "note.txt").write_text("hello sandbox", encoding="utf-8")
    assert fs_core.extract_text(sandbox / "note.txt") == "hello sandbox"


def test_extract_text_reads_docx_and_pdf_fixtures():
    # Uses the real sample_data tree copied in Task 1 -- generating valid
    # .docx/.pdf bytes from scratch in a unit test isn't worth it.
    docx_path = settings.ROOT_DIR / "engineering" / "devops_bob.docx"
    pdf_path = settings.ROOT_DIR / "engineering" / "frontend_priya.pdf"
    assert fs_core.extract_text(docx_path).strip() != ""
    assert fs_core.extract_text(pdf_path).strip() != ""


def test_extract_text_rejects_unsupported_extension(sandbox):
    bad = sandbox / "resume.doc"
    bad.write_text("legacy format", encoding="utf-8")
    with pytest.raises(ValueError):
        fs_core.extract_text(bad)


def test_file_metadata_fields(sandbox):
    (sandbox / "note.txt").write_text("hi", encoding="utf-8")
    meta = fs_core.file_metadata(sandbox / "note.txt")
    assert meta["name"] == "note.txt"
    assert meta["path"] == "note.txt"
    assert meta["extension"] == ".txt"
    assert meta["size_bytes"] == 2
    assert "modified" in meta


def test_is_allowed_extension_and_exceeds_max_size(sandbox, monkeypatch):
    allowed = sandbox / "note.txt"
    allowed.write_text("hi", encoding="utf-8")
    disallowed = sandbox / "note.exe"
    disallowed.write_bytes(b"\x00")

    assert fs_core.is_allowed_extension(allowed) is True
    assert fs_core.is_allowed_extension(disallowed) is False

    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1)
    assert fs_core.exceeds_max_size(allowed) is True
```

Note: `test_extract_text_reads_docx_and_pdf_fixtures` uses the **real** `settings.ROOT_DIR` (not the `sandbox` fixture), so it depends on Task 1's sample-data copy already being in place.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd mcp_integration
uv run pytest tests/test_mcp_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'fs_core'`.

- [ ] **Step 3: Write `fs_core.py`**

```python
"""Pure filesystem logic for the Filesystem MCP Server.

No MCP or LangChain decoration lives here -- filesystem_mcp_server.py wraps
these functions as MCP tools. Kept separate so the sandboxing/extraction
logic can be unit-tested without spinning up a server.
"""

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from config import settings


def resolve_within_root(relative_path: str) -> Path:
    """Resolves a relative path to an absolute path inside settings.ROOT_DIR.

    Rejects absolute paths and ".." segments before joining, since
    `Path(root) / "/abs/path"` would otherwise silently discard `root`
    and resolve to an unrelated absolute path.
    """
    candidate_parts = Path(relative_path)
    if candidate_parts.is_absolute() or ".." in candidate_parts.parts:
        raise ValueError(f"Path '{relative_path}' is not allowed -- it must stay inside the sandbox root.")

    candidate = (settings.ROOT_DIR / candidate_parts).resolve()
    if candidate != settings.ROOT_DIR and settings.ROOT_DIR not in candidate.parents:
        raise ValueError(f"Path '{relative_path}' escapes the sandbox root.")
    return candidate


def extract_text(path: Path) -> str:
    """Extracts plain text content from a .txt, .docx, or .pdf file."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Unsupported file type '{suffix}'. Supported types: .txt, .docx, .pdf")


def file_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(settings.ROOT_DIR)),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def is_allowed_extension(path: Path) -> bool:
    return path.suffix.lower() in settings.ALLOWED_EXTENSIONS


def exceeds_max_size(path: Path) -> bool:
    return path.stat().st_size > settings.MAX_FILE_SIZE_BYTES
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_mcp_server.py -v
```

Expected: all 8 tests `PASS`.

- [ ] **Step 5: Commit**

```bash
git add mcp_integration/fs_core.py mcp_integration/tests/test_mcp_server.py
git commit -m "feat(mcp_integration): port sandboxed filesystem logic into fs_core.py"
```

---

### Task 3: `filesystem_mcp_server.py` — migrated tools + health route

**Files:**
- Create: `mcp_integration/filesystem_mcp_server.py`
- Modify: `mcp_integration/tests/test_mcp_server.py` (append server-level tests)

**Interfaces:**
- Consumes: `fs_core.resolve_within_root/extract_text/file_metadata` (Task 2), `config.settings`, `utils.logger`.
- Produces: `filesystem_mcp_server.mcp` — the `FastMCP` server instance, importable by tests and by Tasks 4-5 (which add more `@mcp.tool`s to this same file) and Task 6 (Docker `CMD`). Tool names on `mcp`: `list_files`, `read_file`, `search_in_file`, `write_file` (this task); `batch_process` (Task 4); `start_watch`, `poll_watch`, `stop_watch` (Task 5).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_mcp_server.py`)

```python
from fastmcp import Client

import filesystem_mcp_server as server


@pytest.fixture
def server_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(server.settings, "ROOT_DIR", tmp_path)
    (tmp_path / "engineering").mkdir()
    (tmp_path / "engineering" / "alice.txt").write_text("Alice knows Python and AWS.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("top level note", encoding="utf-8")
    return tmp_path


async def test_discovery_includes_migrated_tools():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"list_files", "read_file", "search_in_file", "write_file"}.issubset(names)


async def test_health_route_returns_ok():
    async with Client(server.mcp) as client:
        # /health is a plain HTTP route, not an MCP tool -- exercised via
        # Docker's healthcheck in Task 6, not the MCP client here. This test
        # just confirms the route function itself returns the right body.
        pass
    response = await server.health(request=None)
    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'


async def test_list_files_recursive_with_extension_filter(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("list_files", {"directory": ".", "extension": ".txt"})
    paths = {entry["path"] for entry in result.data}
    assert paths == {"engineering/alice.txt", "notes.txt"}


async def test_list_files_not_found_directory(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("list_files", {"directory": "does-not-exist"})
    assert result.data[0]["error"]["code"] == "NOT_FOUND"


async def test_read_file_success_and_not_found(server_sandbox):
    async with Client(server.mcp) as client:
        ok = await client.call_tool("read_file", {"filepath": "engineering/alice.txt"})
        missing = await client.call_tool("read_file", {"filepath": "engineering/bob.txt"})

    assert ok.data["success"] is True
    assert "Python" in ok.data["content"]
    assert missing.data["success"] is False
    assert missing.data["error"]["code"] == "NOT_FOUND"


async def test_read_file_rejects_path_escape(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("read_file", {"filepath": "../outside.txt"})
    assert result.data["success"] is False
    assert result.data["error"]["code"] == "PATH_ESCAPES_ROOT"


async def test_search_in_file_finds_matches(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "search_in_file", {"filepath": "engineering/alice.txt", "keyword": "python"}
        )
    assert result.data["success"] is True
    assert result.data["match_count"] == 1


async def test_search_in_file_rejects_empty_keyword(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "search_in_file", {"filepath": "engineering/alice.txt", "keyword": "   "}
        )
    assert result.data["success"] is False
    assert result.data["error"]["code"] == "VALIDATION_ERROR"


async def test_write_file_creates_then_refuses_overwrite(server_sandbox):
    async with Client(server.mcp) as client:
        first = await client.call_tool("write_file", {"filepath": "shortlist.txt", "content": "Alice"})
        second = await client.call_tool("write_file", {"filepath": "shortlist.txt", "content": "Bob"})

    assert first.data["success"] is True
    assert (server_sandbox / "shortlist.txt").read_text(encoding="utf-8") == "Alice"
    assert second.data["success"] is False
    assert second.data["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mcp_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'filesystem_mcp_server'`.

- [ ] **Step 3: Write `filesystem_mcp_server.py`**

```python
"""Filesystem MCP Server -- Part A deliverable.

Wraps fs_core.py's sandboxed filesystem logic as MCP tools over Streamable
HTTP. Every tool keeps returning a structured {success, ..., error} dict
(never raises for app-level failures) so an MCP client can branch on the
result without needing to catch a protocol-level error.
"""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

import fs_core
from config import settings
from utils import logger

mcp = FastMCP(
    name="filesystem-mcp-server",
    instructions=(
        "Filesystem tools for a sandboxed directory of candidate resumes. "
        "All paths are relative to the sandbox root and may be .txt, .docx, "
        "or .pdf. Use list_files to discover what's available before "
        "reading or searching a specific file."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool
def list_files(
    directory: Annotated[
        str,
        Field(description="Path relative to the sandbox root to list, e.g. 'engineering' or '.' for everything. Listed recursively."),
    ] = ".",
    extension: Annotated[
        str | None,
        Field(description="Optional file extension filter, e.g. '.pdf' or 'txt'. If omitted, files of every type are returned."),
    ] = None,
) -> list[dict]:
    """Recursively list files under a directory inside the sandbox root, optionally filtered by extension, with name/size/modified metadata for each."""
    logger.info(f"list_files(directory={directory!r}, extension={extension!r})")
    try:
        target = fs_core.resolve_within_root(directory)
    except ValueError as exc:
        return [{"error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}]

    if not target.exists():
        return [{"error": {"code": "NOT_FOUND", "message": f"Path not found: {directory}"}}]
    if not target.is_dir():
        return [{"error": {"code": "VALIDATION_ERROR", "message": f"Not a directory: {directory}"}}]

    normalized_ext = None
    if extension:
        normalized_ext = extension.lower()
        if not normalized_ext.startswith("."):
            normalized_ext = f".{normalized_ext}"

    entries = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        if normalized_ext and path.suffix.lower() != normalized_ext:
            continue
        entries.append(fs_core.file_metadata(path))
    return entries


@mcp.tool
def read_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root of the file to read, e.g. 'engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."),
    ],
) -> dict:
    """Read a resume file (.txt, .docx, or .pdf), extract its text content, and return it with file metadata."""
    logger.info(f"read_file(filepath={filepath!r})")
    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {
            "success": False, "filepath": filepath, "content": None, "metadata": None,
            "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)},
        }

    if not target.exists() or not target.is_file():
        return {
            "success": False, "filepath": filepath, "content": None, "metadata": None,
            "error": {"code": "NOT_FOUND", "message": f"File not found: {filepath}"},
        }

    try:
        content = fs_core.extract_text(target)
    except ValueError as exc:
        return {
            "success": False, "filepath": filepath, "content": None,
            "metadata": fs_core.file_metadata(target),
            "error": {"code": "UNSUPPORTED_FORMAT", "message": str(exc)},
        }
    except Exception as exc:
        return {
            "success": False, "filepath": filepath, "content": None,
            "metadata": fs_core.file_metadata(target),
            "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Could not read '{filepath}': {exc}"},
        }

    return {
        "success": True, "filepath": filepath, "content": content,
        "metadata": fs_core.file_metadata(target), "error": None,
    }


@mcp.tool
def search_in_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root of the file to search, e.g. 'engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."),
    ],
    keyword: Annotated[str, Field(description="The keyword or phrase to search for, case-insensitive.")],
) -> dict:
    """Search for a keyword or phrase inside one resume file (.txt, .docx, or .pdf), returning every match with surrounding context. Case-insensitive."""
    logger.info(f"search_in_file(filepath={filepath!r}, keyword={keyword!r})")
    empty_result = {"success": False, "filepath": filepath, "keyword": keyword, "matches": [], "match_count": 0}

    if not keyword.strip():
        return {**empty_result, "error": {"code": "VALIDATION_ERROR", "message": "Please provide a non-empty search keyword."}}

    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {**empty_result, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if not target.exists() or not target.is_file():
        return {**empty_result, "error": {"code": "NOT_FOUND", "message": f"File not found: {filepath}"}}

    try:
        content = fs_core.extract_text(target)
    except Exception as exc:
        return {**empty_result, "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Could not read '{filepath}': {exc}"}}

    context_window = 60
    keyword_lower = keyword.lower()
    content_lower = content.lower()
    matches = []
    search_from = 0
    while True:
        idx = content_lower.find(keyword_lower, search_from)
        if idx == -1:
            break
        line_number = content.count("\n", 0, idx) + 1
        ctx_start = max(0, idx - context_window)
        ctx_end = min(len(content), idx + len(keyword) + context_window)
        context = " ".join(content[ctx_start:ctx_end].split())
        matches.append({"line_number": line_number, "context": context})
        search_from = idx + len(keyword_lower)

    return {
        "success": True, "filepath": filepath, "keyword": keyword,
        "matches": matches, "match_count": len(matches), "error": None,
    }


@mcp.tool
def write_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root for the new file, e.g. 'shortlist_eng.txt'. Must not already exist."),
    ],
    content: Annotated[str, Field(description="The full text content to write to the file.")],
) -> dict:
    """Create a new text file inside the sandbox root with the given content, creating parent directories as needed. Refuses to overwrite an existing file."""
    logger.info(f"write_file(filepath={filepath!r}, content_length={len(content)})")
    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {"success": False, "filepath": filepath, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if target.is_dir():
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "VALIDATION_ERROR", "message": f"Cannot write to '{filepath}': it is a directory."},
        }
    if target.exists():
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "VALIDATION_ERROR", "message": f"Refusing to overwrite existing file: {filepath}"},
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "PERMISSION_DENIED", "message": f"Could not write '{filepath}': {exc}"},
        }

    return {"success": True, "filepath": filepath, "bytes_written": len(content.encode("utf-8")), "error": None}


if __name__ == "__main__":
    mcp.run(transport="http", host=settings.MCP_HOST, port=settings.MCP_PORT)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_mcp_server.py -v
```

Expected: all tests `PASS`. If `Client(server.mcp)`, `result.data`, or `@mcp.custom_route` don't match the installed `fastmcp>=4.0.5` API exactly, check `uv run python -c "import fastmcp; help(fastmcp.Client)"` and adjust — this is the first point in the plan where the exact FastMCP client surface gets exercised for real.

- [ ] **Step 5: Manually verify discovery and one tool call over real HTTP** (sanity check beyond the in-process test client)

```bash
uv run python filesystem_mcp_server.py &
sleep 1
curl http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/mcp -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
kill %1
```

Expected: `/health` returns `{"status": "ok"}`; the `tools/list` JSON-RPC response includes `list_files`, `read_file`, `search_in_file`, `write_file` with their descriptions/schemas.

- [ ] **Step 6: Commit**

```bash
git add mcp_integration/filesystem_mcp_server.py mcp_integration/tests/test_mcp_server.py
git commit -m "feat(mcp_integration): add filesystem_mcp_server.py with migrated tools"
```

---

### Task 4: `batch_process` tool

**Files:**
- Modify: `mcp_integration/filesystem_mcp_server.py` (add `import asyncio`, add `batch_process` tool)
- Create: `mcp_integration/tests/test_batch_process.py`

**Interfaces:**
- Consumes: `fs_core.resolve_within_root/extract_text/file_metadata/is_allowed_extension/exceeds_max_size` (Task 2), `config.settings.BATCH_MAX_CONCURRENCY`.
- Produces: `batch_process` MCP tool on `filesystem_mcp_server.mcp`, returning `{"success": bool, "total_files": int, "processed": int, "failed": int, "skipped": int, "results": list[dict]}`. Per-`results[]` entry: `{"path": str, "status": "success"|"error"|"skipped", "result": {...}}` or `{"path": str, "status": "error", "error": {"code": str, "message": str}}` or `{"path": str, "status": "skipped", "reason": str}`.

- [ ] **Step 1: Write the failing tests**

```python
# mcp_integration/tests/test_batch_process.py
import pytest
from fastmcp import Client

import filesystem_mcp_server as server


@pytest.fixture
def batch_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(server.settings, "ROOT_DIR", tmp_path)
    (tmp_path / "engineering").mkdir()
    (tmp_path / "engineering" / "alice.txt").write_text("Alice: Python, AWS.", encoding="utf-8")
    (tmp_path / "engineering" / "bob.txt").write_text("Bob: Go, Kubernetes.", encoding="utf-8")
    (tmp_path / "engineering" / "resume.exe").write_bytes(b"\x00\x01")  # disallowed extension
    return tmp_path


async def test_batch_process_requires_files_xor_directory():
    async with Client(server.mcp) as client:
        neither = await client.call_tool("batch_process", {})
        both = await client.call_tool("batch_process", {"files": ["a.txt"], "directory": "."})
    assert neither.data["success"] is False
    assert neither.data["error"]["code"] == "VALIDATION_ERROR"
    assert both.data["success"] is False
    assert both.data["error"]["code"] == "VALIDATION_ERROR"


async def test_batch_process_directory_mixed_outcomes(batch_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "batch_process", {"directory": "engineering", "recursive": True}
        )

    data = result.data
    assert data["total_files"] == 3
    assert data["processed"] == 2
    assert data["failed"] == 0
    assert data["skipped"] == 1
    assert data["processed"] + data["failed"] + data["skipped"] == data["total_files"]

    by_path = {r["path"]: r for r in data["results"]}
    assert by_path["engineering/alice.txt"]["status"] == "success"
    assert by_path["engineering/resume.exe"]["status"] == "skipped"


async def test_batch_process_explicit_files_reports_not_found_as_error(batch_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "batch_process", {"files": ["engineering/alice.txt", "engineering/missing.txt"]}
        )

    data = result.data
    assert data["total_files"] == 2
    assert data["processed"] == 1
    assert data["failed"] == 1
    by_path = {r["path"]: r for r in data["results"]}
    assert by_path["engineering/missing.txt"]["status"] == "error"
    assert by_path["engineering/missing.txt"]["error"]["code"] == "NOT_FOUND"


async def test_batch_process_skips_oversized_file(batch_sandbox, monkeypatch):
    monkeypatch.setattr(server.settings, "MAX_FILE_SIZE_BYTES", 1)
    async with Client(server.mcp) as client:
        result = await client.call_tool("batch_process", {"files": ["engineering/alice.txt"]})

    assert result.data["skipped"] == 1
    assert result.data["results"][0]["status"] == "skipped"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_batch_process.py -v
```

Expected: `fastmcp.exceptions.ToolError` or similar "unknown tool 'batch_process'" failure.

- [ ] **Step 3: Add `batch_process` to `filesystem_mcp_server.py`**

Add `import asyncio` to the top of the file (alongside the existing imports), then add:

```python
@mcp.tool
async def batch_process(
    files: Annotated[
        list[str] | None,
        Field(description="Explicit list of paths (relative to the sandbox root) to process. Mutually exclusive with 'directory'."),
    ] = None,
    directory: Annotated[
        str | None,
        Field(description="Directory (relative to the sandbox root) to expand into a file list, the same way list_files would. Mutually exclusive with 'files'."),
    ] = None,
    extension: Annotated[
        str | None,
        Field(description="Optional extension filter when expanding 'directory', e.g. '.pdf'."),
    ] = None,
    recursive: Annotated[
        bool,
        Field(description="Whether to recurse into subdirectories when expanding 'directory'."),
    ] = True,
) -> dict:
    """Read and extract text/metadata for many files at once (bounded concurrency), returning per-file status and aggregate counts. Provide either 'files' or 'directory', not both."""
    logger.info(f"batch_process(files={files!r}, directory={directory!r}, extension={extension!r}, recursive={recursive!r})")

    if files and directory:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Provide either 'files' or 'directory', not both."}}
    if not files and not directory:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Provide either 'files' or 'directory'."}}

    if directory is not None:
        try:
            target_dir = fs_core.resolve_within_root(directory)
        except ValueError as exc:
            return {"success": False, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}
        if not target_dir.exists() or not target_dir.is_dir():
            return {"success": False, "error": {"code": "NOT_FOUND", "message": f"Directory not found: {directory}"}}

        normalized_ext = None
        if extension:
            normalized_ext = extension.lower()
            if not normalized_ext.startswith("."):
                normalized_ext = f".{normalized_ext}"

        walker = target_dir.rglob("*") if recursive else target_dir.glob("*")
        candidates = [
            str(p.relative_to(settings.ROOT_DIR)) for p in sorted(walker)
            if p.is_file() and (normalized_ext is None or p.suffix.lower() == normalized_ext)
        ]
    else:
        candidates = list(files)

    semaphore = asyncio.Semaphore(settings.BATCH_MAX_CONCURRENCY)

    async def process_one(rel_path: str) -> dict:
        async with semaphore:
            try:
                target = fs_core.resolve_within_root(rel_path)
            except ValueError as exc:
                return {"path": rel_path, "status": "error", "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

            if not target.exists() or not target.is_file():
                return {"path": rel_path, "status": "error", "error": {"code": "NOT_FOUND", "message": f"File not found: {rel_path}"}}
            if not fs_core.is_allowed_extension(target):
                return {"path": rel_path, "status": "skipped", "reason": f"Extension '{target.suffix}' is not in ALLOWED_EXTENSIONS."}
            if fs_core.exceeds_max_size(target):
                return {"path": rel_path, "status": "skipped", "reason": f"File exceeds MAX_FILE_SIZE_BYTES ({settings.MAX_FILE_SIZE_BYTES})."}

            try:
                content = await asyncio.to_thread(fs_core.extract_text, target)
            except Exception as exc:
                return {"path": rel_path, "status": "error", "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Unable to process '{rel_path}': {exc}"}}

            return {
                "path": rel_path, "status": "success",
                "result": {"content": content, "metadata": fs_core.file_metadata(target)},
            }

    results = await asyncio.gather(*(process_one(p) for p in candidates))

    processed = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    return {
        "success": True,
        "total_files": len(results),
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_batch_process.py -v
```

Expected: all tests `PASS`.

- [ ] **Step 5: Commit**

```bash
git add mcp_integration/filesystem_mcp_server.py mcp_integration/tests/test_batch_process.py
git commit -m "feat(mcp_integration): add batch_process tool"
```

---

### Task 5: `watch_directory` trio — `start_watch` / `poll_watch` / `stop_watch`

**Files:**
- Modify: `mcp_integration/fs_core.py` (add watch-state management)
- Modify: `mcp_integration/filesystem_mcp_server.py` (add three thin `@mcp.tool` wrappers)
- Create: `mcp_integration/tests/test_watch_directory.py`

**Interfaces:**
- Consumes: `fs_core.resolve_within_root` (Task 2), `config.settings.WATCH_POLL_INTERVAL_SECONDS`.
- Produces: `fs_core.start_watch(directory_path, recursive, allowed_extensions, poll_interval_seconds) -> dict`, `fs_core.poll_watch(watch_id) -> dict`, `fs_core.stop_watch(watch_id) -> dict`, plus the matching `start_watch`/`poll_watch`/`stop_watch` MCP tools on `filesystem_mcp_server.mcp`.

Design: a new file is reported twice — once as `{"ready": False}` the poll after it's first seen, and again as `{"ready": True}` on the first later poll where its size hasn't changed since the previous scan (the "stable across two consecutive polls" guard from spec §7). Files present when `start_watch` is called are snapshotted as already-stable and never reported.

- [ ] **Step 1: Write the failing tests**

```python
# mcp_integration/tests/test_watch_directory.py
import shutil
import time

import pytest
from fastmcp import Client

import filesystem_mcp_server as server


@pytest.fixture
def watch_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(server.settings, "ROOT_DIR", tmp_path)
    (tmp_path / "watched").mkdir()
    (tmp_path / "watched" / "existing.txt").write_text("already here", encoding="utf-8")
    return tmp_path


async def test_start_watch_rejects_missing_directory(watch_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("start_watch", {"directory_path": "does-not-exist"})
    assert result.data["success"] is False
    assert result.data["error"]["code"] == "NOT_FOUND"


async def test_watch_detects_new_file_then_marks_it_ready(watch_sandbox):
    async with Client(server.mcp) as client:
        started = await client.call_tool(
            "start_watch", {"directory_path": "watched", "poll_interval_seconds": 0.2}
        )
        watch_id = started.data["watch_id"]
        assert started.data["success"] is True

        # Files present at start_watch time are snapshotted, not reported.
        time.sleep(0.3)
        first_poll = await client.call_tool("poll_watch", {"watch_id": watch_id})
        assert first_poll.data["events"] == []

        (watch_sandbox / "watched" / "new_resume.txt").write_text("brand new", encoding="utf-8")

        time.sleep(0.3)
        detected_poll = await client.call_tool("poll_watch", {"watch_id": watch_id})
        detected = [e for e in detected_poll.data["events"] if e.get("path") == "new_resume.txt"]
        assert len(detected) == 1
        assert detected[0]["ready"] is False

        time.sleep(0.3)
        ready_poll = await client.call_tool("poll_watch", {"watch_id": watch_id})
        ready = [e for e in ready_poll.data["events"] if e.get("path") == "new_resume.txt"]
        assert len(ready) == 1
        assert ready[0]["ready"] is True

        stopped = await client.call_tool("stop_watch", {"watch_id": watch_id})
        assert stopped.data["stopped"] is True


async def test_poll_unknown_watch_id_returns_validation_error(watch_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("poll_watch", {"watch_id": "not-a-real-id"})
    assert result.data["success"] is False
    assert result.data["error"]["code"] == "VALIDATION_ERROR"


async def test_watch_surfaces_runtime_failure_as_terminal_event(watch_sandbox):
    async with Client(server.mcp) as client:
        started = await client.call_tool(
            "start_watch", {"directory_path": "watched", "poll_interval_seconds": 0.2}
        )
        watch_id = started.data["watch_id"]

        shutil.rmtree(watch_sandbox / "watched")

        time.sleep(0.5)
        poll_after_deletion = await client.call_tool("poll_watch", {"watch_id": watch_id})
        error_events = [e for e in poll_after_deletion.data["events"] if e.get("type") == "error"]
        assert error_events
        assert poll_after_deletion.data["active"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_watch_directory.py -v
```

Expected: "unknown tool 'start_watch'" failures.

- [ ] **Step 3: Add watch-state management to `fs_core.py`**

Add these imports to the top of `fs_core.py`: `import threading`, `import uuid`, `from dataclasses import dataclass, field`. Then append:

```python
@dataclass
class _WatchState:
    directory: Path
    recursive: bool
    allowed_extensions: set[str] | None
    poll_interval_seconds: float
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    known: dict[str, dict] = field(default_factory=dict)
    pending_events: list[dict] = field(default_factory=list)
    active: bool = True
    thread: threading.Thread | None = None


_watches: dict[str, _WatchState] = {}


def _scan(state: "_WatchState") -> dict[str, int]:
    walker = state.directory.rglob("*") if state.recursive else state.directory.glob("*")
    found = {}
    for path in walker:
        if not path.is_file():
            continue
        if state.allowed_extensions and path.suffix.lower() not in state.allowed_extensions:
            continue
        found[str(path.relative_to(state.directory))] = path.stat().st_size
    return found


def _watch_loop(state: "_WatchState") -> None:
    try:
        while not state.stop_event.is_set():
            current = _scan(state)
            now = datetime.now(timezone.utc).isoformat()
            with state.lock:
                for rel_path, size in current.items():
                    entry = state.known.get(rel_path)
                    if entry is None:
                        state.known[rel_path] = {"size": size, "stable": False, "detected_at": now}
                        state.pending_events.append(
                            {"path": rel_path, "filename": Path(rel_path).name, "detected_at": now, "ready": False}
                        )
                    elif not entry["stable"]:
                        if entry["size"] == size:
                            entry["stable"] = True
                            state.pending_events.append(
                                {"path": rel_path, "filename": Path(rel_path).name,
                                 "detected_at": entry["detected_at"], "ready": True}
                            )
                        else:
                            entry["size"] = size
            state.stop_event.wait(state.poll_interval_seconds)
    except Exception as exc:
        with state.lock:
            state.pending_events.append({"type": "error", "message": f"Watch loop failed: {exc}"})
    finally:
        with state.lock:
            state.active = False


def start_watch(
    directory_path: str,
    recursive: bool = False,
    allowed_extensions: list[str] | None = None,
    poll_interval_seconds: float | None = None,
) -> dict:
    try:
        target = resolve_within_root(directory_path)
    except ValueError as exc:
        return {"success": False, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if not target.exists() or not target.is_dir():
        return {"success": False, "error": {"code": "NOT_FOUND", "message": f"Directory not found: {directory_path}"}}

    normalized_exts = None
    if allowed_extensions:
        normalized_exts = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_extensions
        }

    state = _WatchState(
        directory=target,
        recursive=recursive,
        allowed_extensions=normalized_exts,
        poll_interval_seconds=poll_interval_seconds or settings.WATCH_POLL_INTERVAL_SECONDS,
    )
    now = datetime.now(timezone.utc).isoformat()
    for rel_path, size in _scan(state).items():
        state.known[rel_path] = {"size": size, "stable": True, "detected_at": now}

    watch_id = uuid.uuid4().hex
    state.thread = threading.Thread(target=_watch_loop, args=(state,), daemon=True)
    _watches[watch_id] = state
    state.thread.start()

    return {"success": True, "watch_id": watch_id, "error": None}


def poll_watch(watch_id: str) -> dict:
    state = _watches.get(watch_id)
    if state is None:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Unknown watch_id: {watch_id}"}}

    with state.lock:
        events = state.pending_events[:]
        state.pending_events.clear()
        active = state.active

    return {"success": True, "watch_id": watch_id, "events": events, "active": active, "error": None}


def stop_watch(watch_id: str) -> dict:
    state = _watches.pop(watch_id, None)
    if state is None:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Unknown watch_id: {watch_id}"}}

    state.stop_event.set()
    if state.thread is not None:
        state.thread.join(timeout=max(state.poll_interval_seconds * 2, 2))

    return {"success": True, "watch_id": watch_id, "stopped": True, "error": None}
```

- [ ] **Step 4: Add the three thin tool wrappers to `filesystem_mcp_server.py`**

```python
@mcp.tool
def start_watch(
    directory_path: Annotated[str, Field(description="Directory relative to the sandbox root to watch for new files.")],
    recursive: Annotated[bool, Field(description="Whether to watch subdirectories too.")] = False,
    allowed_extensions: Annotated[
        list[str] | None,
        Field(description="Optional list of extensions to watch for, e.g. ['.pdf', '.docx']. If omitted, all files are watched."),
    ] = None,
    poll_interval_seconds: Annotated[
        float | None,
        Field(description="Seconds between scans. Defaults to the server's WATCH_POLL_INTERVAL_SECONDS setting."),
    ] = None,
) -> dict:
    """Start watching a directory in the sandbox for new files, returning a watch_id to pass to poll_watch/stop_watch."""
    logger.info(f"start_watch(directory_path={directory_path!r}, recursive={recursive!r})")
    return fs_core.start_watch(directory_path, recursive, allowed_extensions, poll_interval_seconds)


@mcp.tool
def poll_watch(
    watch_id: Annotated[str, Field(description="The watch_id returned by start_watch.")],
) -> dict:
    """Drain new-file events detected since the last poll for a running watch. Non-blocking; returns immediately."""
    logger.info(f"poll_watch(watch_id={watch_id!r})")
    return fs_core.poll_watch(watch_id)


@mcp.tool
def stop_watch(
    watch_id: Annotated[str, Field(description="The watch_id returned by start_watch.")],
) -> dict:
    """Stop a running watch and release its background thread."""
    logger.info(f"stop_watch(watch_id={watch_id!r})")
    return fs_core.stop_watch(watch_id)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_watch_directory.py -v
```

Expected: all 4 tests `PASS`. The timing-based test is inherently a little sensitive — if it's flaky in CI, raise the `time.sleep` margins relative to `poll_interval_seconds`, don't shrink the poll interval further.

- [ ] **Step 6: Run the full test suite so far**

```bash
uv run pytest tests/ -v
```

Expected: all tests across `test_mcp_server.py`, `test_batch_process.py`, `test_watch_directory.py` `PASS`. This is also the point to walk the spec §8 error-code table by hand and confirm every row (`NOT_FOUND`, `PATH_ESCAPES_ROOT`, `UNSUPPORTED_FORMAT`, `FILE_PROCESSING_ERROR`, `PERMISSION_DENIED`, `VALIDATION_ERROR`, `WATCH_ERROR`) is hit by at least one test above: `NOT_FOUND`/`PATH_ESCAPES_ROOT`/`VALIDATION_ERROR` are covered directly; `UNSUPPORTED_FORMAT` and `FILE_PROCESSING_ERROR` are exercised by `fs_core.extract_text`'s unit tests plus `batch_process`'s error path; `PERMISSION_DENIED` is reachable only via an OS-level write failure (not portably testable — leave as code-reviewed, not test-covered, and note this in `docs/demo-script.md` in Task 9). `WATCH_ERROR` per spec is the code family for watch runtime failures; align the `_watch_loop` exception handler's emitted event with `{"type": "error", "message": ...}` as already implemented — no separate `code` field was specified for watch events in spec §7, so this is intentionally different in shape from the other tools' `{code, message}` errors.

- [ ] **Step 7: Commit**

```bash
git add mcp_integration/fs_core.py mcp_integration/filesystem_mcp_server.py mcp_integration/tests/test_watch_directory.py
git commit -m "feat(mcp_integration): add watch_directory trio (start_watch/poll_watch/stop_watch)"
```

---

### Task 6: Docker packaging

**Files:**
- Create: `mcp_integration/Dockerfile`
- Create: `mcp_integration/docker-compose.yml`
- Create: `/.dockerignore` (repo root — see rationale below)

**Interfaces:**
- Consumes: `filesystem_mcp_server.py` (Task 3-5) as the container's entrypoint; `mcp_integration/.env` (Task 1) for runtime config.
- Produces: a running `filesystem-mcp-server` container reachable at `http://localhost:8000/mcp` from the host, for Tasks 7-8 to connect to.

**Why the build context is the repo root, not `mcp_integration/`:** this repo uses a `uv` **workspace** — one root `pyproject.toml` with `[tool.uv.workspace] members`, and a single shared `uv.lock` at the repo root (confirmed: `agentic_profile_match`'s and `rag_profile_match`'s own `pyproject.toml` don't carry their own lockfiles either). `uv sync` run from inside `mcp_integration/` alone, with only that subdirectory's `pyproject.toml`/`uv.lock` available, cannot resolve the workspace. The reference `todos` project this Dockerfile pattern is adapted from is a *standalone* uv project (its own `pyproject.toml` + `uv.lock`), so its simple "bind-mount just the lockfile" layer doesn't transfer directly — the build context has to be the repo root so `uv sync --package mcp-integration` can see the workspace root and the shared lockfile. `.dockerignore` follows the build context, so it also moves to the repo root (Docker only honors a `.dockerignore` at the root of the build context, not next to the `Dockerfile`, when they differ).

- [ ] **Step 1: Write `mcp_integration/Dockerfile`**

```dockerfile
# Build context is the repo root (see docker-compose.yml's build.context) --
# this project is a uv workspace member, so dependency resolution needs the
# workspace root pyproject.toml and the single shared uv.lock, not just this
# subdirectory. See docs/superpowers/plans/2026-09-23-mcp-integration-implementation.md
# Task 6 for why.
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

WORKDIR /app
COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package mcp-integration --no-dev

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/mcp_integration

EXPOSE 8000

CMD ["python", "filesystem_mcp_server.py"]
```

- [ ] **Step 2: Write `mcp_integration/docker-compose.yml`**

```yaml
services:
  filesystem-mcp-server:
    build:
      context: ..
      dockerfile: mcp_integration/Dockerfile
    container_name: filesystem-mcp-server
    ports:
      - "${MCP_PORT:-8000}:${MCP_PORT:-8000}"
    env_file:
      - .env
    environment:
      - MCP_HOST=0.0.0.0
    volumes:
      - ./sample_data:/app/mcp_integration/sample_data
    healthcheck:
      test: ["CMD", "python", "-c", "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"MCP_PORT\",\"8000\")}/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped
```

The bind mount is deliberate, not a named volume: the point is host visibility of anything `write_file`/`batch_process` produce (for grading/demo), and persistence across rebuilds, matching spec §10.

- [ ] **Step 3: Write `/.dockerignore`** (repo root)

```
.venv/
**/__pycache__/
**/*.pyc
.git/
.env
**/.env
mcp_integration/tests/
mcp_integration/docs/
```

- [ ] **Step 4: Build and run, verify the health check**

```bash
cd mcp_integration
docker compose up --build -d
docker compose ps   # STATUS should reach "healthy" within ~20s
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`. If the image build fails on `uv sync --package mcp-integration`, confirm the package name in `mcp_integration/pyproject.toml`'s `[project] name` is exactly `mcp-integration` (uv normalizes underscores to hyphens for `--package` matching).

- [ ] **Step 5: Verify a real tool call through the containerized server**

```bash
curl -s http://localhost:8000/mcp -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_files","arguments":{"directory":"."}}}'
docker compose down
```

Expected: a JSON-RPC result listing the `sample_data/resumes` tree (bind-mounted from the host).

- [ ] **Step 6: Commit**

```bash
git add mcp_integration/Dockerfile mcp_integration/docker-compose.yml .dockerignore
git commit -m "feat(mcp_integration): add Docker packaging for the filesystem MCP server"
```

---

### Task 7: Streaming spike — validate `stream_events(version="v3")` under an async `MCPAdapter` session

**Files:**
- No files committed by this task. It produces a decision that Task 8 depends on. Run the spike script from the scratchpad directory, not the repo.

**Interfaces:**
- Consumes: the running Docker server from Task 6 (`http://localhost:8000/mcp`), `config.settings`.
- Produces: a documented decision — which of two candidate call shapes to use for `stream_assistant_reply` in Task 8.

Spec §9 flags this explicitly as unresolved: does `agent.stream_events(..., version="v3")`'s typed-projection iterator support `async for ... in stream.interleave(...)` cleanly when tool calls route through an open async `MCPAdapter` session, or does it need the `astream_events` async entry point instead? This task answers that before Task 8 is built on top of an assumption.

- [ ] **Step 1: Start the server** (Task 6's container, or `uv run python filesystem_mcp_server.py` locally)

```bash
cd mcp_integration
docker compose up -d
```

- [ ] **Step 2: Write the spike script** to the scratchpad directory (not the repo) as `streaming_spike.py`

```python
import asyncio
import sys

sys.path.insert(0, ".")  # run from mcp_integration/ so config.py resolves

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.mcp import MCPAdapter
from langchain.messages import HumanMessage

from config import settings


async def main():
    async with MCPAdapter(settings.MCP_SERVER_URL) as adapter:
        tools = await adapter.list_tools()
        print(f"discovered {len(tools)} tools: {[t.name for t in tools]}")

        agent = create_agent(
            model=init_chat_model(model="openai/gpt-oss-120b", model_provider="openrouter"),
            tools=tools,
        )

        # --- Variant A: sync-looking call, async-iterated ---
        try:
            stream = agent.stream_events(
                input={"messages": [HumanMessage(content="List every file under the sandbox root.")]},
                config={"configurable": {"thread_id": "spike-a"}},
                version="v3",
            )
            async for kind, item in stream.interleave("messages"):
                pass
            print("Variant A (agent.stream_events + async for) WORKS")
            print("final output:", stream.output)
            return
        except TypeError as exc:
            print(f"Variant A failed: {exc}")

        # --- Variant B: async entry point ---
        stream = await agent.astream_events(
            input={"messages": [HumanMessage(content="List every file under the sandbox root.")]},
            config={"configurable": {"thread_id": "spike-b"}},
            version="v3",
        )
        async for kind, item in stream.interleave("messages"):
            pass
        print("Variant B (await agent.astream_events + async for) WORKS")
        print("final output:", stream.output)


asyncio.run(main())
```

- [ ] **Step 3: Run it against a real `OPENROUTER_API_KEY`**

```bash
cd mcp_integration
uv run python /path/to/scratchpad/streaming_spike.py
```

- [ ] **Step 4: Record the decision**

Whichever variant prints "WORKS", that is the call shape Task 8's `stream_assistant_reply` uses. If neither works as written, the error message from the attempt (a `TypeError`, an `AttributeError`, or a hang) determines the actual fix — check the installed `langchain` version's exact API with `uv run python -c "from langgraph.graph.state import CompiledStateGraph; help(CompiledStateGraph.stream_events)"` and adjust Task 8 accordingly before starting it. Discard the spike script; it isn't a repo deliverable.

---

### Task 8: `matching_agent.py` — async MCP client agent + REPL

**Files:**
- Create: `mcp_integration/matching_agent.py`
- Delete: `mcp_integration/main.py`
- Create: `mcp_integration/tests/test_matching_agent_mcp.py`

**Interfaces:**
- Consumes: `config.settings.MCP_SERVER_URL` (Task 1), `filesystem_mcp_server.mcp`/`.settings`/`.health` (Tasks 3-6, via the test fixture only — the agent itself never imports the server module), `langchain.mcp.MCPAdapter`, and Task 7's decision for which `stream_events` call shape to use.
- Produces: `matching_agent.build_chat_model() -> BaseChatModel`, `matching_agent.build_assistant_agent(tools: Sequence[BaseTool], model: BaseChatModel | None = None) -> CompiledStateGraph`, `matching_agent.build_thread_config(thread_id: str = DEFAULT_THREAD_ID) -> RunnableConfig`, `async def matching_agent.run_chat_loop(agent, config, console) -> None`, `async def matching_agent.stream_assistant_reply(agent, config, user_message, console, *, show_reasoning) -> None`, `async def matching_agent.main() -> None`. Re-exports `HumanMessage`/`ToolMessage`/`AIMessage` at module level (imported from `langchain.messages`) for the test in this task to reuse.

- [ ] **Step 1: Write `matching_agent.py`**

(This uses Variant A's call shape from Task 7 — `async for kind, item in stream.interleave("messages")` directly on `agent.stream_events(...)`. If Task 7 found Variant B necessary instead, replace the `stream = agent.stream_events(...)` line in `stream_assistant_reply` below with `stream = await agent.astream_events(...)` before running this task's tests.)

```python
"""Terminal chat client for the MCP-backed filesystem assistant -- Part B deliverable.

Same REPL shape as llm_file_assistant/main.py, but every filesystem
capability comes from an MCP server (filesystem_mcp_server.py) discovered
through langchain.mcp.MCPAdapter -- no direct fs_tools/fs_core import here.
"""

import asyncio
from typing import Any, Iterator, Sequence, cast

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.mcp import MCPAdapter
from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ReasoningContentBlock,
    RemoveMessage,
    TextContentBlock,
    ToolMessage,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.chat_model_stream import ChatModelStream
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph

from config import settings

MODEL_NAME = "openai/gpt-oss-120b"
MODEL_PROVIDER = "openrouter"
SYSTEM_PROMPT = (
    "You are the Resume Filing Clerk, an assistant that manages a folder of candidate "
    "resumes on behalf of a hiring team, through a filesystem MCP server. All resumes "
    "live under a single sandboxed root, organized into role subfolders such as "
    "engineering/, marketing/, sales/, design/, and data/. Resumes may be .txt, .docx, "
    "or .pdf. Every filesystem capability you have comes from the MCP tools discovered "
    "at startup: list_files, read_file, search_in_file, write_file, batch_process, "
    "start_watch, poll_watch, and stop_watch. Use batch_process to read many files at "
    "once instead of calling read_file in a loop. Use start_watch/poll_watch/stop_watch "
    "only when the user asks you to monitor a directory for new files -- poll_watch "
    "must be called repeatedly to see new events, it does not block.\n\n"
    "Always explore before acting: list files before you read or search them, and read "
    "the actual resume text before describing a candidate's skills or experience -- "
    "never invent details about a candidate you haven't read. When you write a file, "
    "say exactly which file you created and which source resumes it's based on. Be "
    "concise and accurate; if something isn't in the resumes you've read, say you don't "
    "know instead of guessing."
)
DEFAULT_THREAD_ID = "thread_001"
SHOW_REASONING_DEFAULT = False


# --- Agent setup -------------------------------------------------------------

def build_chat_model() -> BaseChatModel:
    return init_chat_model(model=MODEL_NAME, model_provider=MODEL_PROVIDER)


def build_assistant_agent(tools: Sequence[BaseTool], model: BaseChatModel | None = None) -> CompiledStateGraph:
    return create_agent(
        model=model or build_chat_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=list(tools),
        checkpointer=InMemorySaver(),
        name="assistant_agent",
    )


def build_thread_config(thread_id: str = DEFAULT_THREAD_ID) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


# --- Message content helpers (unchanged from llm_file_assistant/main.py) ---

def _split_message_blocks(message: AnyMessage) -> tuple[str, str]:
    content = message.content
    if isinstance(content, str):
        return "", content

    reasoning_parts: list[str] = []
    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block["type"] == "reasoning":
            reasoning_parts.append(cast(ReasoningContentBlock, block).get("reasoning", ""))
        elif block["type"] == "text":
            text_parts.append(cast(TextContentBlock, block).get("text", ""))
    return "".join(reasoning_parts), "".join(text_parts)


def render_history(console: Console, messages: Sequence[AnyMessage], *, show_reasoning: bool) -> None:
    if not messages:
        console.print(Panel("[yellow]No chat history found.[/yellow]", border_style="yellow"))
        return

    for message in messages:
        if isinstance(message, HumanMessage):
            _, text = _split_message_blocks(message)
            if text:
                console.print(Panel(text, title="You", border_style="cyan"))
        elif isinstance(message, AIMessage):
            reasoning_text, text = _split_message_blocks(message)
            if show_reasoning and reasoning_text:
                console.print(Panel(reasoning_text, title="Reasoning", border_style="magenta", style="dim italic"))
            if text:
                console.print(Panel(Markdown(text), title="Assistant", border_style="green"))
            for tool_call in message.tool_calls or []:
                console.print(f"[dim]Tool call: {tool_call['name']}({tool_call['args']})[/dim]")
        elif isinstance(message, ToolMessage):
            _, text = _split_message_blocks(message)
            console.print(f"[dim]Tool result ({message.name}): {text}[/dim]")


# --- Thread history operations ----------------------------------------------

def get_history(agent: CompiledStateGraph, config: RunnableConfig) -> list[AnyMessage]:
    return agent.get_state(config).values.get("messages", [])


async def clear_history(agent: CompiledStateGraph, config: RunnableConfig) -> None:
    await agent.aupdate_state(config, {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]})


# --- Streaming reply ----------------------------------------------------------

def _iter_message_deltas(item: ChatModelStream) -> Iterator[tuple[str, Any]]:
    for event in item:
        if event.get("event") != "content-block-delta":
            continue
        delta = event.get("delta") or {}
        delta_type = delta.get("type")
        if delta_type == "reasoning-delta":
            yield "reasoning", delta.get("reasoning", "")
        elif delta_type == "text-delta":
            yield "text", delta.get("text", "")
        elif delta_type == "block-delta":
            fields = delta.get("fields") or {}
            if fields.get("type") == "tool_call_chunk":
                yield "tool_call", fields


def _render_tool_calls(tool_call_buffers: dict[int, dict[str, str]]) -> list[Panel]:
    panels = []
    for buf in tool_call_buffers.values():
        name = buf.get("name") or "..."
        args = buf.get("args") or ""
        panels.append(Panel(f"{name}({args})", title="Tool Call", border_style="yellow", style="dim"))
    return panels


def _render_turn(reasoning_text: str, assistant_text: str, tool_call_buffers: dict[int, dict[str, str]] | None = None) -> Group:
    renderables = []
    if reasoning_text:
        renderables.append(Panel(reasoning_text, title="Reasoning", border_style="magenta", style="dim italic"))
    renderables.extend(_render_tool_calls(tool_call_buffers or {}))
    renderables.append(Panel(Markdown(assistant_text or "..."), title="Assistant", border_style="green"))
    return Group(*renderables)


async def stream_assistant_reply(
    agent: CompiledStateGraph,
    config: RunnableConfig,
    user_message: str,
    console: Console,
    *,
    show_reasoning: bool,
) -> None:
    """Streams the assistant's reply for a single user turn, live-updating the console.

    Async so it shares the event loop with the open MCPAdapter session --
    tool calls the agent makes round-trip through that session while this
    coroutine is still iterating the stream.
    """
    stream = agent.stream_events(
        input={"messages": [HumanMessage(content=user_message)]},
        config=config,
        version="v3",
    )

    reasoning_buffer = ""
    assistant_text_buffer = ""
    tool_call_buffers: dict[int, dict[str, str]] = {}
    console.print()

    with Live(_render_turn("", "", tool_call_buffers), refresh_per_second=10, console=console) as live:
        async for kind, item in stream.interleave("messages"):
            if kind != "messages":
                continue
            for delta_kind, delta in _iter_message_deltas(item):
                if delta_kind == "reasoning":
                    if not show_reasoning:
                        continue
                    reasoning_buffer += delta
                elif delta_kind == "text":
                    assistant_text_buffer += delta
                elif delta_kind == "tool_call":
                    index = delta.get("index", 0)
                    buf = tool_call_buffers.setdefault(index, {"name": "", "args": ""})
                    if delta.get("name"):
                        buf["name"] = delta["name"]
                    if delta.get("args") is not None:
                        buf["args"] = delta["args"]
                live.update(_render_turn(reasoning_buffer, assistant_text_buffer, tool_call_buffers))

        stream.output  # Drive the run to completion


# --- REPL ----------------------------------------------------------------------

async def run_chat_loop(agent: CompiledStateGraph, config: RunnableConfig, console: Console) -> None:
    show_reasoning = SHOW_REASONING_DEFAULT

    console.print(Panel(
        "[bold green]Chat started![/bold green] Type 'exit' or 'quit' to end.\n"
        "[yellow]Type 'clear' to clear chat history, 'load' to show previous history, "
        "'reasoning' to toggle showing the model's reasoning.[/yellow]",
        title="MCP Filesystem Chat", border_style="cyan",
    ))

    while True:
        raw_input = await asyncio.to_thread(console.input, "\n[bold blue]You:[/bold blue] ")
        user_message = raw_input.strip()

        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit"}:
            console.print(Panel("[yellow]Chat ended.[/yellow]", border_style="yellow"))
            break
        if user_message.lower() == "clear":
            await clear_history(agent, config)
            console.print(Panel("[bold yellow]Chat history cleared![/bold yellow]", border_style="yellow"))
            continue
        if user_message.lower() == "load":
            render_history(console, get_history(agent, config), show_reasoning=show_reasoning)
            continue
        if user_message.lower() == "reasoning":
            show_reasoning = not show_reasoning
            status = "on" if show_reasoning else "off"
            console.print(Panel(f"[bold yellow]Reasoning display turned {status}.[/bold yellow]", border_style="yellow"))
            continue

        await stream_assistant_reply(agent, config, user_message, console, show_reasoning=show_reasoning)


async def main() -> None:
    console = Console()
    async with MCPAdapter(settings.MCP_SERVER_URL) as adapter:
        tools = await adapter.list_tools()
        agent = build_assistant_agent(tools)
        config = build_thread_config()
        try:
            await run_chat_loop(agent, config, console)
        except KeyboardInterrupt:
            console.print("\n[bold red]Exiting...[/bold red]")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Delete the placeholder entrypoint**

```bash
rm mcp_integration/main.py
```

- [ ] **Step 3: Write the failing test**

```python
# mcp_integration/tests/test_matching_agent_mcp.py
import threading
import time

import httpx
import pytest
import uvicorn
from langchain.mcp import MCPAdapter
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

import filesystem_mcp_server as server
import matching_agent

TEST_PORT = 8766


@pytest.fixture(scope="module")
def running_server(tmp_path_factory):
    sandbox = tmp_path_factory.mktemp("mcp_agent_sandbox")
    (sandbox / "note.txt").write_text("hello from the sandbox", encoding="utf-8")
    server.settings.ROOT_DIR = sandbox

    app = server.mcp.http_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10
    started = False
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{TEST_PORT}/health", timeout=1).status_code == 200:
                started = True
                break
        except httpx.ConnectError:
            time.sleep(0.2)
    if not started:
        raise RuntimeError("Test MCP server did not start in time")

    yield f"http://127.0.0.1:{TEST_PORT}/mcp"

    uv_server.should_exit = True
    thread.join(timeout=5)


async def test_agent_discovers_and_calls_mcp_tool(running_server):
    fake_model = FakeMessagesListChatModel(responses=[
        matching_agent.AIMessage(
            content="",
            tool_calls=[{"name": "list_files", "args": {"directory": "."}, "id": "call_1"}],
        ),
        matching_agent.AIMessage(content="I found one file: note.txt."),
    ])

    async with MCPAdapter(running_server) as adapter:
        tools = await adapter.list_tools()
        names = {t.name for t in tools}
        assert "list_files" in names
        assert "batch_process" in names
        assert "start_watch" in names

        agent = matching_agent.build_assistant_agent(tools, model=fake_model)
        config = matching_agent.build_thread_config("test-thread")

        result = await agent.ainvoke(
            {"messages": [matching_agent.HumanMessage(content="what files are there?")]},
            config=config,
        )

    final = result["messages"][-1]
    assert "note.txt" in final.content

    tool_messages = [m for m in result["messages"] if isinstance(m, matching_agent.ToolMessage)]
    assert tool_messages, "expected the fake model's tool call to round-trip through the real MCP server"
```

- [ ] **Step 4: Run the test to verify it fails**

```bash
cd mcp_integration
uv run pytest tests/test_matching_agent_mcp.py -v
```

Expected: `ModuleNotFoundError: No module named 'matching_agent'` before Step 1/2 above are applied, or a real assertion failure if something in the agent wiring is off once they are.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_matching_agent_mcp.py -v
```

Expected: `PASS`. If `FakeMessagesListChatModel` doesn't accept `.bind_tools()` cleanly under the installed `langchain-core` version, check `uv run python -c "from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel; help(FakeMessagesListChatModel)"` and adjust the fixture.

- [ ] **Step 6: Manual end-to-end run** (requires a real `OPENROUTER_API_KEY` in `.env` and the Docker server from Task 6 running)

```bash
docker compose up -d
uv run python matching_agent.py
```

In the REPL: ask "what resumes do we have in engineering?", confirm tool-call panels and a real streamed answer appear; try `reasoning`, `load`, `clear`, `exit`.

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests across all four files `PASS`.

- [ ] **Step 8: Commit**

```bash
git add mcp_integration/matching_agent.py mcp_integration/tests/test_matching_agent_mcp.py
git rm mcp_integration/main.py
git commit -m "feat(mcp_integration): add matching_agent.py, an async MCP-client REPL"
```

---

### Task 9: Docs & polish

**Files:**
- Create: `mcp_integration/docs/architecture.md`
- Create: `mcp_integration/docs/workflow-diagram.md`
- Create: `mcp_integration/docs/demo-script.md`
- Modify: `mcp_integration/README.md`

**Interfaces:**
- Consumes: the finished system from Tasks 1-8. No code interfaces — this task only produces documentation.

- [ ] **Step 1: Write `docs/architecture.md`**

```markdown
# Architecture

Two processes, one sandboxed data directory:

\`\`\`
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
\`\`\`

- **`matching_agent.py`** -- a `create_agent`-built LangGraph agent with an
  `InMemorySaver` checkpointer, run through a Rich-based terminal REPL. Holds
  no direct filesystem access; every tool it can call comes from
  `MCPAdapter(settings.MCP_SERVER_URL).list_tools()` at startup.
- **`filesystem_mcp_server.py`** -- a `FastMCP` server exposing 8 tools
  (`list_files`, `read_file`, `search_in_file`, `write_file`, `batch_process`,
  `start_watch`, `poll_watch`, `stop_watch`) plus a `/health` route, over
  Streamable HTTP. Runs in Docker; the container publishes `MCP_PORT` to the
  host.
- **`fs_core.py`** -- pure, undecorated filesystem and watch-state logic
  (path sandboxing, text extraction, background watch threads). Has no
  dependency on MCP or LangChain, so it's testable directly.
- **`config.py`** -- a plain `Settings` class reading `.env`/environment
  variables, shared by both processes (though each process only reads the
  settings relevant to it: the server binds `MCP_HOST`/`MCP_PORT` and enforces
  `ROOT_DIR`/`ALLOWED_EXTENSIONS`/etc.; the agent only reads `MCP_SERVER_URL`
  and `OPENROUTER_API_KEY`).
- **`sample_data/resumes/`** -- copied from `llm_file_assistant/root_dir`,
  bind-mounted into the container so agent-written files are visible on the
  host.
```

- [ ] **Step 2: Write `docs/workflow-diagram.md`**

```markdown
# Workflow: one agent <-> MCP interaction

\`\`\`mermaid
stateDiagram-v2
    [*] --> Discovery
    Discovery: MCPAdapter connects, calls list_tools()
    Discovery --> AgentReady: tools registered on the LangGraph agent

    AgentReady --> ModelTurn: user sends a message
    ModelTurn: chat model decides to call a tool
    ModelTurn --> ToolCall: AIMessage with tool_calls

    ToolCall --> MCPRoundTrip: MCPAdapter sends tools/call over Streamable HTTP
    MCPRoundTrip --> ServerFilesystemOp: filesystem_mcp_server.py's @mcp.tool runs
    ServerFilesystemOp --> StructuredResult: {success, ..., error} dict returned
    StructuredResult --> ToolMessage: MCPAdapter wraps it as a ToolMessage

    ToolMessage --> ModelTurn: agent loop continues with the tool result
    ModelTurn --> FinalAnswer: model responds with no further tool_calls
    FinalAnswer --> [*]
\`\`\`

Every arrow from `ToolCall` through `ToolMessage` is visible live in the REPL
via the existing `Tool call: {name}({args})` / `Tool result (...)` panels --
no bespoke MCP-event plumbing was needed for this.
```

- [ ] **Step 3: Write `docs/demo-script.md`**

```markdown
# Demo script

Mapped to the assignment's suggested 9-step sequence.

1. **Architecture intro** -- show `docs/architecture.md`'s diagram; explain
   the two-process split and why the server is dockerized but the agent isn't.
2. **Server config & startup** -- show `.env`, then `docker compose up --build`;
   point out the healthcheck reaching "healthy".
3. **Discovery** -- `curl .../mcp` `tools/list`, or the
   `test_discovery_includes_migrated_tools` test, showing all 8 tools with
   their generated schemas.
4. **A migrated op** -- ask the agent "what's in engineering/backend_alice.txt?";
   show the `read_file` tool-call panel and the extracted content.
5. **`batch_process`** -- ask the agent to summarize every engineering resume
   at once; show the aggregate `{total_files, processed, failed, skipped}`
   counts in the tool result panel.
6. **`watch_directory`** -- ask the agent to watch `sales/` for new resumes;
   drop a new file into `sample_data/resumes/sales/` from a second terminal;
   ask the agent to check for updates and show it picking up the new file via
   `poll_watch`.
7. **Full agent run** -- a multi-turn conversation exercising `list_files` ->
   `search_in_file` -> `write_file` (e.g. "find everyone who knows Python and
   write a shortlist").
8. **Results, logs, tests** -- `uv run pytest tests/ -v` (all green); show the
   `CustomLogger` output in the server container's logs
   (`docker compose logs -f`).
9. **Scope note** -- state explicitly that the bonus multi-MCP integration was
   not implemented (spec §13), and why (time-boxed to the core two-part
   assignment).
```

- [ ] **Step 4: Rewrite `README.md`**

```markdown
# MCP Integration

An MCP-based rebuild of `llm_file_assistant`'s filesystem tooling: the
sandboxed file tools move out of a directly-imported LangChain tool module
and behind a standalone **Filesystem MCP Server**, and the chat agent
(**`matching_agent.py`**) is refactored to discover and call those tools
exclusively through an MCP client -- no direct filesystem access from the
agent's primary path.

Two processes:

\`\`\`
matching_agent.py (LangGraph agent + REPL, host)
        |  langchain.mcp.MCPAdapter, MCP over Streamable HTTP
        v
filesystem_mcp_server.py (FastMCP, Docker)
        |
        v
sample_data/resumes/
\`\`\`

Full design rationale, tool specs, error handling, and the phased
implementation plan live in [`docs/spec.md`](docs/spec.md);
[`docs/architecture.md`](docs/architecture.md) and
[`docs/workflow-diagram.md`](docs/workflow-diagram.md) cover the runtime
picture in more depth.

## Prerequisites

- Python >= 3.12
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run the MCP server)
- An [OpenRouter](https://openrouter.ai/) API key (agent side)

## Setup

\`\`\`bash
cp sample.env .env
# fill in OPENROUTER_API_KEY (and optionally LANGSMITH_*) in .env
uv sync
\`\`\`

## Running

Start the MCP server (Docker):

\`\`\`bash
docker compose up --build
\`\`\`

In a second terminal, run the agent (always on the host):

\`\`\`bash
uv run python matching_agent.py
\`\`\`

REPL commands: `clear` (wipe chat history), `load` (show previous history),
`reasoning` (toggle showing the model's reasoning), `exit`/`quit`.

## Testing

\`\`\`bash
uv run pytest tests/ -v
\`\`\`

`tests/test_mcp_server.py`, `test_batch_process.py`, and
`test_watch_directory.py` run against the `FastMCP` server in-process (no
Docker needed). `tests/test_matching_agent_mcp.py` spins up a real local HTTP
instance of the server and connects to it through `MCPAdapter`, with the chat
model stubbed -- no live `OPENROUTER_API_KEY` required to run the suite.

## Repository layout

See [`docs/spec.md`](docs/spec.md) §3.
```

- [ ] **Step 5: Commit**

```bash
git add mcp_integration/docs/architecture.md mcp_integration/docs/workflow-diagram.md \
        mcp_integration/docs/demo-script.md mcp_integration/README.md
git commit -m "docs(mcp_integration): add architecture/workflow/demo docs, finish README"
```

---

## Plan self-review

**Spec coverage:**
- §2 Architecture -> Task 9 (`docs/architecture.md`), realized by Tasks 3-8.
- §3 Repository layout -> Tasks 1-9 collectively; the one deviation (`.dockerignore` at repo root, no per-project `.gitignore`) is called out explicitly in Task 6 and the layout note above spec's literal listing.
- §4 Config management -> Task 1.
- §5 Migrated tools -> Task 3.
- §6 `batch_process` -> Task 4 (aggregate-count invariant `processed + failed + skipped == total_files` asserted directly in the test).
- §7 `watch_directory` -> Task 5.
- §8 Error handling -> every code produced across Tasks 3-5; explicitly walked in Task 5 Step 6.
- §9 Agent MCP integration -> Tasks 7 (the flagged open question) and 8.
- §10 Docker packaging -> Task 6.
- §11 Testing -> all four files built inline with Tasks 3, 4, 5, 8 (TDD, not deferred).
- §12 Docs & demo artifacts -> Task 9.
- §13 Out of scope -> respected throughout; no bonus/auth/RAG code anywhere in this plan.
- §14 Phased plan -> mapped 1:1 onto Tasks 1-9 (phase 4 "error-handling hardening" folded into Task 5 Step 6 rather than a standalone task, since the codes are produced as part of each tool's own task and only need verifying once, not re-implementing).

**Placeholder scan:** no "TBD"/"add error handling"/"similar to Task N" phrasing anywhere; every step has runnable code or a concrete shell command.

**Type consistency:** `fs_core.resolve_within_root/extract_text/file_metadata/is_allowed_extension/exceeds_max_size` (Task 2) are the exact names used by `filesystem_mcp_server.py` (Task 3), `batch_process` (Task 4), and `fs_core`'s own watch functions (Task 5). `filesystem_mcp_server.mcp` (Task 3) is the exact name imported in Tasks 4, 5, 6 (Docker `CMD`), and both test fixtures in Tasks 5/8 that spin up a real HTTP instance. `matching_agent.build_assistant_agent(tools, model=None)`'s signature (Task 8) matches its only two call sites: `main()` in the same file, and `test_agent_discovers_and_calls_mcp_tool` in `test_matching_agent_mcp.py`.
