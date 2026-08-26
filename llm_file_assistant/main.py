"""Terminal chat client for a LangChain agent with in-memory, per-thread history."""

from typing import Any, Iterator, Sequence, cast

from dotenv import load_dotenv
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
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
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph

from fs_tools import keyword_search, list_directory, read_file, write_file

MODEL_NAME = "openai/gpt-oss-120b"
MODEL_PROVIDER = "openrouter"
SYSTEM_PROMPT = (
    "You are the Resume Filing Clerk, an assistant that manages a folder of candidate "
    "resumes on behalf of a hiring team. All resumes live under a single sandboxed "
    "directory (root_dir/), organized into role subfolders such as engineering/, "
    "marketing/, sales/, design/, and data/. You have four tools, and no other access "
    "to the filesystem:\n"
    "- list_directory(path): see what role folders and candidate files exist.\n"
    "- read_file(path): read one resume's full text.\n"
    "- keyword_search(query, path): find which resumes mention a skill or keyword.\n"
    "- write_file(path, content): create a new file, e.g. a shortlist or summary "
    "report. It will refuse to overwrite an existing file.\n\n"
    "Always explore before acting: list or search before you read, and read the "
    "actual resume text before describing a candidate's skills or experience — never "
    "invent details about a candidate you haven't read. When you write a file, say "
    "exactly which file you created and which source resumes it's based on. Be "
    "concise and accurate; if something isn't in the resumes you've read, say you "
    "don't know instead of guessing."
)
DEFAULT_THREAD_ID = "thread_001"
SHOW_REASONING_DEFAULT = False
TOOLS = [list_directory, read_file, keyword_search, write_file]


# --- Agent setup -------------------------------------------------------------

def build_chat_model() -> BaseChatModel:
    return init_chat_model(model=MODEL_NAME, model_provider=MODEL_PROVIDER)


def build_assistant_agent(model: BaseChatModel | None = None) -> CompiledStateGraph:
    return create_agent(
        model=model or build_chat_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        checkpointer=InMemorySaver(),
        name="assistant_agent",
    )


def build_thread_config(thread_id: str = DEFAULT_THREAD_ID) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


# --- Message content helpers ---------------------------------------------------

def _split_message_blocks(message: AnyMessage) -> tuple[str, str]:
    """Splits a message's content into (reasoning_text, text).

    Content is either a plain string (no reasoning) or a list of v1
    content blocks — `TextContentBlock` (`text`) and `ReasoningContentBlock`
    (`reasoning`) hold their text under different keys, so they can't be
    read with one shared field name.
    """
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
    """Renders an agent thread's message history to the console."""
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


# --- Thread history operations --------------------------------------------------

def get_history(agent: CompiledStateGraph, config: RunnableConfig) -> list[AnyMessage]:
    return agent.get_state(config).values.get("messages", [])


def clear_history(agent: CompiledStateGraph, config: RunnableConfig) -> None:
    agent.update_state(config, {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]})


# --- Streaming reply -----------------------------------------------------------

def _iter_message_deltas(item: ChatModelStream) -> Iterator[tuple[str, Any]]:
    """Yields ("reasoning" | "text" | "tool_call", delta) tuples from a message
    stream's raw `content-block-delta` events, in arrival order.

    `ChatModelStream.text`, `.reasoning`, and `.tool_calls` each only report
    done once the whole message finishes, so iterating one alone can't show
    reasoning, text, and tool calls live as they actually arrive relative to
    each other. Raw event iteration (documented on `ChatModelStream`)
    preserves arrival order across all three. A tool call in progress shows
    up as a `block-delta` whose `fields` carry a `tool_call_chunk` with
    `name`/`args`/`id`/`index`.
    """
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


def stream_assistant_reply(
    agent: CompiledStateGraph,
    config: RunnableConfig,
    user_message: str,
    console: Console,
    *,
    show_reasoning: bool,
) -> None:
    """Streams the assistant's reply for a single user turn, live-updating the console."""
    stream = agent.stream_events(
        input={"messages": [HumanMessage(content=user_message)]},
        config=config,
        version="v3",
    )

    reasoning_buffer = ""
    assistant_text_buffer = ""
    tool_call_buffers: dict[int, dict[str, str]] = {}
    console.print()  # Add spacing

    with Live(_render_turn("", "", tool_call_buffers), refresh_per_second=10, console=console) as live:
        for kind, item in stream.interleave("messages"):
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
                        # `args` arrives as the accumulated-so-far string, not an
                        # incremental fragment — replace rather than concatenate.
                        buf["args"] = delta["args"]
                live.update(_render_turn(reasoning_buffer, assistant_text_buffer, tool_call_buffers))

        stream.output  # Drive the run to completion


# --- REPL ------------------------------------------------------------------------

def run_chat_loop(agent: CompiledStateGraph, config: RunnableConfig, console: Console) -> None:
    show_reasoning = SHOW_REASONING_DEFAULT

    console.print(Panel(
        "[bold green]Chat started![/bold green] Type 'exit' or 'quit' to end.\n"
        "[yellow]Type 'clear' to clear chat history, 'load' to show previous history, "
        "'reasoning' to toggle showing the model's reasoning.[/yellow]",
        title="LangChain Chat", border_style="cyan",
    ))

    while True:
        user_message = console.input("\n[bold blue]You:[/bold blue] ").strip()

        if not user_message:
            continue

        if user_message.lower() in {"exit", "quit"}:
            console.print(Panel("[yellow]Chat ended.[/yellow]", border_style="yellow"))
            break

        if user_message.lower() == "clear":
            clear_history(agent, config)
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

        stream_assistant_reply(agent, config, user_message, console, show_reasoning=show_reasoning)


def main() -> None:
    load_dotenv()
    console = Console()
    agent = build_assistant_agent()
    config = build_thread_config()

    try:
        run_chat_loop(agent, config, console)
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting...[/bold red]")


if __name__ == "__main__":
    main()
