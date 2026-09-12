"""Terminal entrypoint: collects the upfront JD path + deep-screening prompts,
runs matching_agent's compiled graph through Phase 1's one-shot pipeline, then
drives Phase 2's Human Feedback Loop through its interrupt()/Command(resume=...)
pause-and-continue cycle for the turn-by-turn conversation.

Run from agentic_profile_match/: `uv run python cli/main.py`.
"""

import sys
import uuid
from pathlib import Path

# cli/ is a plain (non-package-installed) directory -- when this file is run
# directly, Python puts only cli/ on sys.path, not the parent agentic_profile_match/
# where matching_agent.py and friends live. Adding it explicitly lets this
# script import them regardless of how it's invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from langchain.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from rich.markdown import Markdown
from rich.panel import Panel

from matching_agent import AgentState, build_graph, console


def _render_new_messages(messages: list[AnyMessage]) -> None:
    """Renders the Human Feedback Loop's newly-appended messages for one turn
    (the human's own turn is skipped -- it's already visible as the "You:"
    prompt the human just typed).
    """
    for message in messages:
        if isinstance(message, HumanMessage):
            continue
        if isinstance(message, AIMessage):
            text = message.content if isinstance(message.content, str) else "".join(
                block.get("text", "") for block in message.content if isinstance(block, dict) and block.get("type") == "text"
            )
            if text:
                console.print(Panel(Markdown(text), title="Assistant", border_style="green"))
            for tool_call in message.tool_calls or []:
                console.print(f"[dim]Tool call: {tool_call['name']}({tool_call['args']})[/dim]")
        elif isinstance(message, ToolMessage):
            content = message.content if isinstance(message.content, str) else str(message.content)
            console.print(f"[dim]Tool result ({message.name}): {content}[/dim]")


def run_chat_loop(graph, thread_config: dict, state: dict) -> None:
    console.print(Panel(
        "[bold green]Screening complete.[/bold green] Chat with the agent about the shortlist above.\n"
        "[yellow]Type 'exit'/'quit' to end, 'clear' to wipe chat history.[/yellow]",
        title="Human Feedback Loop", border_style="cyan",
    ))

    while True:
        user_text = console.input("\n[bold blue]You:[/bold blue] ").strip()
        if not user_text:
            continue

        seen = len(state.get("messages", []))
        state = graph.invoke(Command(resume=user_text), thread_config)

        if state.get("session_ended"):
            console.print(Panel("[yellow]Session ended.[/yellow]", border_style="yellow"))
            break

        if user_text.lower() == "clear":
            console.print(Panel("[bold yellow]Chat history cleared.[/bold yellow]", border_style="yellow"))
            continue

        _render_new_messages(state.get("messages", [])[seen:])


def main() -> None:
    load_dotenv()
    graph = build_graph()

    jd_source_path = console.input("[bold blue]JD path[/bold blue] (relative to root_dir/, e.g. jobs/senior_backend_engineer.txt): ").strip()
    deep_screening_answer = console.input(
        "[bold blue]Run full 3-round screening (deep analysis + recommendation)?[/bold blue] [y/N]: "
    ).strip().lower()
    deep_screening_requested = deep_screening_answer in {"y", "yes"}

    thread_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": thread_id}}
    initial_state: AgentState = {
        "thread_id": thread_id,
        "jd_source_path": jd_source_path,
        "deep_screening_requested": deep_screening_requested,
    }

    state = graph.invoke(initial_state, thread_config)

    if state.get("error"):
        console.print(f"[bold red]Error:[/bold red] {state['error']}")
        return

    run_chat_loop(graph, thread_config, state)


if __name__ == "__main__":
    main()
