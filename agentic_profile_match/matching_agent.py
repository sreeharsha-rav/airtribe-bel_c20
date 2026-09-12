"""Phase 1 pipeline (Parse JD -> Extract Requirements -> Search Resumes ->
Rank Candidates -> Generate Report) plus Phase 2's Human Feedback Loop: a
single graph node, re-entered via a self-loop edge, that hands each
conversational turn to a stateless tool-calling helper. See DESIGN.md's
Phase 1/2 node-by-node specs and AGENT_ARCHITECTURE.md for the full design
this implements.
"""

import uuid
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.types import Command, interrupt
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

import config
from fs_tools import list_files, read_file, search_in_file, write_file
from jd_parser import extract_must_have_requirements, extract_nice_to_have_requirements, split_job_sections
from ranking import MatchResult, score_and_rank
from retrieval import embed_job_description, semantic_search
from tools import compare_candidates, extract_requirements as extract_requirements_tool
from tools import generate_interview_questions, search_resumes as search_resumes_tool
from tools import session as tool_session

console = Console(record=True)

CONVERSATION_SYSTEM_PROMPT = (
    "You are a hiring-team assistant helping screen candidates for a job opening. A pipeline "
    "has already run once and produced an initial ranked shortlist, shown to you as your own "
    "first message in this conversation. From here, the human may ask you to explain the "
    "ranking, compare specific candidates, refine the search criteria, draft interview "
    "questions, or screen an entirely different job description -- all via tools, never by "
    "inventing detail you haven't retrieved.\n\n"
    "Tools:\n"
    "- search_resumes(query, must_have_keywords=[], min_experience_years=None): loose "
    "natural-language search that REPLACES the active shortlist. Use it for any refinement "
    "('also require AWS'), a fresh ad-hoc search, or a criteria-changing follow-up.\n"
    "- extract_requirements(jd_text): call this first when the human pastes a whole new job "
    "description, then call search_resumes to shortlist against it.\n"
    "- compare_candidates(candidate_identifiers): read-only side-by-side comparison of "
    "candidates already in the current shortlist (by name or resume_path).\n"
    "- generate_interview_questions(candidate_identifier): drafts interview questions grounded "
    "in a candidate's full resume text.\n"
    "- list_files/read_file/search_in_file/write_file: sandboxed filesystem access under "
    "root_dir/ (jobs/ and resumes/), e.g. to save a shortlist to a file on request.\n\n"
    "Always ground your answers in tool results -- if something isn't in a result you've seen, "
    "say you don't know rather than guessing. Be concise and specific."
)

TOOLS = [
    list_files,
    read_file,
    search_in_file,
    write_file,
    search_resumes_tool,
    extract_requirements_tool,
    compare_candidates,
    generate_interview_questions,
]

_conversational_agent = None


def get_conversational_agent():
    """Builds create_agent(model, tools=TOOLS) once, lazily. No checkpointer of
    its own -- the outer graph's checkpointer already persists state["messages"]
    across turns; this stateless helper just runs one turn's tool-calling loop
    on whatever messages it's handed (see human_feedback_loop).
    """
    global _conversational_agent
    if _conversational_agent is None:
        model = init_chat_model(model=config.MODEL_NAME, model_provider=config.MODEL_PROVIDER)
        _conversational_agent = create_agent(model=model, tools=TOOLS, system_prompt=CONVERSATION_SYSTEM_PROMPT)
    return _conversational_agent


class AgentState(TypedDict, total=False):
    thread_id: str
    jd_source_path: str
    jd_text: str
    jd_sections: dict[str, str]
    must_haves: list[str]
    nice_to_haves: list[str]
    candidate_pool: list[dict]
    match_results: list[MatchResult]
    report: str
    messages: Annotated[list[AnyMessage], add_messages]
    session_ended: bool
    error: str | None


# --- Nodes -------------------------------------------------------------------

def parse_jd(state: AgentState) -> dict:
    """Reads the JD file via the sandboxed fs_tools.read_file. Sets `error`
    (short-circuiting to END) on a bad/missing path -- no retry loop in
    Phase 1, that's conversational territory (Phase 2).
    """
    result = read_file.invoke({"filepath": state["jd_source_path"]})
    if not result["success"]:
        return {"error": result["error"]}
    return {"jd_text": result["content"]}


def route_after_parse_jd(state: AgentState) -> Literal["extract_requirements", "__end__"]:
    if state.get("error"):
        return END
    return "extract_requirements"


def extract_requirements(state: AgentState) -> dict:
    """Purely algorithmic (Q3, Phase 1) -- every posting under
    rag_profile_match/root_dir/jobs/ already follows the same 4-heading
    format jd_parser's regex parses correctly.
    """
    jd_text = state["jd_text"]
    return {
        "jd_sections": split_job_sections(jd_text),
        "must_haves": extract_must_have_requirements(jd_text),
        "nice_to_haves": extract_nice_to_have_requirements(jd_text),
    }


def search_resumes(state: AgentState) -> dict:
    """Embeds jd_sections' descriptive prose (must-haves deliberately
    excluded -- see retrieval.embed_job_description) and runs hybrid RRF
    search. Over-fetches (max(top_k*3, 15)) so Rank Candidates' hard
    must-have filter has headroom before shrinking the pool.
    """
    jd_vectors = embed_job_description(state["jd_sections"])
    pool_size = max(config.MATCH_TOP_K * 3, 15)
    candidate_pool = semantic_search(jd_vectors, top_k=pool_size)
    return {"candidate_pool": candidate_pool}


