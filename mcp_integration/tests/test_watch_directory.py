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
    # NOTE on timing constants: this test is inherently a little sensitive --
    # it relies on exactly one background scan cycle landing between each
    # pair of poll_watch calls below. poll_interval_seconds=0.2 with 0.3s
    # sleeps (a 1.5x margin) proved unreliable on this machine: fixed
    # per-call overhead (RPC round trips, thread scheduling) is a large
    # enough fraction of a 0.2s interval that two scans -- not one -- would
    # sometimes land in the same poll window, so both the "not ready" and
    # "ready" events showed up together. Using a larger poll interval with a
    # roughly 1.4x sleep margin (per the brief: widen the margin, don't
    # shrink the interval) makes that fixed overhead a much smaller fraction
    # of each window, so exactly one scan reliably lands in each.
    poll_interval_seconds = 0.5
    sleep_margin = 0.7

    async with Client(server.mcp) as client:
        started = await client.call_tool(
            "start_watch", {"directory_path": "watched", "poll_interval_seconds": poll_interval_seconds}
        )
        watch_id = started.data["watch_id"]
        assert started.data["success"] is True

        # Files present at start_watch time are snapshotted, not reported.
        time.sleep(sleep_margin)
        first_poll = await client.call_tool("poll_watch", {"watch_id": watch_id})
        assert first_poll.data["events"] == []

        (watch_sandbox / "watched" / "new_resume.txt").write_text("brand new", encoding="utf-8")

        time.sleep(sleep_margin)
        detected_poll = await client.call_tool("poll_watch", {"watch_id": watch_id})
        detected = [e for e in detected_poll.data["events"] if e.get("path") == "new_resume.txt"]
        assert len(detected) == 1
        assert detected[0]["ready"] is False

        time.sleep(sleep_margin)
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
