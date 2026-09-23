"""Terminal chat client for the MCP-backed filesystem assistant -- Part B deliverable.

Same REPL shape as llm_file_assistant/main.py, but every filesystem
capability comes from an MCP server (filesystem_mcp_server.py) discovered
through langchain.mcp.MCPAdapter -- no direct fs_tools/fs_core import here.
"""

import asyncio
from typing import Any, AsyncIterator, Sequence, cast

import truststore

# Some sandboxes' default TLS trust store can't verify OpenRouter's cert
# chain even though outbound network access is fine (see task-7-report.md).
# Repointing SSL verification at the OS trust store is a no-op everywhere
# else, so it's safe to do unconditionally rather than guessing at CI.
truststore.inject_into_ssl()

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
from langchain_core.language_models.chat_model_stream import AsyncChatModelStream
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
#
# NOTE on the streaming call shape: the brief's literal reference code used
# `stream = agent.stream_events(..., version="v3")` followed by
# `async for kind, item in stream.interleave("messages")`. Task 7's live spike
# (see task-7-report.md) found this fails -- `GraphRunStream.interleave()` is
# a plain sync generator with no `__aiter__`, so `async for` over it is a
# TypeError by construction. The async entry point (`astream_events`) returns
# an `AsyncGraphRunStream`, which has no `.interleave()` at all -- it exposes
# named async projections instead (`.messages`, `.values`, `.tool_calls`, ...).
#
# This module's own live exploration (against the real Docker MCP server and
# a real OpenRouter call) confirmed: `async for handle in stream.messages`
# yields one `AsyncChatModelStream` per LLM turn (matching the brief's
# `ChatModelStream` one-for-one, just async), and `async for event in handle`
# yields the identical raw `content-block-delta` event dicts the sync
# `_iter_message_deltas` parsed -- same `reasoning-delta` / `text-delta` /
# `block-delta` (tool_call_chunk) shapes, since both flavors share the same
# `dispatch()` logic in `langchain_core.language_models.chat_model_stream`.
# So `_iter_message_deltas` below is the brief's function made async, with no
# change to its parsing logic. The top-level stream's `.output` is an async
# method on this class (`await stream.output()`), not the bare property the
# sync `GraphRunStream.output` is -- it must be called, not just referenced.


async def _iter_message_deltas(item: AsyncChatModelStream) -> AsyncIterator[tuple[str, Any]]:
    async for event in item:
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
    stream = await agent.astream_events(
        input={"messages": [HumanMessage(content=user_message)]},
        config=config,
        version="v3",
    )

    reasoning_buffer = ""
    assistant_text_buffer = ""
    tool_call_buffers: dict[int, dict[str, str]] = {}
    console.print()

    with Live(_render_turn("", "", tool_call_buffers), refresh_per_second=10, console=console) as live:
        async for item in stream.messages:
            async for delta_kind, delta in _iter_message_deltas(item):
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

        await stream.output()  # Drive the run to completion


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
