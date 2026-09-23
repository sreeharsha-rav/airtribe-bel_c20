from pathlib import Path

import pytest
from fastmcp import Client

import filesystem_mcp_server as server
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


def test_resolve_within_root_rejects_path_resolving_outside_root(sandbox, monkeypatch):
    # A syntactically clean relative path (no "..", not absolute) should still
    # be rejected if it resolves outside the sandbox root -- e.g. via a
    # symlink. Real symlinks are awkward to create reliably on Windows
    # without elevated privileges, so we monkeypatch Path.resolve to simulate
    # that outcome and exercise the post-resolve containment check directly.
    original_resolve = Path.resolve

    def fake_resolve(self, *args, **kwargs):
        if self == sandbox / "innocuous.txt":
            return Path("/definitely/outside")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("innocuous.txt")


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
    # /health is a plain HTTP route, not an MCP tool -- exercised via
    # Docker's healthcheck in Task 6, not the MCP client here. This test
    # just confirms the route function itself returns the right body.
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


async def test_list_files_rejects_non_directory_path(server_sandbox):
    async with Client(server.mcp) as client:
        result = await client.call_tool("list_files", {"directory": "notes.txt"})
    assert result.data[0]["success"] is False
    assert result.data[0]["error"]["code"] == "VALIDATION_ERROR"


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


async def test_write_file_permission_denied_on_os_error(server_sandbox, monkeypatch):
    original_write_text = Path.write_text

    def fake_write_text(self, *args, **kwargs):
        if self == server_sandbox / "blocked.txt":
            raise OSError("simulated disk error")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    async with Client(server.mcp) as client:
        result = await client.call_tool("write_file", {"filepath": "blocked.txt", "content": "data"})

    assert result.data["success"] is False
    assert result.data["error"]["code"] == "PERMISSION_DENIED"