def rank_candidates(state: AgentState) -> dict:
    """Hard must-have filter + min-max score normalization, plus a
    nice-to-have overlap check for survivors (display only).
    """
    match_results = score_and_rank(
        state["candidate_pool"],
        state["must_haves"],
        state["nice_to_haves"],
    )
    return {"match_results": match_results[: config.MATCH_TOP_K]}


def _render_report(match_results: list[MatchResult], jd_source_path: str) -> str:
    if not match_results:
        table_or_message = "[yellow]No candidates satisfied every must-have requirement.[/yellow]"
        console.print(table_or_message)
        return console.export_text(clear=True)

    table = Table(title=f"Candidate Shortlist — {jd_source_path}")
    table.add_column("Rank", justify="right")
    table.add_column("Candidate")
    table.add_column("Score", justify="right")
    table.add_column("Matched Skills")
    table.add_column("Nice-to-haves Present")
    table.add_column("Reasoning")
    table.add_column("Best Excerpt")

    for rank, result in enumerate(match_results, start=1):
        best_excerpt = result.relevant_excerpts[0] if result.relevant_excerpts else "—"
        if len(best_excerpt) > 200:
            best_excerpt = best_excerpt[:200] + "..."
        table.add_row(
            str(rank),
            result.candidate_name or result.resume_path,
            f"{result.match_score:.1f}",
            ", ".join(result.matched_skills) or "—",
            ", ".join(result.nice_to_haves_satisfied) or "—",
            result.reasoning,
            best_excerpt,
        )

    console.print(table)
    return console.export_text(clear=True)


def generate_report(state: AgentState) -> dict:
    """Deterministic rich-rendered table -- no LLM call. Report text is kept
    in state and seeded as the first message so Human Feedback Loop's first
    turn already has the shortlist in context, no tool round-trip needed.
    """
    report = _render_report(state["match_results"], state["jd_source_path"])
    return {"report": report, "messages": [AIMessage(content=report)]}


def human_feedback_loop(state: AgentState) -> dict:
    """One node, re-entered via a self-loop edge -- one execution per
    conversational turn. interrupt() is called first and only once per
    execution; nothing side-effecting runs before it, since a resumed node
    re-executes its whole body from the top (see DESIGN.md's Phase 2
    Overview for the failure mode this avoids).
    """
    user_text = interrupt("Your message:")
    normalized = user_text.strip().lower()

    if normalized in {"exit", "quit"}:
        return {"session_ended": True}

    if normalized == "clear":
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)], "session_ended": False}

    tool_session.match_results = state.get("match_results", [])
    tool_session.must_haves = state.get("must_haves", [])
    tool_session.nice_to_haves = state.get("nice_to_haves", [])
    tool_session.jd_text = state.get("jd_text", "")
    tool_session.jd_sections = state.get("jd_sections", {})
    tool_session.candidate_pool = state.get("candidate_pool", [])

    prior_messages = state.get("messages", [])
    result = get_conversational_agent().invoke({"messages": prior_messages + [HumanMessage(content=user_text)]})
    new_messages = result["messages"][len(prior_messages):]

    return {
        "messages": new_messages,
        "match_results": tool_session.match_results,
        "must_haves": tool_session.must_haves,
        "nice_to_haves": tool_session.nice_to_haves,
        "jd_text": tool_session.jd_text,
        "jd_sections": tool_session.jd_sections,
        "candidate_pool": tool_session.candidate_pool,
        "session_ended": False,
    }


def route_after_human_feedback_loop(state: AgentState) -> Literal["human_feedback_loop", "__end__"]:
    return END if state.get("session_ended") else "human_feedback_loop"


# --- Graph ---------------------------------------------------------------------

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_jd", parse_jd)
    builder.add_node("extract_requirements", extract_requirements)
    builder.add_node("search_resumes", search_resumes)
    builder.add_node("rank_candidates", rank_candidates)
    builder.add_node("generate_report", generate_report)
    builder.add_node("human_feedback_loop", human_feedback_loop)

    builder.add_edge(START, "parse_jd")
    builder.add_conditional_edges("parse_jd", route_after_parse_jd)
    builder.add_edge("extract_requirements", "search_resumes")
    builder.add_edge("search_resumes", "rank_candidates")
    builder.add_edge("rank_candidates", "generate_report")
    builder.add_edge("generate_report", "human_feedback_loop")
    builder.add_conditional_edges("human_feedback_loop", route_after_human_feedback_loop)

    # MatchResult (a plain pydantic model, not a LangChain/LangGraph type) needs
    # to be explicitly allow-listed for msgpack (de)serialization -- otherwise
    # every checkpoint write triggers an "unregistered type" warning that will
    # become a hard error in a future langgraph version.
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("ranking", "MatchResult")])
    return builder.compile(checkpointer=InMemorySaver(serde=serde))


# --- CLI entrypoint --------------------------------------------------------------

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

    thread_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": thread_id}}
    initial_state: AgentState = {"thread_id": thread_id, "jd_source_path": jd_source_path}

    state = graph.invoke(initial_state, thread_config)

    if state.get("error"):
        console.print(f"[bold red]Error:[/bold red] {state['error']}")
        return

    run_chat_loop(graph, thread_config, state)


if __name__ == "__main__":
    main()
