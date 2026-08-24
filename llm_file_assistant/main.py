"""Terminal chat client for a LangChain agent with in-memory, per-thread history."""

from typing import Sequence

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph

MODEL_NAME = "openai/gpt-oss-120b"
MODEL_PROVIDER = "openrouter"
SYSTEM_PROMPT = (
    "You are a helpful assistant, be concise and provide accurate information. "
    "If you don't know the answer, say 'I don't know' instead of making up an answer."
)
DEFAULT_THREAD_ID = "thread_001"


# --- Agent setup -------------------------------------------------------------

def build_chat_model() -> BaseChatModel:
    return init_chat_model(model=MODEL_NAME, model_provider=MODEL_PROVIDER)


def build_assistant_agent(model: BaseChatModel | None = None) -> CompiledStateGraph:
    return create_agent(
        model=model or build_chat_model(),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
        name="assistant_agent",
    )


def build_thread_config(thread_id: str = DEFAULT_THREAD_ID) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


# --- History rendering ---------------------------------------------------------

def _message_text(message: AnyMessage) -> str:
    """Extracts displayable text from a message's content (str or content-block list)."""
    content = message.content
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") in ("text", "output_text", "reasoning"):
                parts.append(block.get("text", ""))
        else:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
    return "".join(parts)


def render_history(console: Console, messages: Sequence[AnyMessage]) -> None:
    """Renders an agent thread's message history to the console."""
    if not messages:
        console.print(Panel("[yellow]No chat history found.[/yellow]", border_style="yellow"))
        return

    for message in messages:
        if isinstance(message, HumanMessage):
            text = _message_text(message)
            if text:
                console.print(Panel(text, title="You", border_style="cyan"))

        elif isinstance(message, AIMessage):
            text = _message_text(message)
            if text:
                console.print(Panel(Markdown(text), title="Assistant", border_style="green"))
            for tool_call in message.tool_calls or []:
                console.print(f"[dim]Tool call: {tool_call['name']}({tool_call['args']})[/dim]")

        elif isinstance(message, ToolMessage):
            console.print(f"[dim]Tool result ({message.name}): {_message_text(message)}[/dim]")


# --- Thread history operations --------------------------------------------------

def get_history(agent: CompiledStateGraph, config: RunnableConfig) -> list[AnyMessage]:
    return agent.get_state(config).values.get("messages", [])


def clear_history(agent: CompiledStateGraph, config: RunnableConfig) -> None:
    agent.update_state(config, {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]})


# --- Streaming reply -----------------------------------------------------------

def stream_assistant_reply(
    agent: CompiledStateGraph,
    config: RunnableConfig,
    user_message: str,
    console: Console,
) -> None:
    """Streams the assistant's reply for a single user turn, live-updating the console."""
    stream = agent.stream_events(
        input={"messages": [HumanMessage(content=user_message)]},
        config=config,
        version="v3",
    )

    assistant_text_buffer = ""
    console.print()  # Add spacing

    with Live(Panel(Markdown("..."), title="Assistant", border_style="green"), refresh_per_second=10, console=console) as live:
        for kind, item in stream.interleave("messages"):
            if kind == "messages":
                for delta in item.text:
                    assistant_text_buffer += delta
                    live.update(Panel(Markdown(assistant_text_buffer), title="Assistant", border_style="green"))

            # FUTURE: Handle tool calls if needed
            # elif kind == "tool_calls":
            #     print(f"\nTool call: {item.tool_name}({item.input})")
            #     for delta in item.output_deltas:
            #         print(delta, end="", flush=True)
            #     print(f"\nTool result: {item.output}")

        stream.output  # Drive the run to completion


# --- REPL ------------------------------------------------------------------------

def run_chat_loop(agent: CompiledStateGraph, config: RunnableConfig, console: Console) -> None:
    console.print(Panel(
        "[bold green]Chat started![/bold green] Type 'exit' or 'quit' to end.\n"
        "[yellow]Type 'clear' to clear chat history, 'load' to show previous history.[/yellow]",
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
            render_history(console, get_history(agent, config))
            continue

        stream_assistant_reply(agent, config, user_message, console)


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
