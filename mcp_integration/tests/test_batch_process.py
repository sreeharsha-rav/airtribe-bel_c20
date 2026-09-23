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
