import threading
import time
from typing import Any

import httpx
import pytest
import uvicorn
from langchain.mcp import MCPAdapter
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import Runnable

import filesystem_mcp_server as server
import matching_agent

TEST_PORT = 8766


class _FakeToolCallingModel(FakeMessagesListChatModel):
    """`FakeMessagesListChatModel` with a working `bind_tools`.

    The base class's `bind_tools` is unimplemented (it raises
    `NotImplementedError` -- there is no real provider to format a tool
    schema for). This test doesn't need tool-schema formatting, only a
    model that returns its canned responses regardless of which tools
    `create_agent` binds, so `bind_tools` is a no-op that returns `self`.
    """

    def bind_tools(self, tools: Any, *, tool_choice: str | None = None, **kwargs: Any) -> Runnable:
        del tools, tool_choice, kwargs
        return self


@pytest.fixture(scope="module")
def running_server(tmp_path_factory):
    sandbox = tmp_path_factory.mktemp("mcp_agent_sandbox")
    (sandbox / "note.txt").write_text("hello from the sandbox", encoding="utf-8")
    original_root_dir = server.settings.ROOT_DIR
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
    server.settings.ROOT_DIR = original_root_dir


async def test_agent_discovers_and_calls_mcp_tool(running_server):
    fake_model = _FakeToolCallingModel(responses=[
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
